export const MAX_IMAGES = 5;
// CLOVA Speech Recognition(짧은 문장 인식)은 60초 이하 음성만 받습니다.
export const MAX_RECORDING_SEC = 60;

// 입력 언어. papago: Papago 언어 코드 / speech: 기기 음성 출력 코드 / csr: 음성 입력 지원 여부
export const LANGUAGES = [
  { code: 'ko', label: '한국어', speech: 'ko-KR', csr: true, placeholder: '민원 내용을 자유롭게 작성해 주세요...' },
  { code: 'en', label: 'English', speech: 'en-US', csr: true, placeholder: 'Describe your complaint...' },
  { code: 'ja', label: '日本語', speech: 'ja-JP', csr: true, placeholder: '苦情の内容を入力してください...' },
  { code: 'zh-CN', label: '中文', speech: 'zh-CN', csr: true, placeholder: '请输入投诉内容...' },
  { code: 'vi', label: 'Tiếng Việt', speech: 'vi-VN', csr: false, placeholder: 'Nhập nội dung khiếu nại...' },
];
export const getLanguage = (code) => LANGUAGES.find((l) => l.code === code) ?? LANGUAGES[0];

// 분류 기준: 부서 8개 / 유형 4개 / 긴급도 3단계
export const DEPARTMENTS = [
  '교통·주차', '도로·시설물', '환경·청소', '건축·주택',
  '복지·보건', '세무·재정', '안전·재난', '일반행정',
];

export const COMPLAINT_TYPES = {
  신고: '문제가 생겨 조치를 요청',
  문의: '절차·방법·자격을 문의',
  건의: '정책·시설 개선을 제안',
  칭찬: '감사·칭찬',
};

export const URGENCY_META = {
  상: { label: '긴급도 상', desc: '생명·안전에 바로 위험', color: '#B91C1C', bg: '#FEE2E2' },
  중: { label: '긴급도 중', desc: '일상 불편이 계속됨', color: '#B45309', bg: '#FEF3C7' },
  하: { label: '긴급도 하', desc: '당장 조치 필요 없음', color: '#1D4ED8', bg: '#DBEAFE' },
};

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
