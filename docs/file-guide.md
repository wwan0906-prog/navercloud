# 레포 파일 안내 — 뭐가 어디 있고, 누가 언제 보나

> 처음 레포를 받은 팀원용. 각 파일이 **무슨 역할**이고 **내가 건드릴 일이 있는지**만 적었습니다.

## 한눈에

```
minwon-auto-guide/
├─ README.md          프로젝트 소개 + 실행법 + 앱에서 호출하는 법  ← 제일 먼저 읽기
├─ .env.example       키 이름 목록 (복사해서 .env 만들고 값 채우기)
├─ .gitignore         올리면 안 되는 것 목록 (키·데이터·pem)
├─ backend/           서버. 실제로 돌아가는 코드와 설정 JSON
├─ ml/                모델 학습·평가 스크립트와 결과
├─ docs/              기술문서, 발표 자료
└─ app/               Expo 앱 (진완, 작성 중)
```

---

## backend/ — 서버 (돌아가는 코드)

### 실행 파일

| 파일 | 역할 | 누가 |
|---|---|---|
| `api.py` | **서버 본체.** `uvicorn api:app` 으로 띄움. `/input` `/analyze` `/tts` `/guide` `/health` 다섯 개 엔드포인트 | 진완(앱 연결), 전원(테스트) |
| `analyze.py` | **분석 파이프라인.** 민원 → 튜닝 모델 분류 → 세부 유형 → 필수정보 판정 → 접수처 → 안내문. `/analyze` 와 `/guide` 가 이걸 부름 | 프롬프트 담당 |
| `core.py` | **OCR·TTS.** 사진→글자(CLOVA OCR), 안내문→mp3(CLOVA Voice). `/input` `/tts` 가 이걸 부름 | 최동훈 |
| `api_io.py` | core.py 만 띄우는 **이전 버전** 서버. 지금은 `api.py` 가 통합본이라 안 써도 됨 | — |
| `run_samples.py` | `samples.txt` 의 민원을 전부 돌려서 표로 저장하는 테스트 도구 | 프롬프트 담당 |
| `requirements.txt` | `pip install -r requirements.txt` | 전원 |

### 설정·데이터 JSON (코드가 읽는 파일 — 내용 바꾸면 동작이 바뀜)

| 파일 | 내용 | 바꿀 일 |
|---|---|---|
| `guide_db.json` | **접수 채널 DB.** 안전신문고·국민신문고·110·정부24·환경신문고·위택스·복지로·창원시 민원콜센터의 주소·전화·이용법·출처·확인일. 18개 세부 유형마다 신고용/문의용 채널 연결 | 전화번호·링크 바뀌면. 다른 지역으로 바꾸면 `city_hall` 수정 |
| `required_fields_18.json` | **필수정보 기준표.** 18개 유형마다 "이 민원엔 이런 정보가 있어야 한다"(항목·판정 기준·조건). 판정 프롬프트가 이걸 그대로 씀 | 판정이 이상하면 여기 문구 수정 |
| `mapping.json` | 8개 서비스 분야 ↔ 원본 18개 유형 연결표. 예: 환경·위생 = 환경미화+위생+상하수도 | 거의 없음 (바꾸면 튜닝 다시 해야 함) |
| `system_prompt.txt` | 분류 모델에 주는 지시문. 튜닝 때 쓴 것과 **글자 하나까지 같아야** 함 | 절대 수정 금지 |
| `fewshot_subcategory.json` | 세부 유형 프롬프트에 넣는 예문 (유형별 2~3개) | 세부 유형이 자꾸 틀리면 예문 교체 |
| `fewshot_entities.json` | 위치·날짜·시간 개체명 예문. 지금은 참고용(코드에서 직접 안 씀) | — |
| `department_map.json` | 세부 유형 → 창원시 담당 부서 상위 3개 (AI허브 데이터에서 집계). 참고용 | — |
| `samples.txt` | 테스트용 민원 60개 | 테스트 문장 추가할 때 |

### 없는 파일 (일부러 안 올림)

| 파일 | 왜 없나 | 어떻게 받나 |
|---|---|---|
| `.env` | API 키. 깃에 올리면 안 됨 | `.env.example` 복사해서 각자 키 채우기. 서버엔 이미 있음 |

