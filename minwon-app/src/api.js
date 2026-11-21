// 앱이 백엔드에 요청하는 기능을 모아 둔 파일입니다.
// 서버 주소는 minwon-app/.env.local 의 EXPO_PUBLIC_API_BASE_URL 에서 읽습니다 (.env.example 참고).
// 주소가 없거나 EXPO_PUBLIC_USE_MOCK=true 이면 서버 없이 목업 데이터(mock.js)를 씁니다.
//
// 연결 상태: ① 음성·사진 → 글자는 서버 연결됨 / ②~⑤ 분석·접수는 아직 목업
// 각 함수 안만 바꾸면 화면 코드는 그대로 쓸 수 있습니다.
import { Platform } from 'react-native';
import { MOCK_OCR_TEXT, MOCK_STT_TEXT, mockAnalyze, mockSubmit } from './mock';

const API_BASE_URL = (process.env.EXPO_PUBLIC_API_BASE_URL || '').replace(/\/+$/, '');
export const USE_SERVER = !!API_BASE_URL && process.env.EXPO_PUBLIC_USE_MOCK !== 'true';

const delay = (ms) => new Promise((r) => setTimeout(r, ms));

// 파일 경로(uri)를 FormData 에 넣을 형태로. 웹(expo start --web)은 uri 가 blob 이라 Blob 으로 변환
async function appendFile(form, field, { uri, name, type }) {
  if (Platform.OS === 'web') {
    const blob = await (await fetch(uri)).blob();
    form.append(field, blob, name);
  } else {
    form.append(field, { uri, name, type });
  }
}

// 백엔드 호출. 실패하면 서버가 보낸 이유({"detail": "..."})를 메시지로 던짐
async function postForm(path, form) {
  let res;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, { method: 'POST', body: form });
  } catch {
    throw new Error('서버와 통신할 수 없습니다. 인터넷 연결이나 서버 주소를 확인해 주세요.');
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(typeof body?.detail === 'string' ? body.detail : `서버 오류 (HTTP ${res.status})`);
  }
  return body;
}

// ① 음성 → 글자 (CLOVA Speech Recognition, 60초 이하, ko·en·ja·zh-CN)
// uri: 녹음 파일(m4a) 경로, lang: 입력 언어 코드
export async function transcribeAudio(uri, lang) {
  if (!USE_SERVER) {
    await delay(900);
    return MOCK_STT_TEXT[lang] ?? MOCK_STT_TEXT.ko;
  }
  const ext = (uri.split('?')[0].split('.').pop() || 'm4a').toLowerCase();
  const form = new FormData();
  await appendFile(form, 'audio', { uri, name: `voice.${ext}`, type: ext === 'm4a' ? 'audio/m4a' : `audio/${ext}` });
  form.append('lang', lang);
  const { text } = await postForm('/api/stt', form);
  return text;
}

// ① 문서 사진 → 글자 (CLOVA OCR)
// asset: expo-image-picker 결과 (uri, fileName, mimeType)
export async function recognizeImage(asset) {
  if (!USE_SERVER) {
    await delay(1100);
    return MOCK_OCR_TEXT;
  }
  const ext = (asset.uri.split('?')[0].split('.').pop() || 'jpg').toLowerCase();
  const form = new FormData();
  await appendFile(form, 'image', {
    uri: asset.uri,
    name: asset.fileName || `document.${ext}`,
    type: asset.mimeType || 'image/jpeg',
  });
  const { text } = await postForm('/api/ocr', form);
  return text;
}

// ①~④ 번역 → 분류 → 답변 초안 → 규정 검사 (아직 목업. 연동 범위 결정 대기)
// 반환 형식은 mock.js의 예시 객체를 참고하세요.
// 서버 연동 시 분류 필드 매핑: service_category → classification.분야, category_name → classification.세부유형
// (화면에는 "교통·자동차 > 자동차"처럼 표시됨)
export async function analyzeComplaint(text, lang) {
  await delay(1200);
  return mockAnalyze(text, lang);
}

// ⑤ 접수 처리 (아직 목업. 연동 범위 결정 대기 — 접수번호 발급, 분야 배정, 긴급 민원은 담당자 확인 대기)
export async function submitComplaint(text, lang, analysis) {
  await delay(800);
  return mockSubmit(analysis);
}
