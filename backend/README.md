# 민원 작성 가이드 백엔드

FastAPI + SQLite. 앱(`minwon-app`, React Native + Expo)이 부르는 API 서버입니다.
앱에서 호출하는 방법은 [API_명세.md](API_명세.md)를 보세요.

## 현재 상태 (2026-11-21)

| 항목 | 담당 | 상태 | 위치 |
|---|---|---|---|
| HCX 분류 (튜닝 모델 → 18개 대분류) | 2번 팀원 | ✅ 연결됨 | `app/hcx.py` → `classify()` |
| HCX 정보 추출 (항목별 원문 구절 · 판정 의견) | 2번 팀원 | ✅ 연결됨 | `app/hcx.py` → `extract()` |
| 분야별 공식 접수 채널 | 2번 팀원 | ✅ 18개 모두 (출처 · 확인일 기록) | `data/guide_seed.json` → `categories[].official_channel` |
| 사진 OCR · 음성 인식 · 읽어주기 | 백엔드 | ✅ 실제 동작 | `app/clova_io.py` |

배포 서버는 `AI_MODE=real`(실제 HCX 호출)로 동작합니다. `.env`의 `AI_MODE=mock`으로 바꾸면 HCX 대신 **키워드 기반 가짜 응답**을 쓰므로, HCX 사용량 없이 화면·흐름을 개발할 수 있습니다. 나머지 흐름(OCR → 판정 → 안내문 → 저장 → 읽어주기)은 두 모드 모두 같습니다.

## 구조

```
backend/
├── app/
│   ├── main.py        API (/api/analyze 등): 입력 검증 · 호출 · 결과 통합
│   ├── clova_io.py    CLOVA OCR(사진 → 텍스트), CLOVA Speech(음성 → 텍스트), CLOVA Voice(안내문 → 음성)
│   ├── ai_client.py   AI 호출 연결 지점: AI_MODE 에 따라 hcx.py(real) 또는 가짜 응답(mock)
│   ├── hcx.py         HCX 실제 호출 (2번 팀원): 분류 · 세부 대분류 · 정보 추출
│   ├── rules.py       Python Rule Engine: sufficient / insufficient / missing / not_applicable
│   ├── guide.py       안내문(guide_message), 읽어주기 문장(guide_text) 조합
│   └── db.py          SQLite: 가이드 DB 조회, 분석 기록 저장
├── data/
│   ├── guide_seed.json   가이드 데이터 원본 (여기만 고치면 됨)
│   ├── category_requirements.json  팀 기준 파일: 18개 분야 필수 정보 (seed 의 key·label·check·when 원본)
│   ├── hcx/              HCX 프롬프트 자료 (2번 팀원): 8개 분야 ↔ 18개 대분류 매핑, 튜닝 시스템 프롬프트, few-shot 예문
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
- 테스트: `python -m pytest -q` (53개). CLOVA·HCX는 가짜 함수로 대체하므로 API 사용량을 쓰지 않습니다.

## 분석 흐름 (`POST /api/analyze`)

```
complaint_text + files(사진 ≤ 5장)
  → clova_io.extract_text()     사진마다 OCR (실패한 사진은 warnings 에 기록하고 계속)
  → 텍스트 + OCR 결과 합치기
  → ai_client.classify()        18개 대분류 중 하나 + 신고/문의   (hcx.classify: HCX 1~2회)
  → normalize_category()        라벨을 18개 대분류 id 로 맞춤
  → db.get_category()           그 분야의 필수 정보 항목 · 접수 채널
  → ai_client.extract()         항목별 원문 구절 · AI 판정 의견   (hcx.extract: HCX 1회)
  → rules.check_fields()        항목별 sufficient / insufficient / missing / not_applicable
  → guide.compose_message()     맞춤형 보완 안내문
  → db.save_complaint()         기록 저장 → id
