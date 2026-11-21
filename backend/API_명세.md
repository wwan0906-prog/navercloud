# 민원 작성 가이드 API 명세 (프론트엔드용)

> 버전 0.3 · 2026-11-21 · `minwon-app/App.js`의 응답 형식(약속안)에 맞춤

## 현재 상태

| 항목 | 상태 | 비고 |
|---|---|---|
| `POST /api/analyze` (텍스트 + 사진 최대 5장) | ✅ 완성 | 앱의 약속안 형식 그대로 |
| 사진 OCR (CLOVA OCR) | ✅ 완성 | 실제 동작 |
| 필수 정보 판정 · 안내문 · 접수 채널 | ✅ 완성 | 실제 동작 |
| 분석 기록 저장 · 조회, 읽어주기(TTS) | ✅ 완성 | 앱에서 쓰려면 화면 추가 필요 (선택) |
| AI 분류 · 정보 추출 (HCX + RAG, 2번 팀원) | ⏳ **아직 없음** | 지금은 키워드 기반 **가짜 응답** (`ai_mode: "mock"`) |
| 분야별 필수 정보 항목 | ✅ 18개 모두 | 팀 기준 파일(민원 18개 카테고리 공식요건 검수) 기준. 분야당 3~5개, 조건부 필수 항목은 조건에 안 맞으면 `not_applicable` |
| 분야별 공식 접수 채널 | ⏳ **미정** | 지금은 전부 국민신문고 · 110 |

앱의 예시 버튼 두 개(가로등 고장, 불법주차)는 가짜 응답 상태에서도 앱 목업과 **같은 판정 결과**가 나옵니다.

## 앱 설정

```bash
cd minwon-app
cp .env.example .env.local      # 배포 서버: EXPO_PUBLIC_API_BASE_URL=http://211.233.204.198:8000
npx expo start -c               # 환경변수를 바꾼 뒤에는 -c 로 캐시 비우고 실행
```

`EXPO_PUBLIC_API_BASE_URL`이 비어 있거나 `EXPO_PUBLIC_USE_MOCK=true`면 서버 없이 `mock.js`의 목업으로 동작합니다.

---

## `POST /api/analyze`

**요청**: `multipart/form-data`

| 필드 | 설명 |
|---|---|
| `complaint_text` | 민원 내용 (비워도 됨) |
| `files` | 문서 사진. 같은 이름으로 여러 개 (최대 5장, jpg · jpeg · png · pdf · tiff) |

텍스트와 사진 중 하나는 있어야 합니다. 사진은 OCR로 읽어서 텍스트 뒤에 붙인 다음 함께 분석합니다.

**응답**

```json
{
  "main_category": "안전건설",
  "field_checks": [
    { "key": "location", "label": "발생 위치", "status": "insufficient",
      "evidence": "집 앞 골목",
      "suggestion": "현장을 찾을 수 있도록 도로명 주소나 주변 건물명을 적어 주세요." },
    { "key": "request", "label": "요청 조치", "status": "missing",
      "evidence": null, "suggestion": "점검·수리 등 원하는 조치를 적어 주세요." }
  ],
  "guide_message": "담당 부서가 바로 처리할 수 있도록 발생 위치, 요청 조치를 보완해 주세요. (예: ...)",
  "official_channel": { "agency": "국민신문고", "url": "https://www.epeople.go.kr", "phone": "110" },

  "id": 1,
  "created_at": "2026-11-20T18:05:12+09:00",
  "category_name": "안전건설",
  "confidence": null,
  "has_guide_data": true,
  "is_complete": false,
  "ai_mode": "mock",
  "complaint_text": "집 앞 골목 가로등이 ...",
  "ocr_texts": [],
  "warnings": [],
  "guide_text": "안전건설 분야 민원입니다. ..."
}
```

**앞의 4개(약속안)는 앱이 이미 쓰고 있는 필드**입니다. 나머지는 추가 정보라 안 써도 됩니다.

| 필드 | 설명 |
|---|---|
| `main_category` | 18개 대분류 중 하나 (AI Hub 라벨 그대로: `문화_체육_관광`처럼 밑줄 포함) |
| `field_checks[].status` | `sufficient` · `insufficient` · `missing` · `not_applicable` |
| `field_checks[].evidence` | 원문에서 찾은 구절. 없으면 `null` |
| `field_checks[].suggestion` | 보완 안내. 충족·해당 없음이면 `null` |
| `category_name` | 표시용 이름 (`문화·체육·관광`처럼 가운뎃점). 배지에 쓰면 더 깔끔함 |
| `has_guide_data` | 이 분야의 필수 정보 기준이 DB에 있는지. `false`면 `field_checks`가 빈 목록 |
| `is_complete` | 필수 항목이 모두 충족인지 |
| `ocr_texts` | 사진별 OCR 결과 |
| `warnings` | 일부 사진을 못 읽었을 때 이유 (나머지로 분석은 계속함) |
| `id` | 기록 번호. 읽어주기 · 기록 조회에 사용 |
| `guide_text` | 읽어주기용 문장 |

## 오류

`{"detail": "메시지"}` 형식입니다. 앱은 이 메시지를 그대로 알림창에 보여주도록 수정해 두었습니다.

| 코드 | 언제 |
|---|---|
| 400 | 텍스트도 없고 읽을 수 있는 사진도 없음, 사진 6장 이상 |
| 502 | CLOVA(OCR · HCX) 호출 실패. 사용량 초과일 수 있음 → 백엔드 담당에게 알려주세요 |
| 503 | AI 연결 전인데 서버가 실제 모드로 설정됨 → 백엔드 담당에게 알려주세요 |

---

## 선택 기능 (화면을 추가할 때)

| API | 용도 |
|---|---|
| `GET /api/complaints/{id}/audio` | 안내문 읽어주기 mp3. 오디오 URI로 바로 사용 (expo-audio 설치 필요). 한 번 만든 음성은 서버가 재사용 |
| `GET /api/complaints?limit=20` | 최근 분석 기록 목록 |
| `GET /api/complaints/{id}` | 기록 하나 (`/api/analyze` 응답과 같은 형식) |
| `POST /api/tts` | 아무 문장이나 mp3로. `{"text", "speaker": "nara", "speed": 0}` |
| `GET /api/categories` | 18개 대분류와 분야별 필수 정보 항목 |
| `GET /api/health` | 서버 상태, AI 모드 |

## 빌드할 때: http 허용

서버 주소가 `http`라서, 앱을 빌드(APK/IPA)하면 기본 설정으로는 호출이 막힙니다. Expo Go로 개발할 때는 보통 문제없습니다. 빌드 전에 `npx expo install expo-build-properties`로 설치하고 `app.json`에 추가해 주세요.

```json
"plugins": [
  ["expo-build-properties", { "android": { "usesCleartextTraffic": true } }]
],
"ios": { "infoPlist": { "NSAppTransportSecurity": { "NSAllowsArbitraryLoads": true } } }
```
