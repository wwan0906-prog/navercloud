# 민원 작성 가이드 백엔드

FastAPI + SQLite. 앱(`minwon-app`, React Native + Expo)이 부르는 API 서버입니다.
앱에서 호출하는 방법은 [API_명세.md](API_명세.md)를 보세요.

## 아직 없음 / 미정

| 항목 | 담당 | 상태 | 연결 위치 |
|---|---|---|---|
| HCX 튜닝 모델 분류 (18개 대분류) | 2번 팀원 | **아직 없음** | `app/ai_client.py` → `_real_classify()` |
| HCX Prompt 정보 추출 | 2번 팀원 | **아직 없음** | `app/ai_client.py` → `_real_extract()` |
| 분야별 공식 접수 채널 | 팀 | **미정** (지금은 전부 국민신문고) | `data/guide_seed.json` → `categories[].official_channel` |

AI가 연결되기 전까지는 `.env`의 `AI_MODE=mock`으로 **키워드 기반 가짜 응답**을 씁니다. 나머지 흐름(OCR → 판정 → 안내문 → 저장 → 읽어주기)은 실제로 동작합니다.

## 구조

```
backend/
├── app/
│   ├── main.py        API (/api/analyze 등): 입력 검증 · 호출 · 결과 통합
│   ├── clova_io.py    CLOVA OCR(사진 → 텍스트), CLOVA Voice(안내문 → 음성)
│   ├── ai_client.py   HCX 연결 지점: 2번 팀원 담당 (아직 없음, 지금은 mock)
│   ├── rules.py       Python Rule Engine: sufficient / insufficient / missing / not_applicable
│   ├── guide.py       안내문(guide_message), 읽어주기 문장(guide_text) 조합
│   └── db.py          SQLite: 가이드 DB 조회, 분석 기록 저장
├── data/
│   ├── guide_seed.json   가이드 데이터 원본 (여기만 고치면 됨)
│   ├── category_requirements.json  팀 기준 파일: 18개 분야 필수 정보 (seed 의 key·label·check·when 원본)
│   ├── minwon.db         서버 시작 시 자동 생성
│   └── audio/            읽어주기 mp3 캐시 (자동 생성)
├── tests/test_api.py
├── API_명세.md            프론트엔드용
├── .env.example
└── requirements.txt
```

## 배포 서버

| 항목 | 값 |
|---|---|
| 주소 | `http://211.233.204.198:8000` (API 테스트 화면: `/docs`) |
| 서버 | NCP `ai-001`, 서버 안의 경로는 `/root/minwon-backend` |
| 실행 방식 | systemd 서비스 `minwon-backend`. 재부팅되거나 프로세스가 죽어도 자동으로 다시 켜짐 |
| ACG | 인바운드 TCP 8000은 전체(`0.0.0.0/0`), SSH(22)는 백엔드 담당 IP만 |

repo가 비공개라 서버에서 `git pull`은 안 됩니다. 백엔드 담당 PC에서 폴더를 복사해서 배포합니다 (SSH 접속 권한 필요).

```bash
# 다시 배포 (repo 루트에서)
rsync -az --exclude .venv --exclude __pycache__ --exclude data/minwon.db --exclude data/audio \
  backend/ root@211.233.204.198:/root/minwon-backend/
ssh root@211.233.204.198 'systemctl restart minwon-backend'

# 패키지가 바뀌었을 때
ssh root@211.233.204.198 'cd /root/minwon-backend && .venv/bin/pip install -q -r requirements.txt && systemctl restart minwon-backend'

# 상태 · 로그
ssh root@211.233.204.198 'systemctl status minwon-backend --no-pager'
ssh root@211.233.204.198 'journalctl -u minwon-backend -n 50 --no-pager'
```

- 서버의 `.env`(CLOVA 키, `AI_MODE`)는 위 rsync로 로컬 `backend/.env`가 함께 복사됩니다. `AI_MODE`를 바꾼 뒤에는 다시 배포하세요.
- 분석 기록 DB(`data/minwon.db`)와 음성 캐시(`data/audio/`)는 서버에만 있고, 배포할 때 덮어쓰지 않습니다.

## 로컬 실행

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # 키 채우기
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- 브라우저에서 `http://localhost:8000/docs`를 열면 API를 직접 눌러볼 수 있습니다.
- 테스트: `python -m pytest -q`. CLOVA는 가짜 함수로 대체하므로 API 사용량을 쓰지 않습니다.

