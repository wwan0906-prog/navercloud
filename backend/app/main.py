"""민원 작성 가이드 백엔드 (FastAPI)

실행:  uvicorn app.main:app --host 0.0.0.0 --port 8000      (backend 폴더에서)
문서:  http://<서버IP>:8000/docs

프론트엔드(minwon-app/App.js) 약속안에 맞춘 API:
    POST /api/analyze   multipart: complaint_text + lang + files(문서 사진 최대 5장)
      → { classification, answer_draft, field_checks[], guide_message, official_channel, ... }
    POST /api/submit    {complaint_id} → 접수번호
"""
import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from . import ai_client, assist, clova_io, db, guide, rules, translate

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


# ---------------------------------------------------------------- 입력 보조: 사진·음성 → 글자
@api.post('/ocr')
def ocr(image: UploadFile = File(...)):
    """문서 사진 한 장 → 글자 (CLOVA OCR). 앱의 recognizeImage()"""
    try:
        return {'text': clova_io.extract_text(image.file.read(), image.filename or 'image.jpg')}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))


@api.post('/stt')
def stt(audio: UploadFile = File(...), lang: str = Form('ko')):
    """녹음 파일(60초 이하, m4a 등) → 글자 (CLOVA Speech Recognition). 앱의 transcribeAudio()"""
    try:
        return {'text': clova_io.transcribe_audio(audio.file.read(), lang), 'lang': lang}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))


# ---------------------------------------------------------------- 분석 (메인)
MIN_TEXT_CHARS = 8                 # 이보다 짧으면 AI 가 아무 분야로나 분류해서 되묻습니다


