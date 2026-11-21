"""답변 초안 · 긴급도 · 요약 · 민원 유형 (HCX 호출 1회)

    make(text, category_name, service_category, fields) -> {
        "유형": "신고|문의|건의|칭찬", "긴급도": "긴급|일반", "요약": str, "answer_draft": str
    }

- AI_MODE=real: HCX(HCX-003) 프롬프트 1회. JSON 으로 받음.
- AI_MODE=mock: 키워드 기반 가짜 응답.
- 생명·안전 위험 표현(가스 냄새, 화재, 연기, 붕괴, 감전 …)이 있으면 AI 판단과 관계없이 '긴급'으로 올립니다.
  (긴급을 일반으로 잘못 내리는 쪽이 더 위험해서, 안전 쪽으로 기울게 함)
- 답변 초안은 '간단한 행동 안내' 수준: 공감 한 문장 + 처리 방향 + 빠진 정보 요청. 확정 답변처럼 쓰지 않음.
"""
from __future__ import annotations

import re

from . import ai_client

TYPES = ('신고', '문의', '건의', '칭찬')
URGENCY = ('긴급', '일반')

# 이런 표현이 있으면 무조건 긴급
DANGER = re.compile(
    r'가스\s*(냄새|누출|새)|화재|불이\s*(났|나|붙)|불길|연기가|타는\s*냄새|폭발|붕괴|무너(져|지|질)|'
    r'감전|전선이?\s*(끊어|늘어|떨어)|쓰러(져|졌)|의식이?\s*없|피를?\s*(많이|흘)|물에\s*빠|'
    r'싱크홀|땅이\s*꺼|맨홀\s*(뚜껑)?이?\s*(열려|없)')
QUESTION = re.compile(r'\?|나요|까요|가요|는지요|궁금합니다|궁금해요|어떻게|언제|어디서|얼마나|알려\s*주세요')
PRAISE = re.compile(r'감사합니다|고맙습니다|칭찬|친절')
SUGGEST = re.compile(r'건의|제안|개선해\s*(주|달)|했으면\s*좋겠|설치해\s*(주|달)|만들어\s*(주|달)')


def make(text: str, category_name: str, service_category: str | None, fields: list[dict]) -> dict:
    out = _real(text, category_name, service_category, fields) if ai_client.mode() == 'real' else _mock(text)
    if DANGER.search(text):
        out['긴급도'] = '긴급'
    return out


# ---------------------------------------------------------------- HCX
_SYSTEM = """당신은 지방자치단체 민원 접수 담당 공무원입니다. 민원을 읽고 아래 네 가지를 판단·작성하세요.

1. 유형: 신고(문제·불편을 알리고 조치를 바람) / 문의(절차·방법·자격·일정 질문) / 건의(정책·시설 개선 제안) / 칭찬(감사) 중 하나
2. 긴급도: 긴급(생명·안전에 바로 위험: 가스 냄새, 화재, 붕괴, 감전, 도로 함몰, 사람이 다침 등) / 일반(그 외)
3. 요약: 민원 내용을 한 문장(40자 이내)으로. 원문에 없는 내용은 넣지 마세요.
4. 답변 초안: 민원인에게 보낼 짧은 첫 답변 2~3문장.
   - 불편에 공감하는 한 문장, 이 분야({service} > {category}) 담당에서 확인·처리하겠다는 안내
   - 아래 확인 항목 중 원문에 없거나 막연한 정보가 있으면 그 정보를 알려 달라고 요청
   - 긴급이면 119(화재·가스·구조) 또는 112(범죄·사고)에 먼저 신고하라고 안내
   - 처리 기한·결과를 약속하지 말고, 원문에 없는 사실을 지어내지 마세요.

확인 항목: {fields}

반드시 아래 JSON 형식으로만 답하세요.
{{"유형": "신고|문의|건의|칭찬", "긴급도": "긴급|일반", "요약": "...", "answer_draft": "..."}}"""


def _real(text: str, category_name: str, service_category: str | None, fields: list[dict]) -> dict:
    from . import hcx
    labels = ', '.join(f['label'] for f in fields) or '(없음)'
    system = _SYSTEM.format(service=service_category or category_name, category=category_name, fields=labels)
    raw = hcx._hcx(system, text, max_tokens=500, temperature=0.2)
    try:
        d = hcx._extract_json(raw)
    except Exception:
        d = {}
    mock = _mock(text)                       # 일부 값이 이상하면 키워드 판단으로 채움
    kind = str(d.get('유형', '')).strip()
    urgency = str(d.get('긴급도', '')).strip()
    summary = str(d.get('요약') or '').strip()
    answer = str(d.get('answer_draft') or '').strip()
    return {
        '유형': kind if kind in TYPES else mock['유형'],
        '긴급도': urgency if urgency in URGENCY else mock['긴급도'],
        '요약': summary or mock['요약'],
        'answer_draft': answer or mock['answer_draft'],
    }


# ---------------------------------------------------------------- mock
def _mock(text: str) -> dict:
    first = re.split(r'(?<=[.!?。])\s+|\n', text.strip())[0]
    summary = first if len(first) <= 40 else first[:39] + '…'
    if PRAISE.search(text):
        kind = '칭찬'
    elif SUGGEST.search(text):
        kind = '건의'
    elif QUESTION.search(text.strip()):
        kind = '문의'
    else:
        kind = '신고'
    urgent = bool(DANGER.search(text))
    if urgent:
        answer = ('위험한 상황으로 보입니다. 지금 위험하다면 민원 접수보다 먼저 119(화재·가스·구조) 또는 '
                  '112(범죄·사고)에 신고해 주세요. 접수된 민원은 담당자가 바로 확인하겠습니다.')
    elif kind == '문의':
        answer = '문의해 주셔서 감사합니다. 담당 분야에서 확인한 뒤 절차와 방법을 안내해 드리겠습니다.'
    elif kind == '칭찬':
        answer = '따뜻한 말씀 감사합니다. 담당 부서에 전달하겠습니다.'
    else:
        answer = '불편을 드려 죄송합니다. 담당 분야에서 현장을 확인한 뒤 처리하겠습니다. 정확한 위치를 알려 주시면 더 빠르게 처리할 수 있습니다.'
    return {'유형': kind, '긴급도': '긴급' if urgent else '일반', '요약': summary, 'answer_draft': answer}
