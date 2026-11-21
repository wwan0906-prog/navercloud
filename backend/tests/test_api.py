"""백엔드 테스트.  backend 폴더에서:  python -m pytest -q

CLOVA OCR/Voice 는 가짜 함수로 바꿔서 실제 API 를 부르지 않습니다 (사용량 절약).
DB 는 임시 폴더에 따로 만듭니다.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app import ai_client, clova_io, guide, main, rules

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
    assert body['official_channel'] == {'agency': '국민신문고', 'url': 'https://www.epeople.go.kr', 'phone': '110'}
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


def test_category_without_fields(client):
    body = analyze(client, '주민등록등본 발급 시간이 궁금합니다').json()
    assert body['main_category'] == '공통' and body['field_checks'] == []
    assert body['has_guide_data'] is False and '준비 중' in body['guide_message']
    assert body['official_channel']['agency'] == '국민신문고'


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
    r = analyze(client, '민원')
    assert r.status_code == 503 and '연결 전' in r.json()['detail']


def test_ai_guide_message_and_not_applicable(client, monkeypatch):
    monkeypatch.setattr(ai_client, 'extract', lambda t, c: {
        'fields': {'facility_or_work': '가로등', 'location': '세종대로 209', 'risk_status': '불이 안 켜짐'},
        'not_applicable': ['request'], 'guide_message': 'AI가 만든 안내문'})
    body = analyze(client, STREETLIGHT).json()
    assert status_of(body)['request'] == 'not_applicable'
    assert body['is_complete'] is True and body['guide_message'] == 'AI가 만든 안내문'


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
