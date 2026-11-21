"""Python Rule Engine: 필수 정보 충족 · 불충분 · 누락 판정

필드 정의(DB fields 테이블)와 정보 추출 결과를 비교해서 항목마다 상태를 매깁니다.
상태 이름은 프론트엔드(민원 필수 정보 기준표 schema 1.0.0의 evaluation_statuses)와 같습니다.
    sufficient      충족
    insufficient    불충분 (너무 짧음 / 모호함 / 형식 불일치)
    missing         누락 (값 없음)
    not_applicable  해당 없음 (조건부 필수 항목인데 이 민원은 조건에 해당하지 않음)

조건부 필수(when) 처리 — 기준 파일 rules.field_policy:
    "when 이 있는 항목은 조건에 해당할 때만 필수"
    조건 해당 여부는 문장 이해가 필요해서 AI 추출 단계가 판단하고 not_applicable 목록으로 알려 줍니다.
    - when 이 있는 항목: AI 가 not_applicable 로 표시하면 → not_applicable
    - when 이 없는 항목: 항상 필수라서 AI 가 not_applicable 로 표시해도 무시하고 값으로 판정

AI 판정과 합치기:
    - AI 가 insufficient 로 판정한 항목은 값이 있어도 불충분 (예: "집 앞"을 AI 가 막연하다고 봄)
    - AI 가 가져온 구절이 원문에 없으면(지어낸 내용) 충족으로 인정하지 않고 불충분.
      기준 파일 rules.evidence: "충족 판정은 반드시 원문에 근거해야 하며 추정으로 값을 만들어내지 않음"
"""
from __future__ import annotations

import re

# 이것만 적혀 있으면 정보가 있다고 보기 어려운 표현
VAGUE_VALUES = {
    '모름', '몰라요', '모르겠음', '모르겠어요', '없음', '없어요', '기타', '그냥',
    '여기', '거기', '저기', '근처', '이쪽', '저쪽', '아까', '예전', '최근', '요즘',
    '-', '.', '?', 'x', 'X', 'null', 'None',
}


# AI 가 가져온 구절에 원문에 없는 글자가 이만큼 연달아 있으면 '원문에 없음'으로 봄.
# 실제 HCX 응답 기준: 지어낸 "이동 조치 요청"(5)·"재발급 방법 문의"(7)는 걸리고,
# 짧게 요약한 "수거 지연"·"고지서 분실"(2)은 통과. 바꿔 말한 표현(예: "빠른 수리 요청")도 걸릴 수 있음.
UNGROUNDED_RUN = 5


def _norm(s: str) -> str:
    return re.sub(r'[^0-9A-Za-z가-힣]', '', s or '')


def unquoted_run(value: str, source_text: str) -> int:
    """value 안에서 원문(source_text)에 없는 글자가 가장 길게 이어진 길이. 0 이면 원문에 그대로 있음.
    글자 두 개씩(바이그램) 원문에 있는지로 봅니다. 띄어쓰기·문장부호는 무시."""
    v, t = _norm(value), _norm(source_text)
    if not v or v in t:
        return 0
    grams = {t[i:i + 2] for i in range(len(t) - 1)}
    covered = [False] * len(v)
    for i in range(len(v) - 1):
        if v[i:i + 2] in grams:
            covered[i] = covered[i + 1] = True
    best = run = 0
    for c in covered:
        run = 0 if c else run + 1
        best = max(best, run)
    return best


def is_grounded(value: str, source_text: str | None) -> bool:
    """AI 가 가져온 구절이 원문에 근거하는지. 원문을 모르면(None) 확인하지 않고 True."""
    if not source_text:
        return True
    return unquoted_run(value, source_text) < UNGROUNDED_RUN


def is_conditional(field: dict) -> bool:
    """조건부 필수 항목(when 이 있음)인지"""
    return bool((field.get('when') or '').strip())


def check_field(field: dict, value, not_applicable: bool = False,
                ai_insufficient: bool = False, source_text: str | None = None) -> dict:
    """필드 하나를 판정해서 프론트엔드 field_checks 항목 형식으로 돌려줍니다.
    not_applicable=True 는 조건부 필수 항목에만 적용됩니다.
    ai_insufficient=True 면 AI 가 불충분으로 판정한 것. source_text 가 있으면 값이 원문에 있는지 확인합니다."""
    text = '' if value is None else str(value).strip()
    grounded = True

    if not_applicable and is_conditional(field):
        status = 'not_applicable'
    elif not text:
        status = 'missing'
    elif not is_grounded(text, source_text):
        status, grounded = 'insufficient', False
    elif ai_insufficient:
        status = 'insufficient'
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
        # 원문에 없는 구절은 화면에 '원문: "..."' 으로 보이면 안 되므로 비움
        'evidence': (text or None) if grounded else None,
        'suggestion': field.get('hint') if needs_fix else None,
        # 화면에는 안 쓰지만 안내문 조합에 씀
        'required': bool(field.get('required', True)),
        'when': field.get('when'),
        'example': field.get('example') if needs_fix else None,
    }


def check_fields(fields: list[dict], extracted: dict | None, not_applicable=(),
                 insufficient=(), source_text: str | None = None) -> list[dict]:
    """not_applicable: AI 가 '조건에 해당하지 않음'으로 표시한 key 목록.
    insufficient: AI 가 '불충분'으로 판정한 key 목록.
    source_text: 분석한 원문 (AI 가 가져온 구절이 원문에 있는지 확인용)."""
    extracted = extracted or {}
    na, insuf = set(not_applicable or ()), set(insufficient or ())
    return [check_field(f, extracted.get(f['key']), f['key'] in na, f['key'] in insuf, source_text)
            for f in fields]


def is_complete(checks: list[dict]) -> bool:
    """필수 항목이 모두 충족(또는 해당 없음)이면 True."""
    return all(c['status'] in ('sufficient', 'not_applicable') for c in checks if c['required'])
