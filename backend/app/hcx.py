"""HCX 실제 호출 (2번 팀원): 분류 · 세부 유형 · 정보 추출

ai_client._real_classify / _real_extract 가 이 모듈을 부릅니다. 백엔드의 다른 부분은 손대지 않습니다.

구조
    1) classify_service(text)   튜닝 모델(HCX-003 LoRA, 작업 ID .env HCX_TUNING_TASK_ID) → 8개 서비스 분야
    2) classify_subtype(text, service)   HCX 프롬프트 → 그 분야에 속한 AI Hub 대분류(18개 중 2~4개) 하나 선택 + 신고/문의
    3) extract(text, category)  HCX 프롬프트 → category["fields"] 항목별 value / status(sufficient·insufficient·missing·not_applicable)

8개 분야 ↔ 18개 대분류 매핑: data/hcx/mapping.json
튜닝 때 쓴 시스템 프롬프트(글자 하나까지 같아야 함): data/hcx/system_prompt.txt
세부 유형 few-shot 예문: data/hcx/fewshot_subcategory.json

평가(같은 test 400건): 베이스 49.8% → few-shot 56.8% → 튜닝 74.5%  (ml/results/compare.md)
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path

import requests

HOST = 'https://clovastudio.stream.ntruss.com'
BASE_MODEL = 'HCX-003'
DATA = Path(__file__).resolve().parent.parent / 'data' / 'hcx'

MAPPING: dict[str, list[str]] = json.loads((DATA / 'mapping.json').read_text(encoding='utf-8'))
SERVICE_LABELS = list(MAPPING.keys())
SYSTEM_PROMPT = (DATA / 'system_prompt.txt').read_text(encoding='utf-8').strip()
_fs = DATA / 'fewshot_subcategory.json'
FEWSHOT_SUB = json.loads(_fs.read_text(encoding='utf-8')) if _fs.exists() else {}

SUBTYPE_DESC = {
    '자동차': '불법주정차, 주차단속, 차량 등록·이전, 차량 자체 문제',
    '교통': '신호등, 교차로, 버스·택시 등 대중교통, 노선, 교통 흐름',
    '안전건설': '도로·보도 파손, 공사장, 옹벽, 가로등 등 시설물 안전',
    '건축허가': '건축물 신축·증축·용도변경, 옥외광고물, 불법 건축',
    '토지': '지번·경계·측량·지적, 토지 이용',
    '환경미화': '쓰레기 투기·수거, 악취, 미세먼지, 재활용, 폐기물',
    '위생': '식당·업소 위생, 식품, 공중위생업소',
    '상하수도': '누수, 단수, 수압, 하수 역류, 수도 요금',
    '산림': '가로수·수목, 공원·놀이터·등산로 등 공원시설 관리, 산림 훼손 (공원 내 쓰레기·시설 문제 포함)',
    '농업_축산': '작물·가축·농지·축사, 농업 지원, 반려동물·유기동물·동물 등록',
    '복지': '복지 급여·돌봄·지원사업, 아동·노인·장애인 복지',
    '보건소': '예방접종, 검진, 보건증, 의료기관 신고, 보건소 이용',
    '세무': '지방세(재산세·자동차세·취득세 등), 과태료 납부, 세금 문의',
    '행정': '증명서 발급, 여권, 주민등록, 처리 지연, 공무원 응대',
    '공통': '특정 분야로 보기 어려운 일반 진정·건의·제안',
    '정보통신': '공공 홈페이지·앱 오류, 통신 설비',
    '경제': '소상공인·일자리·지역경제 지원사업, 시장, 상거래',
    '문화_체육_관광': '문화·체육시설, 행사, 관광지, 숙박업',
}


# ---------------------------------------------------------------- HCX 호출
def _api_key() -> str:
    key = (os.environ.get('CLOVASTUDIO_API_KEY') or os.environ.get('NCP_CLOVASTUDIO_API_KEY') or '').strip()
    if not key:
        from .ai_client import AINotReady
        raise AINotReady('HCX 연결 전: CLOVASTUDIO_API_KEY 가 .env 에 없습니다. AI_MODE=mock 으로 테스트하세요.')
    return key if key.startswith('Bearer ') else f'Bearer {key}'


def _task_id() -> str:
    return (os.environ.get('HCX_TUNING_TASK_ID') or os.environ.get('TUNED_TASK_ID') or 'k6n4aqqb').strip()


def _hcx(system: str, user: str, task: str | None = None, max_tokens: int = 400, temperature: float = 0.1) -> str:
    url = f'{HOST}/v2/tasks/{task}/chat-completions' if task else f'{HOST}/v1/chat-completions/{BASE_MODEL}'
    headers = {'Authorization': _api_key(), 'X-NCP-CLOVASTUDIO-REQUEST-ID': uuid.uuid4().hex,
               'Content-Type': 'application/json'}
    body = {'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
            'maxTokens': max_tokens, 'temperature': temperature, 'topP': 0.8, 'topK': 0, 'repeatPenalty': 1.1}
    for attempt in range(3):
        r = requests.post(url, headers=headers, json=body, timeout=60)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code != 200:
            raise RuntimeError(f'HCX {r.status_code}: {r.text[:200]}')
        return r.json()['result']['message']['content'].strip()
    raise RuntimeError('HCX 재시도 초과 (429/5xx)')


def _extract_json(text: str) -> dict:
    text = re.sub(r'```(?:json)?', '', text)
    m = re.search(r'\{.*\}', text, re.S)
    if not m:
        raise ValueError(f'JSON 없음: {text[:120]}')
    return json.loads(m.group(0))


def _match(answer: str, candidates: list[str]) -> str | None:
    norm = lambda s: re.sub(r'[\s·•ㆍ"\'.,_/]', '', s)
    a = norm(answer)
    for c in candidates:
        if norm(c) in a:
            return c
    return None


# ---------------------------------------------------------------- 1) 8개 서비스 분야 (튜닝 모델)
def classify_service(text: str, use_tuned: bool = True) -> dict:
    raw = _hcx(SYSTEM_PROMPT, text, task=_task_id() if use_tuned else None, max_tokens=20, temperature=0.01)
    return {'service': _match(raw, SERVICE_LABELS), 'raw': raw}


# ---------------------------------------------------------------- 2) 세부 유형 = AI Hub 대분류 (프롬프트)
_SUBTYPE_SYSTEM = """당신은 지방자치단체 민원 담당자입니다. 민원이 아래 세부 유형 중 어디에 해당하는지 하나만 고르세요.

