"""AI 호출 연결 지점: 2번 팀원 담당 (아직 없음)

백엔드는 아래 두 함수만 부릅니다. 2번 팀원은 _real_classify / _real_extract 만 채우면 됩니다.

    classify(text) -> {"category": str, "confidence": float | None}
        HCX + RAG: 민원 18개 대분류 중 하나로 분류. (파인튜닝 대신 RAG 사용으로 변경)
        "category" 는 data/guide_seed.json 의 categories[].id 와 같은 문자열이어야 합니다.
        (AI Hub 대분류 그대로: 자동차, 안전건설, 교통, ..., 문화_체육_관광, 농업_축산 ...)

    extract(text, category) -> {
        "fields": {key: 원문에서 찾은 구절 또는 None},
        "not_applicable": [key, ...],        # 선택. 이 민원에는 해당 없는 항목
        "guide_message": str,                # 선택. 주면 백엔드가 만든 안내문 대신 사용
    }
        HCX Prompt: 정보 추출.
        category["fields"][i] = {"key", "label", "hint", "example", ...} 가 추출할 항목입니다.
        값은 원문의 해당 구절을 그대로 넣으세요 (화면에 '원문: "..."' 으로 표시됨).
        원문에 없으면 None. 충족·불충분·누락 판정은 백엔드 rules.py 가 합니다.

.env 의 AI_MODE:
    mock (기본) 가짜 응답. 프론트엔드·백엔드 개발용
    real        실제 HCX 호출 (2번 팀원 코드 연결 후 사용)
"""
from __future__ import annotations

import os
import re


class AINotReady(RuntimeError):
    """AI_MODE=real 인데 아직 실제 호출 코드가 연결되지 않았을 때."""


def mode() -> str:
    return os.environ.get('AI_MODE', 'mock').strip().lower()


def classify(text: str) -> dict:
    return _real_classify(text) if mode() == 'real' else _mock_classify(text)


def extract(text: str, category: dict) -> dict:
    return _real_extract(text, category) if mode() == 'real' else _mock_extract(text, category)


# ---------------------------------------------------------------- 실제 호출 (2번 팀원이 채울 곳)
def _real_classify(text: str) -> dict:
    raise AINotReady('분류(HCX + RAG) 연결 전입니다. .env 에서 AI_MODE=mock 으로 테스트하세요.')


def _real_extract(text: str, category: dict) -> dict:
    raise AINotReady('정보 추출(HCX Prompt) 연결 전입니다. .env 에서 AI_MODE=mock 으로 테스트하세요.')


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
