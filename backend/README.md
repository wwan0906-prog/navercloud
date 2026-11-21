# 민원 작성 가이드 백엔드

FastAPI + SQLite. 앱(`minwon-app`, React Native + Expo)이 부르는 API 서버입니다.
앱에서 호출하는 방법은 [API_명세.md](API_명세.md)를 보세요.

## 아직 없음 / 미정

| 항목 | 담당 | 상태 | 연결 위치 |
|---|---|---|---|
| HCX + RAG 분류 (18개 대분류) | 2번 팀원 | **아직 없음** | `app/ai_client.py` → `_real_classify()` |
| HCX Prompt 정보 추출 | 2번 팀원 | **아직 없음** | `app/ai_client.py` → `_real_extract()` |
| 분야별 필수 정보 항목 | 팀 | **미정** (18개 중 `안전건설`, `교통`만 예시) | `data/guide_seed.json` → `categories[].fields` |
| 분야별 공식 접수 채널 | 팀 | **미정** (지금은 전부 국민신문고) | `data/guide_seed.json` → `categories[].official_channel` |

AI가 연결되기 전까지는 `.env`의 `AI_MODE=mock`으로 **키워드 기반 가짜 응답**을 씁니다. 나머지 흐름(OCR → 판정 → 안내문 → 저장 → 읽어주기)은 실제로 동작합니다.

## 구조

```
backend/
├── app/
│   ├── main.py        API (/api/analyze 등): 입력 검증 · 호출 · 결과 통합
│   ├── clova_io.py    CLOVA OCR(사진 → 텍스트), CLOVA Voice(안내문 → 음성)
│   ├── ai_client.py   HCX + RAG 연결 지점: 2번 팀원 담당 (아직 없음, 지금은 mock)
│   ├── rules.py       Python Rule Engine: sufficient / insufficient / missing / not_applicable
│   ├── guide.py       안내문(guide_message), 읽어주기 문장(guide_text) 조합
│   └── db.py          SQLite: 가이드 DB 조회, 분석 기록 저장
├── data/
│   ├── guide_seed.json   가이드 데이터 원본 (여기만 고치면 됨)
│   ├── minwon.db         서버 시작 시 자동 생성
│   └── audio/            읽어주기 mp3 캐시 (자동 생성)
├── tests/test_api.py
├── API_명세.md            프론트엔드용
├── .env.example
└── requirements.txt
```

## 실행

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # 키 채우기
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- 브라우저에서 `http://<서버IP>:8000/docs`를 열면 API를 직접 눌러볼 수 있습니다.
- NCP 서버에 올릴 때는 **ACG에서 8000번 포트를 열어야** 합니다.
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
    # HCX + RAG 호출
    return {"category": "교통", "confidence": 0.93}
    #        ↑ guide_seed.json 의 categories[].id (AI Hub 대분류 18개) 중 하나, 글자 그대로

def _real_extract(text: str, category: dict) -> dict:
    # category["fields"] 에 추출할 항목 목록이 있음: [{"key", "label", "hint", "example"}, ...]
    # → 프롬프트에 그대로 넣어서 각 key 에 해당하는 원문 구절을 뽑게 하면 됨
    return {
        "fields": {"traffic_target": "불법 주정차 차량", "location_or_route": "상가 앞", "request": None},
        "not_applicable": [],          # 선택: 이 민원에 해당 없는 항목 key
        "guide_message": None,         # 선택: LLM 이 안내문을 직접 만들면 여기에 (없으면 백엔드가 만듦)
    }
```

- 값은 **원문 구절 그대로** 주세요. 앱에 `원문: "…"`으로 표시됩니다. 원문에 없으면 `None`.
- 충족·불충분·누락 판정은 백엔드(`rules.py`)가 합니다.
- HCX 키는 `.env`에 추가하고 `os.environ`으로 읽어주세요.

## 가이드 데이터 수정 (`data/guide_seed.json`)

`guide_seed.json`이 원본입니다. 서버를 시작할 때마다 SQLite에 다시 적재하므로, **JSON만 고치고 서버를 재시작**하면 됩니다. 분석 기록은 재적재해도 유지됩니다.

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
| `not_applicable` 해당 없음 | AI가 `not_applicable`로 표시한 항목 |
| `missing` 누락 | 값이 없음 |
| `insufficient` 불충분 | "근처", "모름" 같은 모호한 표현만 있음 / `min_length`보다 짧음 / `pattern`에 안 맞음 |
| `sufficient` 충족 | 위에 해당하지 않음 |

예: 발생 위치 `pattern`은 숫자(번지·도로명 번호)나 "OO아파트", "OO사거리" 같은 건물·지점 이름을 요구합니다. 그래서 "집 앞 골목", "상가 앞"은 불충분, "세종대로 209", "OO아파트 정문 앞"은 충족입니다.

## DB 테이블

| 테이블 | 내용 |
|---|---|
| `categories` | 18개 대분류 |
| `fields` | 분야별 필수 정보 항목과 판정 기준 |
| `channels` | 공식 접수 채널 (`category_id`가 NULL이면 기본 채널) |
| `complaints` | 분석 기록 (분석 텍스트, 사진 수, 결과 JSON) |

※ `complaints`에는 민원 원문과 OCR 결과가 그대로 저장되므로 이름·주소 같은 개인정보가 들어갈 수 있습니다.
