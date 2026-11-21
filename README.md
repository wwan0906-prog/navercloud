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
| AI 상태 | ⏳ 분류·정보 추출은 **아직 mock(가짜 응답)**. 응답의 `ai_mode`가 `"mock"` |

- 주소는 꼭 **`http://`**를 붙여서 입력하세요. 휴대폰 브라우저는 `http://`를 빼면 `https`로 접속하다가 실패할 수 있습니다.
- 서버는 백엔드 담당이 관리합니다. 접속이 안 되거나 `502`·`503` 오류가 나면 알려주세요.

## 📱 앱을 서버에 연결하기

```bash
cd minwon-app
npm install                    # 처음 한 번
cp .env.example .env.local     # 아래 내용으로 수정
npx expo start -c              # -c: 환경변수를 바꾼 뒤에는 캐시를 비우고 실행
```

`minwon-app/.env.local`:

```
EXPO_PUBLIC_API_BASE_URL=http://211.233.204.198:8000
EXPO_PUBLIC_USE_MOCK=false
```

- `.env.local`은 git에 올라가지 않습니다. 각자 만들어 주세요.
- 서버 없이 화면만 보고 싶으면 `EXPO_PUBLIC_USE_MOCK=true`로 두세요. `mock.js`의 목업 응답을 씁니다.
- **휴대폰(Expo Go)으로 볼 때**: Expo 개발 서버에 붙으려면 휴대폰과 PC가 **같은 와이파이**에 있어야 합니다. 안 되면 `npx expo start --tunnel`로 실행하세요. 백엔드 서버는 공인 IP라서 와이파이·모바일 데이터 어디서든 접속됩니다.
- **APK/IPA로 빌드할 때**: 서버가 `https`가 아니라 `http`라서 http 허용 설정이 필요합니다 → [API 명세의 "빌드할 때"](backend/API_명세.md#빌드할-때-http-허용)

### 연결 확인

1. 앱에서 **예시2: 불법주차** 버튼을 누르고 분석합니다.
2. 결과에 `교통`, "발생 위치·노선: 불충분", "요청 사항: 누락"이 나오면 서버와 연결된 것입니다.
3. 문서 사진을 첨부하면 서버가 CLOVA OCR로 글자를 읽어서 함께 분석합니다.

## 🤖 AI 연결 (2번 팀원)

`backend/app/ai_client.py`의 `_real_classify`, `_real_extract` 두 함수만 채우면 됩니다. 입출력 형식은 [backend/README.md의 "AI 연결 방법"](backend/README.md#2번-팀원-ai-연결-방법)에 있습니다. 연결되면 배포 서버의 `AI_MODE`를 `real`로 바꿔서 다시 배포합니다.

## 현재 상태

| 항목 | 상태 |
|---|---|
| 앱 화면 (입력, 사진 첨부, 점검 결과, 접수 채널) | ✅ |
| 백엔드 API, 문서 사진 OCR, 필수 정보 판정, 분석 기록, 읽어주기(TTS) | ✅ 배포됨 |
| 18개 분야 필수 정보 항목 (`backend/data/category_requirements.json` 기준) | ✅ |
| AI 분류(HCX 튜닝 모델)·정보 추출 | ⏳ 아직 없음 (지금은 mock) |
| 분야별 공식 접수 채널 | ⏳ 미정 (지금은 전부 국민신문고 · 110) |
| 앱의 읽어주기 버튼 | ⏳ 선택 (서버 API는 있음: `GET /api/complaints/{id}/audio`) |