## 분석 흐름 (`POST /api/analyze`)

```
complaint_text + files(사진 ≤ 5장)
  → clova_io.extract_text()     사진마다 OCR (실패한 사진은 warnings 에 기록하고 계속)
  → 텍스트 + OCR 결과 합치기
  → ai_client.classify()        18개 대분류 중 하나      (2번 팀원: 아직 없음)
  → db.get_category()           그 분야의 필수 정보 항목 · 접수 채널
  → ai_client.extract()         항목별 원문 구절           (2번 팀원: 아직 없음)
  → rules.check_fields()        항목별 sufficient / insufficient / missing / not_applicable
  → guide.compose_message()     맞춤형 보완 안내문
  → db.save_complaint()         기록 저장 → id
```

## 2번 팀원: AI 연결 방법

`app/ai_client.py`의 두 함수만 채우고 `.env`를 `AI_MODE=real`로 바꾸면 됩니다.

```python
def _real_classify(text: str) -> dict:
    # HCX 튜닝 모델 호출 (아래 '튜닝 모델 호출' 참고)
    return {"category": "교통", "confidence": 0.93}
    #        ↑ guide_seed.json 의 categories[].id (AI Hub 대분류 18개) 중 하나, 글자 그대로

def _real_extract(text: str, category: dict) -> dict:
    # category["fields"] 에 추출할 항목 목록이 있음: [{"key", "label", "check", "when", "hint", "example"}, ...]
    # → 프롬프트에 그대로 넣어서 각 key 에 해당하는 원문 구절을 뽑게 하면 됨
    return {
        "fields": {"traffic_target": "불법 주정차 차량", "location_or_route": "상가 앞", "request": None},
        "not_applicable": [],          # 선택: when 조건에 해당하지 않는 항목 key (아래 참고)
        "guide_message": None,         # 선택: LLM 이 안내문을 직접 만들면 여기에 (없으면 백엔드가 만듦)
    }
```

- 값은 **원문 구절 그대로** 주세요. 앱에 `원문: "…"`으로 표시됩니다. 원문에 없으면 `None`.
- 원문에 없는 값을 추정해서 만들지 마세요 (기준 파일 `rules.evidence`).
- `when`이 있는 항목(조건부 필수)은 이 민원이 그 조건에 해당하지 않으면 `not_applicable`에 key를 넣어 주세요. 예: 교통 `location_or_route`의 when은 "특정 장소·노선·운행을 대상으로 신고하는 경우"라서, 교통 제도 일반 문의면 해당 없음.
- `when`이 없는 항목은 항상 필수라서 `not_applicable`에 넣어도 무시됩니다.
- 충족·불충분·누락 판정은 백엔드(`rules.py`)가 합니다.
- HCX 키는 `.env`에 추가하고 `os.environ`으로 읽어주세요.

### 튜닝 모델 호출

분류는 CLOVA Studio에서 튜닝한 HCX 모델을 씁니다. `.env`에 두 값을 넣어 주세요 (`.env.example` 참고).

```
CLOVASTUDIO_API_KEY=nv-...        # CLOVA Studio API 키
HCX_TUNING_TASK_ID=...            # 튜닝 작업 ID (플레이그라운드 '코드 보기'의 URL에 들어 있음)
```

```python
url = f"https://clovastudio.stream.ntruss.com/v2/tasks/{os.environ['HCX_TUNING_TASK_ID']}/chat-completions"
headers = {"Authorization": f"Bearer {os.environ['CLOVASTUDIO_API_KEY']}", "Content-Type": "application/json"}
body = {"messages": [{"role": "system", "content": "..."}, {"role": "user", "content": text}]}
```

- 튜닝 모델이 `"교통"`, `교통.`, `문화·체육·관광`, `분류: 세무`처럼 라벨에 따옴표·공백·가운뎃점을 섞어 내도, 백엔드가 `normalize_category()`로 18개 라벨 중 하나에 맞춥니다. 맞추지 못하면 그대로 두고, 이 경우 "안내 기준 없음"으로 응답합니다.
- 튜닝할 때 학습 데이터의 정답 라벨은 **`guide_seed.json`의 `categories[].id`와 같은 글자**(AI Hub 대분류 그대로: `문화_체육_관광`, `농업_축산` 등)로 맞추는 게 가장 안전합니다.
- v2 주소가 404면 `/v1/tasks/...`로 시도해 보세요 (수업 lab6의 `compare_tuning.py`도 v2 → v1 순서로 시도합니다).

