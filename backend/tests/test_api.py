"""백엔드 테스트.  backend 폴더에서:  python -m pytest -q

CLOVA OCR/Voice 는 가짜 함수로 바꿔서 실제 API 를 부르지 않습니다 (사용량 절약).
DB 는 임시 폴더에 따로 만듭니다.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app import ai_client, clova_io, db, guide, main, rules

STREETLIGHT = '집 앞 골목 가로등이 어제부터 안 켜져서 밤에 너무 위험해요.'
PARKING = '상가 앞에 불법 주정차 차량이 계속 세워져 있어 통행이 어렵습니다.'
FRONT_KEYS = {'main_category', 'field_checks', 'guide_message', 'official_channel'}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DB_PATH', str(tmp_path / 'test.db'))
    monkeypatch.setenv('AI_MODE', 'mock')
    monkeypatch.setattr(main, 'AUDIO_DIR', tmp_path / 'audio')

    def fake_ocr(data, filename='x.png', **k):
        if filename.endswith('.gif'):
            raise ValueError('지원하지 않는 형식: gif')
        return data.decode()                     # 테스트에서는 파일 내용을 OCR 결과로 사용
    monkeypatch.setattr(clova_io, 'extract_text', fake_ocr)

    calls = []

    def fake_tts(text, speaker='nara', speed=0, save_to=None):
        calls.append(text)
        if save_to:
            open(save_to, 'wb').write(b'ID3fake')
        return b'ID3fake'
    monkeypatch.setattr(clova_io, 'synthesize_speech', fake_tts)
    with TestClient(main.app) as c:          # with 로 열어야 서버 시작(DB 적재)이 실행됨
        c.tts_calls = calls
        yield c


def analyze(client, text='', files=()):
    return client.post('/api/analyze', data={'complaint_text': text},
                       files=[('files', f) for f in files])


def status_of(body):
    return {c['key']: c['status'] for c in body['field_checks']}


def test_health(client):
    r = client.get('/api/health').json()
    assert r['status'] == 'ok' and r['ai_mode'] == 'mock' and len(r['categories']) == 18


def test_streetlight_matches_frontend_mock(client):
    body = analyze(client, STREETLIGHT).json()
    assert FRONT_KEYS <= body.keys()
    assert body['main_category'] == '안전건설'
    assert status_of(body) == {'facility_or_work': 'sufficient', 'location': 'insufficient',
                               'risk_status': 'sufficient', 'request': 'missing'}
    loc = next(c for c in body['field_checks'] if c['key'] == 'location')
    assert loc['evidence'] == '집 앞 골목' and '도로명 주소' in loc['suggestion']
    assert set(body['field_checks'][0]) == {'key', 'label', 'status', 'evidence', 'suggestion'}
    assert body['official_channel']['agency'] == '안전신문고'          # 분야별 채널 적용 (guide_seed official_channel)
    assert '발생 위치, 요청 조치를 보완해 주세요' in body['guide_message']
    assert body['is_complete'] is False


def test_parking_matches_frontend_mock(client):
    body = analyze(client, PARKING).json()
    assert body['main_category'] == '교통'
    assert status_of(body) == {'traffic_target': 'sufficient', 'location_or_route': 'insufficient',
                               'issue_details': 'sufficient', 'request': 'missing'}


def test_complete_complaint(client):
    body = analyze(client, '세종대로 209 정문 앞 가로등이 고장 나서 위험해요. 수리해 주세요.').json()
    assert set(status_of(body).values()) == {'sufficient'}
    assert body['is_complete'] is True and '모두 들어 있습니다' in body['guide_message']


def test_common_category_has_fields(client):
    body = analyze(client, '주민등록등본 발급 시간이 궁금합니다').json()
    assert body['main_category'] == '공통' and body['has_guide_data'] is True
    assert [c['key'] for c in body['field_checks']] == ['target', 'issue_details', 'request']
    assert body['official_channel']['agency'] == '국민신문고'


def test_category_without_fields(client, monkeypatch):
    real = db.get_category
    monkeypatch.setattr(db, 'get_category', lambda cid: {**real(cid), 'fields': []})
    body = analyze(client, '주민등록등본 발급 시간이 궁금합니다').json()
    assert body['field_checks'] == [] and body['has_guide_data'] is False
    assert '준비 중' in body['guide_message']


def test_unknown_category(client, monkeypatch):
    monkeypatch.setattr(ai_client, 'classify', lambda t: {'category': '없는분야', 'confidence': 0.4})
    body = analyze(client, '아무 민원').json()
    assert body['main_category'] == '없는분야' and body['field_checks'] == []
    assert '안내 기준이 없습니다' in body['guide_message']


def test_photos_are_ocred_and_combined(client):
    body = analyze(client, '', files=[('a.png', PARKING.encode(), 'image/png')]).json()
    assert body['ocr_texts'] == [PARKING] and body['main_category'] == '교통'
    assert body['complaint_text'] == ''


def test_bad_photo_is_warning_not_error(client):
    r = analyze(client, STREETLIGHT, files=[('a.gif', b'x', 'image/gif')])
    assert r.status_code == 200 and 'gif' in r.json()['warnings'][0]


def test_empty_input(client):
    assert analyze(client).status_code == 400
    r = analyze(client, files=[('a.gif', b'x', 'image/gif')])
    assert r.status_code == 400 and 'gif' in r.json()['detail']


def test_too_many_photos(client):
    files = [(f'{i}.png', b'x', 'image/png') for i in range(6)]
    assert analyze(client, 'x', files=files).status_code == 400


def test_ai_not_ready(client, monkeypatch):
    monkeypatch.setenv('AI_MODE', 'real')
    # .env 에 HCX 키가 있어도 '키 없음' 상황을 만들어서 실제 HCX 를 부르지 않게 함
    monkeypatch.delenv('CLOVASTUDIO_API_KEY', raising=False)
    monkeypatch.delenv('NCP_CLOVASTUDIO_API_KEY', raising=False)
    r = analyze(client, '민원')
    assert r.status_code == 503 and '연결 전' in r.json()['detail']


def test_ai_guide_message_and_not_applicable(client, monkeypatch):
    # location 은 when 있음(현장 신고일 때만 필수) → 해당 없음 인정
    monkeypatch.setattr(ai_client, 'extract', lambda t, c: {
        'fields': {'facility_or_work': '가로등', 'risk_status': '불이 안 켜짐', 'request': '수리 요청'},
        'not_applicable': ['location'], 'guide_message': 'AI가 만든 안내문'})
    body = analyze(client, STREETLIGHT).json()
    assert status_of(body)['location'] == 'not_applicable'
    assert body['is_complete'] is True and body['guide_message'] == 'AI가 만든 안내문'


def test_not_applicable_ignored_for_unconditional_field(client, monkeypatch):
    # request 는 when 없음(항상 필수) → AI 가 해당 없음이라고 해도 값으로 판정
    monkeypatch.setattr(ai_client, 'extract', lambda t, c: {
        'fields': {'facility_or_work': '가로등', 'location': '세종대로 209', 'risk_status': '불이 안 켜짐'},
        'not_applicable': ['request']})
    body = analyze(client, STREETLIGHT).json()
    assert status_of(body)['request'] == 'missing'
    assert body['is_complete'] is False and '요청 조치를 보완해 주세요' in body['guide_message']


def test_saved_listed_and_audio_cached(client):
    created = analyze(client, STREETLIGHT).json()
    assert client.get(f'/api/complaints/{created["id"]}').json() == created
    assert client.get('/api/complaints').json()[0]['id'] == created['id']
    assert client.get('/api/complaints/9999').status_code == 404
    for _ in range(2):
        r = client.get(f'/api/complaints/{created["id"]}/audio')
        assert r.status_code == 200 and r.headers['content-type'] == 'audio/mpeg'
    assert len(client.tts_calls) == 1            # 두 번째는 저장된 파일 재사용
    assert client.tts_calls[0].startswith('안전건설 분야 민원입니다.')


def test_tts(client):
    r = client.post('/api/tts', json={'text': '안녕하세요'})
    assert r.status_code == 200 and r.content == b'ID3fake'
    assert client.post('/api/tts', json={'text': 'x', 'speed': 9}).status_code == 422


def test_categories(client):
    cats = client.get('/api/categories').json()
    assert [c['id'] for c in cats][:3] == ['자동차', '안전건설', '교통']
    assert cats[1]['fields'][0]['key'] == 'facility_or_work'
    loc = cats[1]['fields'][1]
    assert loc['key'] == 'location' and loc['when'] and loc['check']
    assert cats[1]['fields'][0]['when'] is None
    assert all(c['fields'] for c in cats)


# ---------------------------------------------------------------- 규칙 엔진 · 문장
@pytest.mark.parametrize('value, status', [
    (None, 'missing'), ('', 'missing'), ('근처', 'insufficient'),
    ('집 앞 골목', 'insufficient'), ('상가 앞', 'insufficient'),
    ('OO아파트 정문 앞', 'sufficient'), ('세종대로 209', 'sufficient'),
])
def test_rule_location(value, status):
    seed = json.loads(open('data/guide_seed.json', encoding='utf-8').read())
    field = next(f for c in seed['categories'] if c['id'] == '안전건설'
                 for f in c['fields'] if f['key'] == 'location')
    assert rules.check_field(field, value)['status'] == status


@pytest.mark.parametrize('field, na, status', [
    ({'key': 'x', 'label': 'x', 'when': '현장 신고인 경우'}, True, 'not_applicable'),
    ({'key': 'x', 'label': 'x', 'when': '현장 신고인 경우'}, False, 'missing'),
    ({'key': 'x', 'label': 'x'}, True, 'missing'),
    ({'key': 'x', 'label': 'x', 'when': '  '}, True, 'missing'),
])
def test_rule_when(field, na, status):
    assert rules.check_field(field, None, not_applicable=na)['status'] == status


def test_josa():
    assert guide.josa('요청 조치', '을', '를') == '요청 조치를'
    assert guide.josa('요청 사항', '을', '를') == '요청 사항을'


def test_seed_is_valid():
    seed = json.loads(open('data/guide_seed.json', encoding='utf-8').read())
    ids = [c['id'] for c in seed['categories']]
    assert len(ids) == 18 == len(set(ids))
    for cat in seed['categories']:
        keys = [f['key'] for f in cat['fields']]
        assert len(keys) == len(set(keys)), f'{cat["id"]}: 필드 key 중복'
        assert keys, f'{cat["id"]}: 필드 없음'
        for f in cat['fields']:
            assert f.get('hint') and f.get('example'), f'{cat["id"]}.{f["key"]}: hint/example 없음'


def test_seed_matches_requirements():
    """guide_seed.json 의 key·label·check·when 이 팀 기준 파일과 같은지"""
    seed = json.loads(open('data/guide_seed.json', encoding='utf-8').read())
    req = json.loads(open('data/category_requirements.json', encoding='utf-8').read())
    pick = lambda f: (f['key'], f['label'], f['check'], f.get('when'))
    assert {c['id'] for c in seed['categories']} == set(req['categories'])
    for cat in seed['categories']:
        expected = [pick(f) for f in req['categories'][cat['id']]['required_fields']]
        assert [pick(f) for f in cat['fields']] == expected, cat['id']


@pytest.mark.parametrize('raw, expected', [
    ('교통', '교통'), (' "교통" ', '교통'), ('교통.', '교통'), ('분류: 세무', '세무'),
    ('문화·체육·관광', '문화_체육_관광'), ('문화 체육 관광', '문화_체육_관광'), ('농업/축산', '농업_축산'),
    ('이 민원은 상하수도 분야입니다', '상하수도'), ('없는분야', '없는분야'), (None, ''),
])
def test_normalize_category(raw, expected):
    ids = ['교통', '세무', '문화_체육_관광', '농업_축산', '상하수도']
    assert ai_client.normalize_category(raw, ids) == expected


def test_analyze_normalizes_tuned_model_label(client, monkeypatch):
    monkeypatch.setattr(ai_client, 'classify', lambda t: {'category': ' "교통"\n', 'confidence': None})
    body = analyze(client, PARKING).json()
    assert body['main_category'] == '교통' and body['has_guide_data'] is True


# ---------------------------------------------------------------- 사진·음성 → 글자
def test_ocr(client):
    r = client.post('/api/ocr', files={'image': ('a.png', '민원 신청서'.encode(), 'image/png')})
    assert r.status_code == 200 and r.json() == {'text': '민원 신청서'}
    assert client.post('/api/ocr', files={'image': ('a.gif', b'x', 'image/gif')}).status_code == 400
    assert client.post('/api/ocr').status_code == 422


def test_stt(client, monkeypatch):
    seen = {}

    def fake_stt(data, lang='ko'):
        seen.update(data=data, lang=lang)
        return '가로등이 고장났어요'
    monkeypatch.setattr(clova_io, 'transcribe_audio', fake_stt)
    r = client.post('/api/stt', files={'audio': ('voice.m4a', b'm4a-bytes', 'audio/m4a')}, data={'lang': 'en'})
    assert r.status_code == 200 and r.json() == {'text': '가로등이 고장났어요', 'lang': 'en'}
    assert seen == {'data': b'm4a-bytes', 'lang': 'en'}


def test_stt_unsupported_language(client):
    r = client.post('/api/stt', files={'audio': ('v.m4a', b'x', 'audio/m4a')}, data={'lang': 'vi'})
    assert r.status_code == 400 and 'vi' in r.json()['detail']


# ---------------------------------------------------------------- AI 판정과 합치기
def test_ai_insufficient_is_respected(client, monkeypatch):
    """AI 가 불충분으로 본 항목은 백엔드 규칙상 통과해도 불충분"""
    monkeypatch.setattr(ai_client, 'extract', lambda t, c: {
        'fields': {'facility_or_work': '가로등', 'location': '세종대로 209', 'risk_status': '어제부터 안 켜짐',
                   'request': '수리'}, 'insufficient': ['facility_or_work']})
    body = analyze(client, '세종대로 209 가로등이 어제부터 안 켜짐. 수리 부탁').json()
    assert status_of(body)['facility_or_work'] == 'insufficient'
    assert status_of(body)['location'] == 'sufficient'


def test_made_up_evidence_is_not_sufficient(client, monkeypatch):
    """원문에 없는 구절(지어낸 요청)은 충족으로 인정하지 않고, 원문으로 표시하지도 않음"""
    monkeypatch.setattr(ai_client, 'classify', lambda t: {'category': '교통', 'confidence': None})
    monkeypatch.setattr(ai_client, 'extract', lambda t, c: {'fields': {
        'traffic_target': '불법 주정차 차량', 'location_or_route': '세종대로 209 앞',
        'issue_details': '세워져 있어 통행이 어렵습니다', 'request': '불법 주정차 차량 이동 조치 요청'}})
    body = analyze(client, '세종대로 209 앞에 불법 주정차 차량이 계속 세워져 있어 통행이 어렵습니다.').json()
    req = next(c for c in body['field_checks'] if c['key'] == 'request')
    assert req['status'] == 'insufficient' and req['evidence'] is None and req['suggestion']
    assert status_of(body)['traffic_target'] == 'sufficient'
    assert body['is_complete'] is False


@pytest.mark.parametrize('value, text, grounded', [
    ('불법 주정차 차량 이동 조치 요청', '상가 앞에 불법 주정차 차량이 계속 세워져 있어 통행이 어렵습니다.', False),
    ('재발급 방법 문의', '재산세 고지서를 잃어버렸는데 어떻게 다시 받을 수 있나요?', False),
    ('수거 지연', '음식물 쓰레기통이 3일째 수거가 안 돼서 냄새가 심해요.', True),
    ('고지서 분실', '재산세 고지서를 잃어버렸는데 어떻게 다시 받을 수 있나요?', True),
    ('상가 앞 불법 주정차 차량', '상가 앞에 불법 주정차 차량이 계속 세워져 있어요', True),
    ('아무거나', None, True),
])
def test_is_grounded(value, text, grounded):
    assert rules.is_grounded(value, text) is grounded
