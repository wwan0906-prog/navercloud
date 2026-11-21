"""AI 호출 연결 지점: 2번 팀원 담당 — app/hcx.py 로 연결됨 (AI_MODE=real)

백엔드는 아래 두 함수만 부릅니다. 2번 팀원은 _real_classify / _real_extract 만 채우면 됩니다.

    classify(text) -> {"category": str, "confidence": float | None}
        HCX 튜닝 모델: 민원 18개 대분류 중 하나로 분류.
        튜닝 모델 호출: POST https://clovastudio.stream.ntruss.com/v2/tasks/{taskId}/chat-completions
                      (Authorization: Bearer {CLOVASTUDIO_API_KEY}, .env 의 HCX_TUNING_TASK_ID)
        모델 출력에 따옴표·공백·가운뎃점이 섞여도 백엔드가 normalize_category() 로 라벨을 맞춥니다.
        "category" 는 data/guide_seed.json 의 categories[].id 와 같은 문자열이어야 합니다.
        (AI Hub 대분류 그대로: 자동차, 안전건설, 교통, ..., 문화_체육_관광, 농업_축산 ...)

    extract(text, category) -> {
        "fields": {key: 원문에서 찾은 구절 또는 None},
        "not_applicable": [key, ...],        # 선택. when 조건에 해당하지 않는 항목
        "guide_message": str,                # 선택. 주면 백엔드가 만든 안내문 대신 사용
    }
        HCX Prompt: 정보 추출.
        category["fields"][i] = {"key", "label", "check", "when", "hint", "example", ...} 가 추출할 항목입니다.
        (기준: data/category_requirements.json. check = 충족 판정 기준, when = 조건부 필수 조건)
        값은 원문의 해당 구절을 그대로 넣으세요 (화면에 '원문: "..."' 으로 표시됨).
        원문에 없으면 None. 추정으로 값을 만들지 마세요 (기준 파일 rules.evidence).
        when 이 있는 항목은 이 민원이 그 조건에 해당하지 않으면 not_applicable 에 key 를 넣으세요.
        when 이 없는 항목은 항상 필수라서 not_applicable 에 넣어도 무시됩니다.
        충족·불충분·누락 판정은 백엔드 rules.py 가 합니다.

.env 의 AI_MODE:
    mock (기본) 가짜 응답. 프론트엔드·백엔드 개발용
    real        실제 HCX 호출 (2번 팀원 코드 연결 후 사용)
"""
from __future__ import annotations

import os
import re


class AINotReady(RuntimeError):
    """AI_MODE=real 인데 아직 실제 호출 코드가 연결되지 않았을 때."""


def normalize_category(label, valid_ids) -> str:
    """튜닝 모델이 낸 라벨을 DB 의 대분류 id 로 맞춥니다. 못 맞추면 정리한 문자열을 그대로 돌려줍니다.
    예: ' "교통" ' → 교통 / '문화·체육·관광' → 문화_체육_관광 / '분류: 세무' → 세무"""
    text = str(label or '').strip().strip('"\'`[](){}<>.。 ')
    if text.startswith('분류:') or text.startswith('대분류:'):
        text = text.split(':', 1)[1].strip()
    if text in valid_ids:
        return text
    key = re.sub(r'[\s·ㆍ,/_-]+', '_', text).strip('_')
    for vid in valid_ids:
        if key == vid or key.replace('_', '') == vid.replace('_', ''):
            return vid
    found = [vid for vid in valid_ids if vid in text]       # 문장 속에 라벨이 하나만 들어 있는 경우
    return found[0] if len(found) == 1 else text


def mode() -> str:
    return os.environ.get('AI_MODE', 'mock').strip().lower()


def classify(text: str) -> dict:
    return _real_classify(text) if mode() == 'real' else _mock_classify(text)


def extract(text: str, category: dict) -> dict:
    return _real_extract(text, category) if mode() == 'real' else _mock_extract(text, category)


# ---------------------------------------------------------------- 실제 호출 (2번 팀원: app/hcx.py)
# 흐름: 튜닝 모델(8개 서비스 분야) → 프롬프트(그 분야에 속한 AI Hub 대분류 중 선택, 신고/문의 판별) → 프롬프트(항목별 추출·판정)
# 분류 결과의 intent(신고/문의)를 추출 프롬프트에 넘기려고 마지막 분류 결과를 잠시 들고 있습니다.
_last_intent: dict[str, str] = {}


def _real_classify(text: str) -> dict:
    from . import hcx
    res = hcx.classify(text)
    _last_intent[text] = res.get('intent', '신고')
    if len(_last_intent) > 200:          # 메모리 보호
        _last_intent.pop(next(iter(_last_intent)))
    return res


def _real_extract(text: str, category: dict) -> dict:
    from . import hcx
    return hcx.extract(text, category, _last_intent.get(text, '신고'))


# ---------------------------------------------------------------- 가짜 응답 (개발용)
# 실제 모델이 아닙니다. 프론트엔드 예시 버튼 두 개(가로등 고장, 불법주차)가
# 그럴듯하게 나오도록 키워드로 흉내만 냅니다.
_MOCK_CATEGORY_KEYWORDS = [
    ('교통', r'주차|주정차|버스|신호|택시|교통|정류장'),
    ('안전건설', r'가로등|도로|공사|보도|파손|맨홀|육교|하수구'),
]
_PLACE = r'(?:[^\s.,!?]+\s+){0,2}[^\s.,!?]+\s*(?:앞|옆|뒤|근처|건너편)(?:\s*골목)?'  # 앞 단어 2개까지
_SENTENCE = r'[^.!?]*{}[^.!?]*'
_MOCK_FIELD_PATTERNS = {
    'location': _PLACE,
    'location_or_route': _PLACE,
    'facility_or_work': r'가로등|신호등|보도블록|도로|맨홀|공사\s*현장|공사|육교|하수구',
    'traffic_target': r'불법\s*주정차\s*차량|불법\s*주정차|주차|버스|신호등|택시',
    'risk_status': _SENTENCE.format(r'(?:위험|파손|고장|안\s*켜|깨져|무너)'),
    'issue_details': _SENTENCE.format(r'(?:어렵|막혀|위험|불편|세워져)'),
    'request': _SENTENCE.format(r'(?:해\s*주세요|바랍니다|요청|단속\s*해|수리\s*해)'),
}


def _mock_classify(text: str) -> dict:
    for category, pattern in _MOCK_CATEGORY_KEYWORDS:
        if re.search(pattern, text):
            return {'category': category, 'confidence': None}
    return {'category': '공통', 'confidence': None}


def _mock_extract(text: str, category: dict) -> dict:
    fields = {}
    for f in category.get('fields', []):
        pattern = _MOCK_FIELD_PATTERNS.get(f['key'])
        m = re.search(pattern, text) if pattern else None
        fields[f['key']] = m.group(0).strip() if m else None
    return {'fields': fields}
