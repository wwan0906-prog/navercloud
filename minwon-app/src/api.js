// 앱이 백엔드에 요청하는 기능을 모아 둔 파일입니다.
// 지금은 백엔드 연결 전이라 모두 목업 데이터를 돌려줍니다.
// 백엔드 연동 시 각 함수 안의 목업 부분만 실제 API 호출로 바꾸면 화면 코드는 그대로 쓸 수 있습니다.
import { MOCK_OCR_TEXT, MOCK_STT_TEXT, mockAnalyze, mockSubmit } from './mock';

const delay = (ms) => new Promise((r) => setTimeout(r, ms));

// ① 음성 → 글자 (연동 예정: CLOVA Speech Recognition)
// uri: 녹음 파일(m4a) 경로, lang: 입력 언어 코드
export async function transcribeAudio(uri, lang) {
  await delay(900);
  return MOCK_STT_TEXT[lang] ?? MOCK_STT_TEXT.ko;
}

// ① 문서 사진 → 글자 (연동 예정: CLOVA OCR)
// asset: expo-image-picker 결과 (uri, fileName, mimeType)
export async function recognizeImage(asset) {
  await delay(1100);
  return MOCK_OCR_TEXT;
}

// ①~④ 번역 → 분류 → 답변 초안 → 규정 검사 (연동 예정: Papago, HCX 튜닝 모델, RAG, 모순 검사)
// 반환 형식은 mock.js의 예시 객체를 참고하세요.
export async function analyzeComplaint(text, lang) {
  await delay(1200);
  return mockAnalyze(text, lang);
}

// ⑤ 접수 처리 (연동 예정: Function Calling — 접수번호 발급, 부서 배정, 긴급 민원은 담당자 확인 대기)
export async function submitComplaint(text, lang, analysis) {
  await delay(800);
  return mockSubmit(analysis);
}