---

## ml/ — 모델 학습·평가

### 스크립트

| 파일 | 역할 | 언제 쓰나 |
|---|---|---|
| `prepare_data.py` | AI허브 원본 → `train.csv`(튜닝용 3,200) + `test.jsonl`(평가용 400) + few-shot JSON + 통계 | 데이터 다시 뽑을 때 (분야 바꾸거나 건수 늘릴 때) |
| `tuning.py` | CLOVA Studio 튜닝 학습 생성 API 호출. 키는 `.env` 에서 읽음 | v2 튜닝할 때 |
| `eval_classifier.py` | 튜닝 전/후 모델에 같은 test 400건을 풀게 해서 정확도 측정. `--compare` 로 비교표 생성 | 모델 바꿀 때마다 |

### results/ — 결과 (발표 재료)

| 파일 | 내용 |
|---|---|
| `compare.md` | **튜닝 전후 비교표.** 지시만 49.8% / few-shot 56.8% / 튜닝 74.5%, 분야별 정확도 ← 발표 핵심 |
| `base_summary.md` | 튜닝 전(HCX-003) 상세: 분야별 정확도, 자주 틀린 조합, 틀린 예시 |
| `fewshot8_summary.md` | 예시 8개 넣은 버전 상세 |
| `tuned_summary.md` | 튜닝 모델 상세 |
| `samples_결과.md` | 샘플 민원 60개를 파이프라인에 넣은 결과 표 (분야·누락·불충분·채널·소요 시간) |
| `stats.md` | 학습 데이터 통계: 분야별 원문 건수, 학습/평가 건수 ← "사용 데이터셋과 데이터 수" 슬라이드 |
| `raw_stats_full.json` | AI허브 원본 전체 집계 (분야·하위분류·개체명·부서·술어 분포) |

### 없는 파일 (일부러 안 올림)

| 파일 | 왜 없나 | 어떻게 받나 |
|---|---|---|
| `train.csv`, `test.jsonl` | AI허브 데이터 가공본 → **재배포 금지** | AI허브에서 원본 받아 `prepare_data.py` 실행. 또는 팀 드라이브에서 (레포 밖) |
| `results/*.jsonl` | 모델 응답 원본 로그 (크고 md에 요약됨) | 서버 `~/team_proj/results/` 에 있음 |

---

## docs/

| 파일 | 내용 |
|---|---|
| `기술문서.md` | 평가 기준의 기술문서: 개요·역할·아키텍처·흐름·스펙·API·데이터·History(시행착오 표)·리스크·일정·체크리스트 |
| `파일안내.md` | 이 문서 |

---

## 자주 하는 작업 → 어느 파일

| 하고 싶은 것 | 파일 |
|---|---|
| 서버 띄우기 | `backend/api.py` (`uvicorn api:app --host 0.0.0.0 --port 8000`) |
| 민원 하나 넣어보기 | `cd backend && python3 analyze.py "민원 문장"` |
| 앱에서 뭘 보내고 받는지 | `README.md` "앱에서 호출하는 법" 표 |
| 전화번호·링크 고치기 | `backend/guide_db.json` |
| 판정이 이상할 때 | `backend/required_fields_18.json` (기준) 또는 `backend/analyze.py` 의 `FIELDS_SYSTEM` (프롬프트) |
| 세부 유형이 이상할 때 | `backend/analyze.py` 의 `SUBTYPE_DESC` (유형 설명) |
| 튜닝 모델 바꾸기 | `.env` 의 `TUNED_TASK_ID` |
| 발표 숫자 찾기 | `ml/results/compare.md`, `stats.md`, `docs/기술문서.md` History |

## 작업 흐름 (중요)

- **코드 수정은 PC에서** → `git push` → **서버에서 `git pull`**
- **서버에서 생긴 결과물**(results 등)은 VS Code 우클릭 → 다운로드 → PC에서 commit
- `.env`, `*.pem`, `train.csv`, `test.jsonl` 은 절대 커밋하지 않기 (`.gitignore` 가 막아주지만 확인)
