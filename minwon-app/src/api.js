// 앱이 백엔드에 요청하는 기능을 모아 둔 파일입니다.
// 서버 주소는 minwon-app/.env.local 의 EXPO_PUBLIC_API_BASE_URL 에서 읽습니다 (.env.example 참고).
// 주소가 없거나 EXPO_PUBLIC_USE_MOCK=true 이면 서버 없이 목업 데이터(mock.js)를 씁니다.
//
// 연결 상태: ① 음성·사진 → 글자, ②~④ 분석, ⑤ 접수 모두 서버 연결됨 (규정 검사는 범위 제외)
// 각 함수 안만 바꾸면 화면 코드는 그대로 쓸 수 있습니다.
import { Platform } from 'react-native';
import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';
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

// 파일(사진·녹음)을 올리는 요청.
// Expo SDK 58의 기본 fetch(expo/fetch)는 React Native식 파일 파트({ uri, name, type })를 지원하지 않아
// "Unsupported FormDataPart implementation"으로 실패함 → 네이티브에서는 XMLHttpRequest로 보냄
const UPLOAD_TIMEOUT_MS = 60000;

function uploadForm(path, form) {
  if (Platform.OS === 'web') return postForm(path, form);
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${API_BASE_URL}${path}`);
    xhr.timeout = UPLOAD_TIMEOUT_MS;
    xhr.onload = () => {
      let body = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {}
      if (xhr.status >= 200 && xhr.status < 300) resolve(body);
      else reject(new Error(typeof body?.detail === 'string' ? body.detail : `서버 오류 (HTTP ${xhr.status})`));
    };
    xhr.onerror = () => {
      console.warn(`[api] ${path} 업로드 실패 (네트워크 오류)`);
      reject(new Error('서버와 통신할 수 없습니다. 인터넷 연결이나 서버 주소를 확인해 주세요.'));
    };
    xhr.ontimeout = () => {
      console.warn(`[api] ${path} 업로드 시간 초과`);
      reject(new Error('서버 응답이 너무 늦습니다. 잠시 후 다시 시도해 주세요.'));
    };
    xhr.send(form);
  });
}

// 백엔드 호출. 실패하면 서버가 보낸 이유({"detail": "..."})를 메시지로 던짐
async function postForm(path, form) {
  let res;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, { method: 'POST', body: form });
  } catch (e) {
    // 실제 원인을 개발 서버 로그(Metro)에 남겨 원인 파악이 가능하도록 함
    console.warn(`[api] ${path} 요청 실패:`, e?.message ?? e);
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
  const { text } = await uploadForm('/api/stt', form);
  return text;
}

// ① 문서 사진 → 글자 (CLOVA OCR)
// asset: expo-image-picker 결과 (uri, fileName, mimeType)
export async function recognizeImage(asset) {
  if (!USE_SERVER) {
    await delay(1100);
    return MOCK_OCR_TEXT;
  }
  const form = new FormData();
  await appendFile(form, 'image', await prepareImageForUpload(asset));
  const { text } = await uploadForm('/api/ocr', form);
  return text;
}

// 휴대폰 원본 사진(수 MB, iOS는 HEIC)을 그대로 올리면 업로드가 느리거나 끊기고 OCR이 못 읽는 형식일 수 있음
// → 긴 변 MAX_UPLOAD_EDGE px 이하의 JPEG로 바꿔서 보냄 (문서 글자 인식에는 충분한 해상도)
const MAX_UPLOAD_EDGE = 1600;

async function prepareImageForUpload(asset) {
  const original = {
    uri: asset.uri,
    name: asset.fileName || `document.${(asset.uri.split('?')[0].split('.').pop() || 'jpg').toLowerCase()}`,
    type: asset.mimeType || 'image/jpeg',
  };
  if (Platform.OS === 'web') return original;
  try {
    const { width = 0, height = 0 } = asset;
    const context = ImageManipulator.manipulate(asset.uri);
    if (Math.max(width, height) > MAX_UPLOAD_EDGE) {
      context.resize(width >= height ? { width: MAX_UPLOAD_EDGE } : { height: MAX_UPLOAD_EDGE });
    }
    const image = await context.renderAsync();
    const saved = await image.saveAsync({ compress: 0.7, format: SaveFormat.JPEG });
    return { uri: saved.uri, name: 'document.jpg', type: 'image/jpeg' };
  } catch (e) {
    console.warn('[api] 사진 변환 실패, 원본으로 전송:', e?.message ?? e);
    return original;
  }
}

// ①~④ 번역 → 분류 → 필수 정보 점검 → 답변 초안·긴급도·요약 (서버: HCX 튜닝 모델 + 프롬프트)
// 서버가 화면 형식 그대로 돌려줌: classification{분야, 세부유형, 유형, 긴급도, 요약}, translated_text,
// answer_draft, answer_translated, field_checks, guide_message, official_channel, id(접수에 사용)
// 규정 검사(consistency)는 이번 범위에서 제외되어 서버가 null 로 보냄 → 화면에서 숨겨짐
export async function analyzeComplaint(text, lang) {
  if (!USE_SERVER) {
    await delay(1200);
    return mockAnalyze(text, lang);
  }
  const form = new FormData();
  form.append('complaint_text', text);
  form.append('lang', lang);
  return postForm('/api/analyze', form);
}

// ⑤ 접수: 접수번호 발급 + 분야 배정. 긴급 민원은 담당자 확인 대기 (서버: /api/submit)
export async function submitComplaint(text, lang, analysis) {
  if (!USE_SERVER || !analysis?.id) {
    await delay(800);
    return mockSubmit(analysis);
  }
  let res;
  try {
    res = await fetch(`${API_BASE_URL}/api/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ complaint_id: analysis.id }),
    });
  } catch {
    throw new Error('서버와 통신할 수 없습니다. 인터넷 연결이나 서버 주소를 확인해 주세요.');
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(typeof body?.detail === 'string' ? body.detail : `서버 오류 (HTTP ${res.status})`);
  }
  return body;   // { receipt_no, department, status, message, ... }
}