## 가이드 데이터 수정 (`data/guide_seed.json`)

`guide_seed.json`이 원본입니다. 서버를 시작할 때마다 SQLite에 다시 적재하므로, **JSON만 고치고 서버를 재시작**하면 됩니다. 분석 기록은 재적재해도 유지됩니다.

18개 분야의 필수 정보 항목(`key`·`label`·`check`·`when`)은 팀 기준 파일 `data/category_requirements.json`(민원 18개 카테고리 공식요건 검수, schema 1.0.0)을 그대로 옮긴 것입니다. 기준 파일이 바뀌면 seed도 같이 고쳐야 하고, 둘이 다르면 `test_seed_matches_requirements` 테스트가 실패합니다. `min_length`·`pattern`·`hint`·`example`은 기준 파일에 없어서 백엔드가 덧붙인 값입니다.

```jsonc
{
  "default_channel": { "agency": "국민신문고", "url": "https://www.epeople.go.kr", "phone": "110" },
  "categories": [{
    "id": "교통",                        // AI Hub 대분류 라벨 그대로
    "name": "교통",                      // 표시 이름 (생략하면 id)
    "official_channel": { "agency": "...", "url": "...", "phone": "..." },  // 없으면 default_channel
    "fields": [{
      "key": "location_or_route",       // 추출 결과의 키
      "label": "발생 위치·노선",
      "required": true,
      "when": "특정 장소·노선·운행을 대상으로 신고하는 경우",  // 있으면 조건부 필수 (기준 파일)
      "check": "교차로·정류장·노선 등 ... 식별 가능",          // 충족 판정 기준 (기준 파일, AI 프롬프트용)
      "min_length": 2,                  // 이보다 짧으면 불충분
      "pattern": "\\d|\\S(아파트|...)",  // 정규식. 안 맞으면 불충분 (선택)
      "hint": "상가 이름이나 도로명 주소, ...",   // → suggestion
      "example": "OO마트 앞 도로"
    }]
  }]
}
```

## 판정 규칙 (`app/rules.py`)

| 상태 | 조건 |
|---|---|
| `not_applicable` 해당 없음 | `when`이 있는 항목인데 AI가 `not_applicable`로 표시함 (`when`이 없는 항목은 표시해도 무시) |
| `missing` 누락 | 값이 없음 |
| `insufficient` 불충분 | **AI가 가져온 구절이 원문에 없음**(지어낸 내용) / **AI가 불충분으로 판정** / "근처", "모름" 같은 모호한 표현만 있음 / `min_length`보다 짧음 / `pattern`에 안 맞음 |
| `sufficient` 충족 | 위에 해당하지 않음 |

**원문 확인**: AI가 가져온 구절에 원문에 없는 글자가 5자 이상 연달아 있으면 지어낸 것으로 보고 불충분 처리하며, 화면에 `원문: "…"`으로 표시하지 않습니다 (`rules.UNGROUNDED_RUN`). 실제 HCX 응답에서 "불법 주정차 차량 **이동 조치 요청**"(원문에 요청이 없는데 만든 문장)은 걸리고, "수거 지연"처럼 짧게 요약한 것은 통과합니다. 다만 "빨리 고쳐주세요" → "빠른 수리 요청"처럼 **뜻은 같은데 다르게 바꿔 말한 것도 걸립니다.** 프롬프트에서 "value 는 원문을 그대로 복사"를 더 강하게 지시하면 줄어듭니다.

예: 발생 위치 `pattern`은 숫자(번지·도로명 번호)나 "OO아파트", "OO사거리" 같은 건물·지점 이름을 요구합니다. 그래서 "집 앞 골목", "상가 앞"은 불충분, "세종대로 209", "OO아파트 정문 앞"은 충족입니다.

## DB 테이블

| 테이블 | 내용 |
|---|---|
| `categories` | 18개 대분류 |
| `fields` | 분야별 필수 정보 항목과 판정 기준 |
| `channels` | 공식 접수 채널 (`category_id`가 NULL이면 기본 채널) |
| `complaints` | 분석 기록 (분석 텍스트, 사진 수, 결과 JSON) |

※ `complaints`에는 민원 원문과 OCR 결과가 그대로 저장되므로 이름·주소 같은 개인정보가 들어갈 수 있습니다.