세부 유형과 설명:
{options}

{examples}또한 민원의 성격을 판단하세요.
- "신고": 현장의 문제·불편·위험을 알리고 조치(단속·수거·수리·점검)를 바라는 것
- "문의": 절차·방법·자격·일정·비용 등을 질문하는 것

반드시 아래 JSON 형식으로만 답하세요. 다른 말은 쓰지 마세요.
{{"subtype": "<세부 유형 이름>", "intent": "신고|문의", "reason": "<한 문장>"}}"""


def classify_subtype(text: str, service: str) -> dict:
    cands = MAPPING[service]
    options = '\n'.join(f'- {c}: {SUBTYPE_DESC.get(c, "")}' for c in cands)
    ex = []
    for c in cands:
        for _sub, texts in list(FEWSHOT_SUB.get(c, {}).items())[:2]:
            if texts:
                ex.append(f'민원: {texts[0]}\n→ {{"subtype": "{c}"}}')
    examples = ('예시:\n' + '\n'.join(ex[:6]) + '\n\n') if ex else ''
    raw = _hcx(_SUBTYPE_SYSTEM.format(options=options, examples=examples), text, max_tokens=150)
    try:
        d = _extract_json(raw)
        sub = _match(str(d.get('subtype', '')), cands) or cands[0]
        intent = '문의' if '문의' in str(d.get('intent', '')) else '신고'
    except Exception:
        sub = _match(raw, cands) or cands[0]
        intent = '문의' if re.search(r'(나요|가요|까요|하죠|어떻게|뭐가|얼마나|궁금)', text) else '신고'
    return {'subtype': sub, 'intent': intent, 'raw': raw}


def classify(text: str) -> dict:
    """ai_client._real_classify 용. category = AI Hub 대분류 id (guide_seed.json categories[].id 와 동일)"""
    svc = classify_service(text)
    if not svc['service']:
        # 튜닝 모델 답이 8개 분야 어디에도 안 맞으면 오류 대신 '공통'(일반 진정·건의)으로 (백엔드 담당 수정)
        return {'category': '공통', 'confidence': None, 'service_category': '세무·행정',
                'intent': '문의' if re.search(r'(나요|가요|까요|어떻게|궁금)', text) else '신고',
                'fallback': f'분야 판독 실패: {svc["raw"][:60]!r}'}
    if len(MAPPING[svc['service']]) == 1:
        sub = {'subtype': MAPPING[svc['service']][0], 'intent': '신고', 'raw': ''}
    else:
        sub = classify_subtype(text, svc['service'])
    return {'category': sub['subtype'], 'confidence': None,
            'service_category': svc['service'], 'intent': sub['intent']}


# ---------------------------------------------------------------- 3) 정보 추출 (프롬프트)
_FIELDS_SYSTEM = """당신은 지방자치단체 민원 접수 담당자입니다. 민원 원문을 읽고, 아래 각 항목이 원문에 충분히 들어 있는지 판정하세요.

