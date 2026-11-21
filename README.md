# AI 민원 작성 도우미

민원 내용(텍스트·문서 사진)을 넣으면 18개 분야 중 하나로 분류하고, **빠지거나 부족한 필수 정보**와 **공식 접수 채널**을 안내하는 앱입니다.

| 폴더 | 내용 | 문서 |
|---|---|---|
| `minwon-app/` | 앱 (React Native + Expo) | |
| `backend/` | API 서버 (FastAPI + SQLite, CLOVA OCR·Voice) | [backend/README.md](backend/README.md), [backend/API_명세.md](backend/API_명세.md) |

---

## 🚀 배포 서버

| 항목 | 값 |
|---|---|
| **서버 주소** | **`http://211.233.204.198:8000`** |
| 상태 확인 | http://211.233.204.198:8000/api/health → `{"status":"ok", ...}`가 나오면 정상 |
| API 테스트 화면 | http://211.233.204.198:8000/docs (브라우저에서 바로 호출해 볼 수 있음) |
| 메인 API | `POST /api/analyze` (자세한 내용은 [API 명세](backend/API_명세.md)) |
| AI 상태 | ✅ 실제 AI (HCX 튜닝 모델 + 프롬프트). 응답의 `ai_mode`가 `"real"` |

- 주소는 꼭 **`http://`**를 붙여서 입력하세요. 휴대폰 브라우저는 `http://`를 빼면 `https`로 접속하다가 실패할 수 있습니다.
- 서버는 백엔드 담당이 관리합니다. 접속이 안 되거나 `502`·`503` 오류가 나면 알려주세요.

## 📱 앱을 서버에 연결하기

```bash
cd minwon-app
npm install                    # 처음 한 번
cp .env.example .env.local     # 아래 내용이 이미 들어 있음
npx expo start
```

`minwon-app/.env.local`:

```
EXPO_PUBLIC_API_BASE_URL=http://211.233.204.198:8000
EXPO_PUBLIC_USE_MOCK=false
```

- `.env.local`은 git에 올라가지 않습니다. 각자 만들어 주세요.
- `.env.local`을 고친 뒤에는 앱을 **다시 로드(Reload)**하면 반영됩니다 (Expo Go: 휴대폰을 흔들고 Reload).
- 서버 없이 화면만 보고 싶으면 `EXPO_PUBLIC_USE_MOCK=true`로 두세요. `src/mock.js`의 목업 데이터를 씁니다.
- **휴대폰(Expo Go)으로 볼 때**: Expo 개발 서버에 붙으려면 휴대폰과 PC가 **같은 와이파이**에 있어야 합니다. 안 되면 `npx expo start --tunnel`로 실행하세요. 백엔드 서버는 공인 IP라서 와이파이·모바일 데이터 어디서든 접속됩니다.
- **APK/IPA로 빌드할 때**: 서버가 `https`가 아니라 `http`라서 http 허용 설정이 필요합니다 → [API 명세의 "빌드할 때"](backend/API_명세.md#빌드할-때-http-허용)

### 연결 확인

앱의 ① 음성·사진 입력, ②~④ 분석(분류·필수 정보 점검·답변 초안·긴급도·외국어 번역), ⑤ 접수가 모두 서버에 연결돼 있습니다 (`src/api.js`). 규정 검사는 이번 범위에서 빠져서 화면에 나오지 않습니다.

1. **문서 사진**을 찍거나 고르면, 사진 속 글자가 입력창에 들어갑니다. 목업일 때 나오던 "보도블록 파손…" 예시 문장이 아니라 실제 사진의 글자가 나오면 연결된 것입니다.
2. **🎤 음성으로 입력**을 눌러 말하고 끝내면, 말한 내용이 입력창에 들어갑니다 (60초 이하, 한국어·영어·일본어·중국어).

## 🤖 AI 연결 (2번 팀원)

`backend/app/ai_client.py`의 `_real_classify`, `_real_extract` 두 함수만 채우면 됩니다. 입출력 형식은 [backend/README.md의 "AI 연결 방법"](backend/README.md#2번-팀원-ai-연결-방법)에 있습니다. 연결되면 배포 서버의 `AI_MODE`를 `real`로 바꿔서 다시 배포합니다.

## 현재 상태

| 항목 | 상태 |
|---|---|
| 앱 화면 (기획서 6단계: 음성·사진·외국어 입력, 분류, 답변, 규정 검사, 접수) | ✅ |
| 앱 ↔ 서버: 음성 입력(CSR), 문서 사진(OCR) | ✅ 연결됨 |
| 앱 ↔ 서버: 분석(답변 초안·긴급도·요약·외국어 번역)·접수 | ✅ 연결됨 (규정 검사는 범위 제외) |
| 백엔드 API, 문서 사진 OCR, 필수 정보 판정, 분석 기록, 읽어주기(TTS) | ✅ 배포됨 |
| 18개 분야 필수 정보 항목 (`backend/data/category_requirements.json` 기준) | ✅ |
| AI 분류(HCX 튜닝 모델)·정보 추출 | ✅ 배포 서버 실제 AI 모드 |
| 분야별 공식 접수 채널 | ✅ 18개 분야 (2번 팀원 조사, `guide_seed.json`) |
| 앱의 읽어주기 버튼 | ⏳ 선택 (서버 API는 있음: `GET /api/complaints/{id}/audio`) |
