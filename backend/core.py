"""민원 자동 분류 프로젝트 - 입출력 모듈 (OCR 입력 / TTS 출력)

화면 담당이 import 해서 쓰는 함수 3개:
    extract_text(image_bytes, filename)  이미지 → 민원 텍스트 (CLOVA OCR General)
    normalize_input(text=None, image_bytes=None, filename=None)
                                         텍스트/이미지 중 들어온 것을 {"text", "source"}로 통일
    synthesize_speech(text, speaker=...) 행동강령 텍스트 → mp3 bytes (CLOVA Voice)

키는 같은 폴더의 .env 에서 읽습니다 (.env.example 참고).
"""
from __future__ import annotations

import base64
import os
import re
import time
import uuid
from pathlib import Path

import requests

MODULE_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------------- 설정 (.env)
def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"\''))


_load_env(MODULE_DIR / '.env')

VOICE_URL = 'https://naveropenapi.apigw.ntruss.com/tts-premium/v1/tts'
OCR_FORMATS = {'jpg', 'jpeg', 'png', 'pdf', 'tif', 'tiff'}
TTS_MAX_CHARS = 1000          # 한 번 요청에 보낼 최대 글자 수 (길면 문장 단위로 나눠 보냄)


def _env(name: str) -> str:
    value = os.environ.get(name, '').strip()
    if not value:
        raise RuntimeError(f'.env 에 {name} 값이 없습니다. ({MODULE_DIR / ".env"})')
    return value


# ---------------------------------------------------------------- 입력: OCR
def extract_text(image_bytes: bytes, filename: str = 'image.png',
                 min_confidence: float = 0.0) -> str:
    """CLOVA OCR(General)로 이미지 속 글자를 읽어 한 덩어리 텍스트로 돌려줍니다.

    실습(03회차 7-3)은 Object Storage 공개 URL을 넘겼지만, 여기서는 업로드받은
    이미지를 바로 보내도록 base64(`data` 필드)로 넣습니다.
    min_confidence 보다 신뢰도가 낮은 글자 조각은 버립니다 (기본 0 = 모두 사용).
    """
    fmt = Path(filename).suffix.lower().lstrip('.') or 'png'
    if fmt not in OCR_FORMATS:
        raise ValueError(f'지원하지 않는 형식: {fmt} (가능: {", ".join(sorted(OCR_FORMATS))})')
    if fmt == 'tif':
        fmt = 'tiff'

    body = {
        'version': 'V2',
        'requestId': uuid.uuid4().hex,
        'timestamp': int(time.time() * 1000),
        'lang': 'ko',
        'images': [{
            'format': fmt,
            'name': Path(filename).stem or 'minwon',
            'data': base64.b64encode(image_bytes).decode('ascii'),
        }],
    }
    headers = {'Content-Type': 'application/json', 'X-OCR-SECRET': _env('CLOVA_OCR_SECRET')}
    res = requests.post(_env('CLOVA_OCR_INVOKE_URL'), headers=headers, json=body, timeout=60)
    if res.status_code != 200:
        raise RuntimeError(f'CLOVA OCR {res.status_code}: {res.text[:300]}')

    text_parts = []
    for image in res.json().get('images', []):
        if image.get('inferResult') != 'SUCCESS':
            raise RuntimeError(f'OCR 판독 실패: {image.get("message", image.get("inferResult"))}')
        for field in image.get('fields', []):
            if field.get('inferConfidence', 1.0) < min_confidence:
                continue
            text_parts.append(field.get('inferText', ''))
            # lineBreak=True 이면 그 조각 뒤에서 줄이 바뀝니다
            text_parts.append('\n' if field.get('lineBreak') else ' ')
    return _clean(''.join(text_parts))


def _clean(text: str) -> str:
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r' *\n *', '\n', text)
    return text.strip()


def normalize_input(text: str | None = None, image_bytes: bytes | None = None,
                    filename: str | None = None) -> dict:
    """텍스트 또는 이미지 중 들어온 것을 분류 모델에 넘길 형식으로 통일합니다.

    둘 다 들어오면 직접 입력한 텍스트를 우선합니다.
    반환: {"text": "민원 원문", "source": "text" | "ocr"}
    """
    if text and text.strip():
        return {'text': _clean(text), 'source': 'text'}
    if image_bytes:
        extracted = extract_text(image_bytes, filename or 'image.png')
        if not extracted:
            raise ValueError('이미지에서 글자를 찾지 못했습니다.')
        return {'text': extracted, 'source': 'ocr'}
    raise ValueError('민원 텍스트나 이미지 중 하나는 있어야 합니다.')


# ---------------------------------------------------------------- 출력: TTS
def synthesize_speech(text: str, speaker: str = 'nara', speed: int = 0,
                      save_to: str | Path | None = None) -> bytes:
    """CLOVA Voice로 텍스트를 읽은 mp3 를 돌려줍니다.

    speaker: nara(여, 차분), jinho(남), nminseo, nshasha 등 CLOVA Voice 목소리 ID
    speed:   -5(빠름) ~ 5(느림), 0 보통
    save_to: 경로를 주면 파일로도 저장합니다.
    """
    text = text.strip()
    if not text:
        raise ValueError('읽을 텍스트가 비어 있습니다.')
    headers = {
        'X-NCP-APIGW-API-KEY-ID': _env('CLOVA_VOICE_CLIENT_ID'),
        'X-NCP-APIGW-API-KEY': _env('CLOVA_VOICE_CLIENT_SECRET'),
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    audio = b''
    for chunk in _split_for_tts(text):
        data = {'speaker': speaker, 'speed': speed, 'volume': 0, 'format': 'mp3', 'text': chunk}
        res = requests.post(VOICE_URL, headers=headers, data=data, timeout=30)
        if res.status_code != 200:
            raise RuntimeError(f'CLOVA Voice {res.status_code}: {res.text[:300]}')
        audio += res.content          # mp3 는 프레임 단위라 이어 붙여도 재생됩니다

    if save_to:
        Path(save_to).write_bytes(audio)
    return audio


def _split_for_tts(text: str, limit: int = TTS_MAX_CHARS) -> list[str]:
    """긴 텍스트를 문장 경계에서 limit 글자 이하 조각으로 나눕니다."""
    if len(text) <= limit:
        return [text]
    sentences = re.split(r'(?<=[.!?。])\s+|\n+', text)
    chunks, current = [], ''
    for s in filter(None, (s.strip() for s in sentences)):
        while len(s) > limit:                       # 한 문장이 너무 길면 강제로 자름
            chunks.append(s[:limit])
            s = s[limit:]
        if len(current) + len(s) + 1 > limit:
            chunks.append(current)
            current = s
        else:
            current = f'{current} {s}'.strip()
    if current:
        chunks.append(current)
    return chunks