```

## AI 연결 (HCX, 2번 팀원 `app/hcx.py`)

`.env`에 아래 값을 넣고 `AI_MODE=real`이면 실제 HCX를 부릅니다 (`.env.example` 참고). 키가 없으면 분석 요청이 503으로 끝나니, 키 없이 개발할 때는 `AI_MODE=mock`으로 두세요.

```
CLOVASTUDIO_API_KEY=nv-...        # CLOVA Studio API 키
HCX_TUNING_TASK_ID=...            # 튜닝 작업 ID (비워 두면 hcx.py 의 기본값 사용)
AI_MODE=real
```

분석 한 번에 HCX를 최대 3번 부르고, 응답까지 4~10초 걸립니다.

| 단계 | 함수 | 모델 | 결과 |
|---|---|---|---|
| ① 분야 | `classify_service()` | HCX-003 LoRA 튜닝 모델 (`/v2/tasks/{taskId}/chat-completions`) | 8개 서비스 분야 중 하나 |
| ② 대분류 | `classify_subtype()` | HCX-003 + 프롬프트 | 그 분야에 속한 AI Hub 대분류(18개 중 1~4개) 하나 + 신고/문의. 분야에 대분류가 하나뿐이면 호출 안 함 |
| ③ 추출 | `extract()` | HCX-003 + 프롬프트 | 항목별 원문 구절(`fields`), 조건 해당 없음(`not_applicable`), AI가 본 불충분(`insufficient`) |

- 8개 분야 ↔ 18개 대분류 매핑은 `data/hcx/mapping.json`, 튜닝 때 쓴 시스템 프롬프트는 `data/hcx/system_prompt.txt`(글자 하나까지 같아야 함)입니다.
- ③의 프롬프트에는 분류된 분야의 `check`·`when`이 항목별로 들어갑니다. 문의 민원이면 위치·일시 같은 현장 항목은 `not_applicable`로 판정하게 지시합니다.
- HCX가 429·5xx를 내면 2·4·6초 간격으로 최대 3번 재시도하고, 그래도 실패하면 502입니다.
- 모델 출력에 따옴표·공백·가운뎃점이 섞여도(`"교통"`, `문화·체육·관광`, `분류: 세무`) 백엔드가 `normalize_category()`로 18개 라벨 중 하나에 맞춥니다. 못 맞추면 "안내 기준 없음" + 기본 채널로 응답합니다.
- **최종 판정은 HCX가 아니라 `rules.py`가 합니다.** HCX가 준 구절이 원문에 없으면 불충분으로 처리합니다 (아래 '판정 규칙').

`ai_client.py`는 연결 지점만 맡습니다. 다른 AI로 바꾸려면 `_real_classify(text)` → `{"category", "confidence"}`, `_real_extract(text, category)` → `{"fields", "not_applicable"?, "insufficient"?, "guide_message"?}` 형식만 지키면 됩니다. 값은 원문 구절 그대로, 원문에 없으면 `None`입니다.

## 가이드 데이터 수정 (`data/guide_seed.json`)

`guide_seed.json`이 원본입니다. 서버를 시작할 때마다 SQLite에 다시 적재하므로, **JSON만 고치고 서버를 재시작**하면 됩니다. 분석 기록은 재적재해도 유지됩니다.

접수 채널(`official_channel`)은 분야마다 하나씩, 신고용 1순위 채널 기준으로 들어 있습니다 (데모 지역 창원시, 2026-11-21 확인). `source`·`checked_at`은 근거 기록용이라 DB와 API 응답에는 들어가지 않고 기관명·주소·전화만 나갑니다. 지역을 바꾸려면 창원시 민원콜센터로 된 9개 분야만 고치면 됩니다.

18개 분야의 필수 정보 항목(`key`·`label`·`check`·`when`)은 팀 기준 파일 `data/category_requirements.json`(민원 18개 카테고리 공식요건 검수, schema 1.0.0)을 그대로 옮긴 것입니다. 기준 파일이 바뀌면 seed도 같이 고쳐야 하고, 둘이 다르면 `test_seed_matches_requirements` 테스트가 실패합니다. `min_length`·`pattern`·`hint`·`example`은 기준 파일에 없어서 백엔드가 덧붙인 값입니다.

```jsonc
{
  "default_channel": { "agency": "국민신문고", "url": "https://www.epeople.go.kr", "phone": "110" },
  "categories": [{
    "id": "교통",                        // AI Hub 대분류 라벨 그대로
    "name": "교통",                      // 표시 이름 (생략하면 id)
    "official_channel": { "agency": "안전신문고", "url": "https://www.safetyreport.go.kr", "phone": "110",
                          "source": "https://www.korea.kr/...", "checked_at": "2026-11-21" },  // 없으면 default_channel
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