@api.post('/analyze')
def analyze(complaint_text: str = Form(''), lang: str = Form('ko'),
            files: Optional[List[UploadFile]] = File(None)):
    """민원 텍스트(+ 문서 사진) → (번역) → 분류 → 정보 추출·판정 + 답변 초안·긴급도·요약 → (역번역). DB 에 저장.
    (sync 함수로 둔 이유: OCR·HCX 호출이 블로킹이라 FastAPI 가 스레드에서 돌리게 하려고)"""
    files = [f for f in (files or []) if f is not None and f.filename]
    if len(files) > MAX_IMAGES:
        raise HTTPException(400, f'사진은 최대 {MAX_IMAGES}장까지 보낼 수 있습니다.')
    if lang not in translate.SUPPORTED:
        raise HTTPException(400, f'지원하지 않는 언어입니다: {lang} (가능: {", ".join(sorted(translate.SUPPORTED))})')

    # 1. 문서 사진 OCR (한 장이 실패해도 나머지는 계속)
    ocr_texts, warnings = [], []
    for i, f in enumerate(files, 1):
        try:
            ocr_texts.append(clova_io.extract_text(f.file.read(), f.filename))
        except (ValueError, RuntimeError) as e:
            warnings.append(f'사진 {i}({f.filename}) 글자 인식 실패: {e}')

    # 2. 외국어면 한국어로 번역 (사진 OCR 글자는 한국어 문서로 보고 번역하지 않음)
    original = complaint_text.strip()
    translated_text = None
    if lang != 'ko' and original:
        try:
            translated_text = translate.translate(original, lang, 'ko')
        except (ValueError, RuntimeError) as e:
            raise HTTPException(502, f'번역 실패: {e}')
    korean = translated_text or original

    # 3. 분석할 텍스트 = (번역된) 입력 텍스트 + 사진에서 읽은 글자
    parts = [korean] + [f'[첨부 문서 {i}]\n{t}' for i, t in enumerate(ocr_texts, 1) if t]
    text = '\n\n'.join(p for p in parts if p)
    if not text:
        detail = '민원 내용을 입력하거나 글자가 있는 문서 사진을 첨부해 주세요.'
        raise HTTPException(400, ' '.join([detail] + warnings))
    if len(re.sub(r'\s', '', text)) < MIN_TEXT_CHARS:
        raise HTTPException(400, '내용이 너무 짧아요. 어디서, 무슨 일이 있는지 조금 더 자세히 적어 주세요.')

    # 4. AI: 분류 → (정보 추출 ∥ 답변 초안·긴급도·요약)  두 번째 단계는 동시에 호출
    try:
        cls = ai_client.classify(text)
        cls['category'] = ai_client.normalize_category(
            cls.get('category'), [c['id'] for c in db.list_categories()])
        category = db.get_category(cls['category'])
        category_name = category['name'] if category else cls['category']
        service = cls.get('service_category') or ai_client.service_of(cls['category'])
        fields = category['fields'] if category else []
        with ThreadPoolExecutor(max_workers=2) as pool:
            f_extract = pool.submit(ai_client.extract, text, category) if fields else None
            f_assist = pool.submit(assist.make, text, category_name, service, fields)
            extracted = f_extract.result() if f_extract else {}
            extra = f_assist.result()
    except ai_client.AINotReady as e:
        raise HTTPException(503, str(e))
    except Exception as e:                       # HCX 호출 실패 등
        raise HTTPException(502, f'AI 호출 실패: {e}')

    # 5. 판정 · 안내문 · 접수 채널
    checks = rules.check_fields(fields, extracted.get('fields'), extracted.get('not_applicable'),
                                extracted.get('insufficient'), source_text=text)
    complete = bool(checks) and rules.is_complete(checks)
    message = extracted.get('guide_message') or guide.compose_message(category, cls['category'], checks, complete)
    channel = (category or {}).get('official_channel') or db.default_channel()

    # 6. 외국어면 답변 초안을 그 언어로 역번역
    answer_translated = None
    if lang != 'ko':
        try:
            answer_translated = translate.translate(extra['answer_draft'], 'ko', lang)
        except (ValueError, RuntimeError) as e:
            warnings.append(f'답변 번역 실패: {e}')

    result = {
        # ---- 앱(minwon-app) 화면이 쓰는 필드
        'classification': {
            '분야': service,                     # 8개 서비스 분야 (튜닝 모델)
            '세부유형': category_name,            # 18개 유형 (표시 이름)
            '유형': extra['유형'],               # 신고 · 문의 · 건의 · 칭찬
            '긴급도': extra['긴급도'],            # 긴급 · 일반
            '요약': extra['요약'],
        },
        'translated_text': translated_text,      # 외국어 입력일 때 한국어 번역 (한국어면 null)
        'answer_draft': extra['answer_draft'],
        'answer_translated': answer_translated,  # 외국어 입력일 때 답변 역번역
        'consistency': None,                     # 규정 검사: 이번 범위에서 제외
        'main_category': cls['category'],
        'service_category': service,
        'field_checks': [{k: c[k] for k in ('key', 'label', 'status', 'evidence', 'suggestion')}
                         for c in checks],
        'guide_message': message,
        'official_channel': channel,
        # ---- 추가 정보
        'category_name': category_name,
        'confidence': cls.get('confidence'),
        'has_guide_data': bool(checks),
        'is_complete': complete,
        'ai_mode': ai_client.mode(),
        'lang': lang,
        'translation_engine': translate.engine() if lang != 'ko' else None,
        'complaint_text': original,
        'ocr_texts': ocr_texts,
        'warnings': warnings,
        'guide_text': guide.compose_speech(category_name, message, channel),
    }
    result['id'], result['created_at'] = db.save_complaint(text, len(files), result)
    return result


# ---------------------------------------------------------------- 접수
class SubmitRequest(BaseModel):
    complaint_id: int = Field(..., description='/api/analyze 응답의 id')


@api.post('/submit')
def submit(req: SubmitRequest):
    """분석 결과로 접수: 접수번호 발급 + 분야 배정. 긴급 민원은 자동 처리하지 않고 담당자 확인 대기.
    같은 분석 결과로 두 번 접수하면 처음 접수를 그대로 돌려줍니다."""
    result = db.get_complaint(req.complaint_id)
    if result is None:
        raise HTTPException(404, '해당 분석 기록이 없습니다. 다시 분석해 주세요.')
    cls = result.get('classification') or {}
    department = cls.get('분야') or result.get('service_category') or result.get('main_category')
    urgent = cls.get('긴급도') == '긴급'
    status = 'pending_review' if urgent else 'received'
    message = ('긴급 민원으로 분류되어 담당자가 확인한 뒤 처리합니다.' if urgent
               else '담당 분야로 배정되었습니다. 처리 결과는 접수번호로 확인할 수 있습니다.')
    return db.create_receipt(req.complaint_id, department, result.get('main_category'),
                             cls.get('긴급도'), status, message)


@api.get('/receipts/{receipt_no}')
def receipt(receipt_no: str):
    """접수번호로 접수 내용 확인"""
    r = db.get_receipt(receipt_no)
    if r is None:
        raise HTTPException(404, '해당 접수번호가 없습니다.')
    return r


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
