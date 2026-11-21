export const MAX_IMAGES = 5;
// CLOVA Speech Recognition(짧은 문장 인식)은 60초 이하 음성만 받습니다.
export const MAX_RECORDING_SEC = 60;

// 입력 언어: CLOVA Speech 단문 인식이 지원하는 4개 언어만 사용
// code: Papago 언어 코드 / speech: 기기 음성 출력 코드
export const LANGUAGES = [
  { code: 'ko', label: '한국어', speech: 'ko-KR', placeholder: '민원 내용을 자유롭게 작성해 주세요...' },
  { code: 'en', label: 'English', speech: 'en-US', placeholder: 'Describe your complaint...' },
  { code: 'ja', label: '日本語', speech: 'ja-JP', placeholder: '苦情の内容を入力してください...' },
  { code: 'zh-CN', label: '中文', speech: 'zh-CN', placeholder: '请输入投诉内容...' },
];
export const getLanguage = (code) => LANGUAGES.find((l) => l.code === code) ?? LANGUAGES[0];

// 분류 기준: 분야 8개(HCX 튜닝 모델) / 유형 4개 / 긴급도 2단계(긴급·일반)
// classification.분야 ← 서버 service_category, classification.세부유형 ← 서버 category_name
export const SERVICE_CATEGORIES = [
  '교통·자동차', '도로·안전시설', '건축·토지', '환경·위생',
  '산림·농업', '복지·보건', '세무·행정', '경제·문화',
];

// 화면 표시용: "교통·자동차 > 자동차" (세부 유형이 없으면 분야만)
export const formatCategory = (classification) => {
  const { 분야, 세부유형 } = classification ?? {};
  if (!분야) return 세부유형 ?? '';
  return 세부유형 ? `${분야} > ${세부유형}` : 분야;
};

export const COMPLAINT_TYPES = {
  신고: '문제가 생겨 조치를 요청',
  문의: '절차·방법·자격을 문의',
  건의: '정책·시설 개선을 제안',
  칭찬: '감사·칭찬',
};

export const URGENCY_META = {
  긴급: { desc: '생명·안전에 바로 위험', color: '#B91C1C', bg: '#FEE2E2' },
  일반: { desc: '당장 위험하지는 않음', color: '#1D4ED8', bg: '#DBEAFE' },
};
export const isUrgent = (classification) => classification?.긴급도 === '긴급';

// 답변 초안 ↔ 규정 모순 검사 결과
export const CONSISTENCY_META = {
  consistent: { label: '규정과 일치', color: '#15803D', bg: '#DCFCE7' },
  inconsistent: { label: '규정과 불일치', color: '#B91C1C', bg: '#FEE2E2' },
  insufficient_evidence: { label: '근거 부족', color: '#B45309', bg: '#FEF3C7' },
};

// 필수 정보 점검 판정 상태
export const FIELD_STATUS_META = {
  sufficient: { label: '충족', color: '#15803D', bg: '#DCFCE7' },
  insufficient: { label: '불충분', color: '#B45309', bg: '#FEF3C7' },
  missing: { label: '누락', color: '#DC2626', bg: '#FEE2E2' },
  not_applicable: { label: '해당 없음', color: '#6B7280', bg: '#F3F4F6' },
};
export const FIELD_STATUS_ORDER = { missing: 0, insufficient: 1, sufficient: 2, not_applicable: 3 };

export const RECEIPT_STATUS_META = {
  received: { label: '접수 완료', color: '#15803D', bg: '#DCFCE7' },
  pending_review: { label: '담당자 확인 대기', color: '#B45309', bg: '#FEF3C7' },
};
