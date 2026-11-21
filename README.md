# 민원 자동분류 & 맞춤형 작성 가이드 (navercloud)

> 처음이면 [docs/file-guide.md](docs/file-guide.md) 부터 — 어떤 파일이 뭔지, 누가 언제 보는지

> 네이버클라우드 소버린AI 과정 조별 프로젝트 · 최종 발표 2026-11-28

시민이 민원을 자연어(또는 사진)로 적으면, 분야를 분류하고 **빠진 정보가 무엇인지** 알려주고, **공식 접수 채널(링크·전화)**을 안내하는 앱.

## 동작 흐름

```
텍스트 / 사진(OCR)
  → ① HCX 튜닝 모델: 8개 분야 분류
  → ② HCX 프롬프트: 세부 유형(18) + 신고/문의 판별
  → ③ HCX 프롬프트: 필수 정보 충족/불충분/누락 판정 (기준표 JSON)
  → ④ 가이드 DB(JSON): 접수 채널·전화번호 조회  ← LLM 미사용
  → ⑤ 안내문 조립 → CLOVA Voice(TTS)
```

- **LLM은 이해(①②③)만, 판정 기준과 접수처는 사람이 만든 JSON**에서 가져옵니다. 링크·전화번호에 환각이 없습니다.
- 긴급 키워드(화재·가스·폭행·실종 등)는 LLM 호출 전에 정규식으로 잡아 119/112/129를 먼저 안내합니다.

## 폴더

| 폴더 | 내용 | 담당 |
|---|---|---|
| `backend/` | FastAPI 서버 `api.py`: `/input`(OCR), `/analyze`(분류·판정·안내), `/tts`(음성), `/guide`(한 번에) | 진완(통합), 최동훈(입출력) |
| `minwon-app/` | React Native + Expo 앱 (`App.js`, `/api/analyze` 호출) | 진완 |
| `ml/` | 데이터 전처리, 튜닝 평가 스크립트, 결과 | 김찬결 |
| `docs/` | 기술문서, 파일 안내, 발표 자료 | 이상훈 |
| `src/` | 초기 실험 코드 (현재 비어 있음) | — |

## 실행 (backend)

```bash
cd backend
pip install -r requirements.txt
cp ../.env.example .env    # 키 채우기
uvicorn api:app --host 0.0.0.0 --port 8000
# http://<서버IP>:8000/docs 에서 테스트
# (api_io.py 는 입출력만 있는 이전 버전. api.py 가 통합본)
```

단독 테스트:
```bash
python3 analyze.py "집 앞 도로에 불법주차가 너무 많아요"
```

## 데이터 · 모델

- 학습 데이터: AI허브 「민원 업무 자동화 인공지능 언어 데이터」(dataSetSn=619). **데이터 파일은 재배포 금지라 레포에 없음** — 각자 AI허브에서 받아 `ml/prepare_data.py`로 변환.
- 튜닝: HCX-003 / LoRA / epochs 8 / lr 1e-4 / 3,200건 (8개 분야 × 400)
- 평가 (같은 test 400건): 베이스 49.8% → few-shot 8 56.8% → **튜닝 74.5%** (`ml/results/compare.md`)

## 8개 분야

교통·자동차 / 도로·안전시설 / 건축·토지 / 환경·위생 / 산림·농업 / 복지·보건 / 세무·행정 / 경제·문화
(원본 18개 유형과의 매핑: `backend/mapping.json`)

## 앱에서 호출하는 법 (요약)

| 할 일 | 호출 | 보내는 것 | 받는 것 |
|---|---|---|---|
| **앱(App.js)이 쓰는 것** | `POST /api/analyze` (JSON) | `{"complaint_text": "..."}` | `main_category, sub_category, extracted_info, validation{status, missing_fields}, guide_message, official_channel{agency,url,phone}, guide_text(TTS용), emergency` |
| 텍스트 민원 분석 (전체 필드) | `POST /analyze` (JSON) | `{"text": "..."}` | `category, subtype, intent, fields[], missing[], insufficient[], suggestions[], channels[], guide_text, emergency` |
| 사진 민원 | `POST /input` (multipart) → `/analyze` | `image` 파일 | `{text, source}` → 위와 같음 |
| 안내문 읽어주기 | `POST /tts` (JSON) | `{"text": guide_text}` | mp3 바이너리 |
| 전부 한 번에 | `POST /guide` (multipart) | `text` 또는 `image`, `with_audio=true` | 분석 결과 + `audio_base64` |

- `/analyze` 는 HCX 3회 호출로 **4~10초** 걸립니다. 로딩 표시 필수.
- `minwon-app/App.js` 의 `USE_MOCK = false`, `API_URL = 'http://<서버IP>:8000/api/analyze'` 로 바꾸면 바로 연동됨.
- 앱은 http 서버를 기본 차단하므로 Expo `app.json` 에 Android `usesCleartextTraffic`, iOS ATS 예외 필요.
- `fields[].status` 는 `sufficient | insufficient | missing | not_applicable`. 화면엔 O / △ / X / - 로.
- `emergency` 가 null 이 아니면 `{number, note}` — 맨 위에 빨간 배너로.
- `category` 가 null 이면 입력이 너무 짧은 것. `guide_text` 를 그대로 보여주면 됨.

## 주의

- `.env`, `*.pem`, API 키가 든 파일은 **절대 커밋하지 않습니다** (`.gitignore` 참고).
- `backend/guide_db.json`의 전화번호·링크는 공식 출처를 확인해 `source`, `checked_at`을 기록합니다.
