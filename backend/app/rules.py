"""Python Rule Engine: 필수 정보 충족 · 불충분 · 누락 판정

필드 정의(DB fields 테이블)와 정보 추출 결과를 비교해서 항목마다 상태를 매깁니다.
상태 이름은 프론트엔드(민원 필수 정보 기준표 schema 1.0.0의 evaluation_statuses)와 같습니다.
    sufficient      충족
    insufficient    불충분 (너무 짧음 / 모호함 / 형식 불일치)
    missing         누락 (값 없음)
    not_applicable  해당 없음 (AI 가 이 민원에는 해당 없다고 표시한 항목)
"""
from __future__ import annotations

import re

# 이것만 적혀 있으면 정보가 있다고 보기 어려운 표현
VAGUE_VALUES = {
    '모름', '몰라요', '모르겠음', '모르겠어요', '없음', '없어요', '기타', '그냥',
    '여기', '거기', '저기', '근처', '이쪽', '저쪽', '아까', '예전', '최근', '요즘',
    '-', '.', '?', 'x', 'X', 'null', 'None',
}


def check_field(field: dict, value, not_applicable: bool = False) -> dict:
    """필드 하나를 판정해서 프론트엔드 field_checks 항목 형식으로 돌려줍니다."""
    text = '' if value is None else str(value).strip()

    if not_applicable:
        status = 'not_applicable'
    elif not text:
        status = 'missing'
    elif text in VAGUE_VALUES:
        status = 'insufficient'
    elif field.get('min_length') and len(text) < field['min_length']:
        status = 'insufficient'
    elif field.get('pattern') and not re.search(field['pattern'], text):
        status = 'insufficient'
    else:
        status = 'sufficient'

    needs_fix = status in ('missing', 'insufficient')
    return {
        'key': field['key'],
        'label': field['label'],
        'status': status,
        'evidence': text or None,
        'suggestion': field.get('hint') if needs_fix else None,
        # 화면에는 안 쓰지만 안내문 조합에 씀
        'required': bool(field.get('required', True)),
        'example': field.get('example') if needs_fix else None,
    }


def check_fields(fields: list[dict], extracted: dict | None, not_applicable=()) -> list[dict]:
    extracted = extracted or {}
    na = set(not_applicable or ())
    return [check_field(f, extracted.get(f['key']), f['key'] in na) for f in fields]


def is_complete(checks: list[dict]) -> bool:
    """필수 항목이 모두 충족(또는 해당 없음)이면 True."""
    return all(c['status'] in ('sufficient', 'not_applicable') for c in checks if c['required'])
