"""통합 FastAPI 서버 — 앱이 부르는 엔드포인트 4개

    uvicorn api:app --host 0.0.0.0 --port 8000
    http://<서버IP>:8000/docs   ← 브라우저에서 바로 테스트

    POST /input    텍스트 or 사진 → 민원 원문           (core.py, 최동훈)
    POST /analyze  민원 원문 → 분류·판정·접수처·안내문   (analyze.py)
    POST /tts      안내문 → mp3                          (core.py, 최동훈)
    POST /guide    사진/텍스트 → 분석 → (선택) mp3 까지 한 번에  (앱에서 호출 1번으로 끝내고 싶을 때)
    POST /api/analyze  minwon-app/App.js 가 쓰는 형식 ({complaint_text} → main_category/validation/official_channel ...)
    GET  /health   서버 살아있는지 + 설정 확인

키는 같은 폴더 .env 에서 읽습니다 (.env.example 참고).
"""
from __future__ import annotations

import base64
import time
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

import core          # OCR·TTS (.env 를 먼저 읽음)
import analyze       # 분류·판정·안내

app = FastAPI(title="민원 자동분류 & 작성 가이드", version="0.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ---------------------------------------------------------------- 요청 모델
class AnalyzeIn(BaseModel):
    text: str
    use_tuned: bool = True          # False 면 튜닝 모델 대신 HCX-003 프롬프트 분류 (장애 시 백업)


class TTSIn(BaseModel):
    text: str
    speaker: str = "nara"
    speed: int = 0


# ---------------------------------------------------------------- 공통 에러 변환
def _run(fn, *a, **k):
    try:
        return fn(*a, **k)
    except ValueError as e:          # 입력 문제
        raise HTTPException(400, str(e))
    except RuntimeError as e:        # CLOVA 호출 실패 (키·한도·네트워크)
        raise HTTPException(502, str(e))


# ---------------------------------------------------------------- 엔드포인트
@app.get("/health")
def health():
    return {"ok": True, "tuned_task": analyze.TUNED_TASK_ID, "base_model": analyze.BASE_MODEL,
            "labels": analyze.LABELS, "guide_db_version": analyze.GUIDE.get("_meta", {}).get("version")}


@app.post("/input")
async def input_(text: Optional[str] = Form(None), image: Optional[UploadFile] = File(None)):
    """텍스트 또는 사진 → {"text": 민원 원문, "source": "text"|"ocr"}"""
    if image is not None:
        return _run(core.normalize_input, text, await image.read(), image.filename)
    return _run(core.normalize_input, text)


@app.post("/analyze")
def analyze_(req: AnalyzeIn):
    """민원 원문 → category, subtype, intent, fields[], missing[], insufficient[], suggestions[], channels[], guide_text, emergency"""
    res = _run(analyze.analyze, req.text, req.use_tuned)
    if "error" in res:
        raise HTTPException(502, res["error"])
    return res


# ---------------------------------------------------------------- 앱(minwon-app/App.js) 호환 엔드포인트
class AppAnalyzeIn(BaseModel):
    complaint_text: str


def to_app_schema(res: dict) -> dict:
    """analyze() 결과 → App.js 가 기대하는 모양
    {main_category, sub_category, extracted_info, validation{status, missing_fields}, guide_message, official_channel{agency,url,phone}}"""
    if res.get("category") is None:                      # 너무 짧은 입력
        return {"main_category": "분류 불가", "sub_category": "-", "extracted_info": {},
                "validation": {"status": "불충분", "missing_fields": ["민원 내용(무엇이·어디서·언제)"]},
                "guide_message": res.get("guide_text", ""), "official_channel": {"agency": "국민콜 110", "url": "https://www.110.go.kr", "phone": "110"},
                "emergency": res.get("emergency")}
    fields = res.get("fields", [])
    extracted = {f["label"]: (f["value"] if f.get("value") else "미기재") for f in fields if f["status"] != "not_applicable"}
    missing = [f["label"] for f in fields if f["status"] == "missing"]
    insufficient = [f"{f['label']} (더 구체적으로)" for f in fields if f["status"] == "insufficient"]
    status = "충족" if not missing and not insufficient else ("불충분" if not missing else "누락")
    ch = res["channels"][0] if res.get("channels") else {"name": "국민신문고", "url": "https://www.epeople.go.kr", "phone": "110"}
    guide = " ".join(s for s in res.get("suggestions", []) if not s.startswith("팁:")) or res.get("guide_text", "")
    tips = [s[3:].strip() for s in res.get("suggestions", []) if s.startswith("팁:")]
    if tips:
        guide += " " + "팁: " + tips[0]
    if res.get("emergency"):
        guide = "⚠ " + res["emergency"]["note"] + " " + guide
    return {"main_category": res["category"], "sub_category": f"{res['subtype']} ({res.get('intent', '신고')})",
            "extracted_info": extracted,
            "validation": {"status": status, "missing_fields": missing + insufficient},
            "guide_message": guide,
            "official_channel": {"agency": ch["name"], "url": ch.get("url") or "", "phone": ch.get("phone") or "110"},
            "guide_text": res.get("guide_text", ""),      # TTS 용
            "emergency": res.get("emergency"),
            "_raw": {k: res[k] for k in ("category", "subtype", "intent", "fields", "channels") if k in res}}


@app.post("/api/analyze")
def api_analyze(req: AppAnalyzeIn):
    """App.js 용. 요청 {"complaint_text": "..."} → 앱 화면 형식 응답"""
    res = _run(analyze.analyze, req.complaint_text)
    if "error" in res:
        raise HTTPException(502, res["error"])
    return to_app_schema(res)


@app.post("/tts", response_class=Response)
def tts(req: TTSIn):
    """안내문 → mp3 바이너리 (audio/mpeg)"""
    audio = _run(core.synthesize_speech, req.text, req.speaker, req.speed)
    return Response(audio, media_type="audio/mpeg")


@app.post("/guide")
async def guide(text: Optional[str] = Form(None), image: Optional[UploadFile] = File(None),
                with_audio: bool = Form(False), speaker: str = Form("nara")):
    """한 번에: (사진→OCR) → 분석 → (선택) 음성.  multipart/form-data

    응답: /analyze 결과 + "input": {text, source} + (with_audio=true 면) "audio_base64": mp3 를 base64 로
    앱에서 호출 1번으로 끝내고 싶을 때 사용. 사진+음성이면 10초 넘을 수 있으니 로딩 표시 필수.
    """
    t0 = time.time()
    if image is not None:
        inp = _run(core.normalize_input, text, await image.read(), image.filename)
    else:
        inp = _run(core.normalize_input, text)
    res = _run(analyze.analyze, inp["text"])
    if "error" in res:
        raise HTTPException(502, res["error"])
    res["input"] = inp
    if with_audio and res.get("guide_text"):
        audio = _run(core.synthesize_speech, res["guide_text"], speaker, 0)
        res["audio_base64"] = base64.b64encode(audio).decode("ascii")
    res.setdefault("_debug", {})["total_sec"] = round(time.time() - t0, 1)
    return res