판정 기준:
- sufficient: 항목의 check 기준을 원문이 충족함
- insufficient: 언급은 있지만 check 기준에 못 미침 (예: "집 앞"처럼 위치가 막연함)
- missing: 원문에 전혀 없음
- not_applicable: when 조건에 해당하지 않아 검사 대상이 아님

규칙:
1. 원문에 없는 내용을 추측해서 채우지 마세요. value 에는 원문에서 찾은 표현을 그대로 적고, 없으면 null.
2. 조금이라도 언급이 있으면 missing 이 아니라 insufficient 입니다. missing 은 전혀 언급이 없을 때만.
3. "3일째", "일주일째", "밤마다", "어제부터" 같은 상대적 시간 표현도 일시 정보로 인정합니다.
4. when 조건이 있는 항목은, 민원이 그 조건에 해당하지 않으면 반드시 not_applicable 로 판정합니다.
5. 이 민원의 성격은 "{intent}"입니다. 문의(절차·방법·자격·일정 질문)인 경우 발생 위치·일시·현장 상황·피해 규모 같은 현장 항목은 not_applicable 로 판정합니다.
6. 신청인의 이름·연락처는 검사하지 않습니다.

검사 항목 (세부 유형: {category}):
{fields}

반드시 아래 JSON 형식으로만 답하세요.
{{"fields": [{{"key": "...", "status": "sufficient|insufficient|missing|not_applicable", "value": "원문 표현 또는 null", "note": "부족하면 무엇이 더 필요한지 한 문장"}}]}}"""


def extract(text: str, category: dict, intent: str = '신고') -> dict:
    """ai_client._real_extract 용.
    반환: {"fields": {key: 원문 구절|None}, "not_applicable": [key], "insufficient": [key], "notes": {key: 보완 메모}}
    (충족/불충분/누락 최종 판정은 백엔드 rules.py. insufficient 는 참고용 — rules.py 가 쓰면 LLM 판정이 반영됨)"""
    spec = category.get('fields') or []
    if not spec:
        return {'fields': {}}
    lines = []
    for f in spec:
        when = f" (when: {f['when']})" if f.get('when') else ''
        lines.append(f"- key={f['key']} / {f['label']}{when}\n  check: {f.get('check', '')}")
    raw = _hcx(_FIELDS_SYSTEM.format(intent=intent, category=category.get('name') or category.get('id', ''),
                                     fields='\n'.join(lines)), text, max_tokens=600)
    d = _extract_json(raw)
    by_key = {x.get('key'): x for x in d.get('fields', [])}
    fields, na, insuf, notes = {}, [], [], {}
    for f in spec:
        x = by_key.get(f['key'], {})
        st = x.get('status', 'missing')
        val = x.get('value')
        val = None if val in (None, '', 'null', 'None') else str(val).strip()
        if st == 'not_applicable':
            na.append(f['key'])
            fields[f['key']] = None
        else:
            fields[f['key']] = val
            if st == 'insufficient':
                insuf.append(f['key'])
        if x.get('note'):
            notes[f['key']] = x['note']
    return {'fields': fields, 'not_applicable': na, 'insufficient': insuf, 'notes': notes, 'raw': raw}
