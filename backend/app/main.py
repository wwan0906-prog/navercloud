"""민원 작성 가이드 백엔드 (FastAPI)

실행:  uvicorn app.main:app --host 0.0.0.0 --port 8000      (backend 폴더에서)
문서:  http://<서버IP>:8000/docs

프론트엔드(minwon-app/App.js) 약속안에 맞춘 API:
    POST /api/analyze   multipart: complaint_text + files(문서 사진 최대 5장)
      → { main_category, field_checks[], guide_message, official_channel, ... }
"""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from . import ai_client, clova_io, db, guide, rules

AUDIO_DIR = Path(__file__).resolve().parent.parent / 'data' / 'audio'
MAX_IMAGES = 5                     # 프론트엔드 MAX_IMAGES 와 같게


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()                      # 서버 시작 때 guide_seed.json → SQLite 재적재
    yield


app = FastAPI(title='민원 작성 가이드 백엔드', version='0.2.0', lifespan=lifespan)

# 앱(Expo 웹/모바일)이 다른 주소에서 호출할 수 있게 허용 (교육용이라 전체 허용)
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

api = APIRouter(prefix='/api')


class TTSRequest(BaseModel):
    text: str
    speaker: str = 'nara'
    speed: int = Field(0, ge=-5, le=5)


# ---------------------------------------------------------------- 상태 확인
@api.get('/health')
def health():
    return {'status': 'ok', 'ai_mode': ai_client.mode(),
            'categories': [c['id'] for c in db.list_categories()]}


# ---------------------------------------------------------------- 분석 (메인)
@api.post('/analyze')
def analyze(complaint_text: str = Form(''), files: Optional[List[UploadFile]] = File(None)):
    """민원 텍스트 + 문서 사진 → OCR → 분류 → 정보 추출 → 판정 → 안내문. 결과는 DB 에 저장됩니다.
    (sync 함수로 둔 이유: OCR·HCX 호출이 블로킹이라 FastAPI 가 스레드에서 돌리게 하려고)"""
    files = [f for f in (files or []) if f is not None and f.filename]
    if len(files) > MAX_IMAGES:
        raise HTTPException(400, f'사진은 최대 {MAX_IMAGES}장까지 보낼 수 있습니다.')

    # 1. 문서 사진 OCR (한 장이 실패해도 나머지는 계속)
    ocr_texts, warnings = [], []
    for i, f in enumerate(files, 1):
        try:
            ocr_texts.append(clova_io.extract_text(f.file.read(), f.filename))
        except (ValueError, RuntimeError) as e:
            warnings.append(f'사진 {i}({f.filename}) 글자 인식 실패: {e}')

    # 2. 분석할 텍스트 = 입력 텍스트 + 사진에서 읽은 글자
    parts = [complaint_text.strip()] + [f'[첨부 문서 {i}]\n{t}' for i, t in enumerate(ocr_texts, 1) if t]
    text = '\n\n'.join(p for p in parts if p)
    if not text:
        detail = '민원 내용을 입력하거나 글자가 있는 문서 사진을 첨부해 주세요.'
        raise HTTPException(400, ' '.join([detail] + warnings))

    # 3. AI 분류 · 추출 (2번 팀원 담당, 지금은 mock)
    try:
        cls = ai_client.classify(text)
        cls['category'] = ai_client.normalize_category(
            cls.get('category'), [c['id'] for c in db.list_categories()])
        category = db.get_category(cls['category'])
        extracted = ai_client.extract(text, category) if category and category['fields'] else {}
    except ai_client.AINotReady as e:
        raise HTTPException(503, str(e))
    except Exception as e:                       # HCX 호출 실패 등
        raise HTTPException(502, f'AI 호출 실패: {e}')

    # 4. 판정 · 안내문 · 접수 채널
    checks = rules.check_fields(category['fields'] if category else [],
                                extracted.get('fields'), extracted.get('not_applicable'))
    complete = bool(checks) and rules.is_complete(checks)
    message = extracted.get('guide_message') or guide.compose_message(category, cls['category'], checks, complete)
    channel = (category or {}).get('official_channel') or db.default_channel()
    category_name = category['name'] if category else cls['category']

    result = {
        # ---- 프론트엔드 약속안 필드
        'main_category': cls['category'],
        'field_checks': [{k: c[k] for k in ('key', 'label', 'status', 'evidence', 'suggestion')}
                         for c in checks],
        'guide_message': message,
        'official_channel': channel,
        # ---- 추가 정보 (프론트엔드에서 안 써도 됨)
        'category_name': category_name,
        'confidence': cls.get('confidence'),
        'has_guide_data': bool(checks),
        'is_complete': complete,
        'ai_mode': ai_client.mode(),
        'complaint_text': complaint_text.strip(),
        'ocr_texts': ocr_texts,
        'warnings': warnings,
        'guide_text': guide.compose_speech(category_name, message, channel),
    }
    result['id'], result['created_at'] = db.save_complaint(text, len(files), result)
    return result


# ---------------------------------------------------------------- 기록 조회
@api.get('/complaints')
def complaints(limit: int = Query(20, ge=1, le=100)):
    """최근 분석 기록 목록 (최신순)"""
    return db.list_complaints(limit)


@api.get('/complaints/{complaint_id}')
def complaint(complaint_id: int):
    """분석 결과 하나 (/api/analyze 응답과 같은 형식)"""
    result = db.get_complaint(complaint_id)
    if result is None:
        raise HTTPException(404, '해당 기록이 없습니다.')
    return result


# ---------------------------------------------------------------- 읽어주기 (TTS 옵션)
@api.get('/complaints/{complaint_id}/audio')
def complaint_audio(complaint_id: int):
    """안내문을 읽어주는 mp3. 앱에서 이 주소를 오디오 URI 로 바로 쓰면 됩니다.
    한 번 만든 음성은 저장해 두고 재사용합니다 (CLOVA Voice 사용량 절약)."""
    result = db.get_complaint(complaint_id)
    if result is None:
        raise HTTPException(404, '해당 기록이 없습니다.')
    path = AUDIO_DIR / f'{complaint_id}.mp3'
    if not path.exists():
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        try:
            clova_io.synthesize_speech(result['guide_text'], save_to=path)
        except RuntimeError as e:
            raise HTTPException(502, str(e))
    return FileResponse(path, media_type='audio/mpeg')


@api.post('/tts', response_class=Response)
def tts(req: TTSRequest):
    """임의 텍스트 → mp3 (목소리·속도를 바꿔 보고 싶을 때)"""
    try:
        audio = clova_io.synthesize_speech(req.text, req.speaker, req.speed)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    return Response(audio, media_type='audio/mpeg')


# ---------------------------------------------------------------- 가이드 데이터
@api.get('/categories')
def categories():
    """DB 에 들어 있는 18개 대분류 · 필수 정보 항목 · 접수 채널 전체"""
    return db.list_categories()


app.include_router(api)
