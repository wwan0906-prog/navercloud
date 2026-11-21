"""외국어 민원 번역: 외국어 → 한국어(분석용), 한국어 → 외국어(답변 역번역)

    translate(text, source, target) -> str

번역 엔진은 있는 키에 따라 고릅니다.
    1) .env 에 PAPAGO_CLIENT_ID / PAPAGO_CLIENT_SECRET 이 있으면 Papago (NCP Papago Translation)
    2) 없으면 HCX (AI_MODE=real 일 때, CLOVASTUDIO_API_KEY 사용)
    3) 둘 다 안 되면(mock 모드 등) 번역하지 않고 원문 그대로
"""
from __future__ import annotations

import os

import requests

from . import ai_client

PAPAGO_URL = 'https://papago.apigw.ntruss.com/nmt/v1/translation'
LANG_NAMES = {'ko': '한국어', 'en': '영어', 'ja': '일본어', 'zh-CN': '중국어(간체)'}
SUPPORTED = set(LANG_NAMES)


def engine() -> str:
    """지금 쓰는 번역 엔진 이름: papago / hcx / none"""
    if os.environ.get('PAPAGO_CLIENT_ID', '').strip() and os.environ.get('PAPAGO_CLIENT_SECRET', '').strip():
        return 'papago'
    if ai_client.mode() == 'real':
        return 'hcx'
    return 'none'


def translate(text: str, source: str, target: str) -> str:
    text = (text or '').strip()
    if not text or source == target:
        return text
    for code in (source, target):
        if code not in SUPPORTED:
            raise ValueError(f'번역을 지원하지 않는 언어입니다: {code} (가능: {", ".join(sorted(SUPPORTED))})')
    eng = engine()
    if eng == 'papago':
        return _papago(text, source, target)
    if eng == 'hcx':
        return _hcx(text, source, target)
    return text


def _papago(text: str, source: str, target: str) -> str:
    headers = {
        'X-NCP-APIGW-API-KEY-ID': os.environ['PAPAGO_CLIENT_ID'].strip(),
        'X-NCP-APIGW-API-KEY': os.environ['PAPAGO_CLIENT_SECRET'].strip(),
    }
    res = requests.post(PAPAGO_URL, headers=headers,
                        data={'source': source, 'target': target, 'text': text}, timeout=30)
    if res.status_code != 200:
        raise RuntimeError(f'Papago {res.status_code}: {res.text[:200]}')
    return res.json()['message']['result']['translatedText'].strip()


_HCX_SYSTEM = ('당신은 공공기관 민원 번역가입니다. 사용자가 보낸 {src} 문장을 {tgt}로 자연스럽고 정확하게 번역하세요. '
               '주소·고유명사·숫자는 그대로 두고, 내용을 더하거나 빼지 마세요. 번역문만 출력하세요.')


def _hcx(text: str, source: str, target: str) -> str:
    from . import hcx
    system = _HCX_SYSTEM.format(src=LANG_NAMES[source], tgt=LANG_NAMES[target])
    out = hcx._hcx(system, text, max_tokens=800, temperature=0.1)
    return out.strip().strip('"').strip()
