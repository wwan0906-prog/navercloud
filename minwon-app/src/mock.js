import { isUrgent } from './config';

// 목업 데이터: 서버 연결 전 화면 개발·시연용 예시입니다.
// 규정 근거·접수처 정보는 실제 출처가 아니므로 발표 자료에 그대로 쓰지 마세요.

export const SAMPLES = [
  { label: '가로등 고장', lang: 'ko', text: '집 앞 골목 가로등이 어제부터 안 켜져서 밤에 너무 위험해요.' },
  { label: '불법주차', lang: 'ko', text: '상가 앞에 불법 주정차 차량이 계속 세워져 있어 통행이 어렵습니다.' },
  { label: '가스 냄새', lang: 'ko', text: '아파트 1층 복도에서 가스 냄새가 심하게 나요. 지금도 계속 나고 있어요.' },
  { label: 'English', lang: 'en', text: 'Trash bags have been piled up in front of my apartment for 3 days and nobody has collected them.' },
];

export const MOCK_STT_TEXT = {
  ko: '집 앞 도로가 움푹 파였어요. 차가 지나갈 때마다 덜컹거려서 위험합니다.',
  en: 'There is a big pothole on the road in front of my house.',
  ja: '家の前の道路に大きな穴があいています。',
  'zh-CN': '我家门前的路上有一个大坑。',
};

export const MOCK_OCR_TEXT =
  '[문서 인식 결과]\n민원 신청서\n신청 내용: 보도블록 파손으로 보행 불편\n발생 장소: (기재 없음)';

const EXAMPLE_CHANNEL = {
  agency: '안전신문고 (예시)',
  url: 'https://www.safetyreport.go.kr',
  phone: '110',
};

const STREETLIGHT = {
  translated_text: null,
  classification: { 부서: '도로·시설물', 유형: '신고', 긴급도: '일반', 요약: '골목 가로등이 어제부터 꺼져 야간 통행이 위험함' },
  answer_draft:
    '불편을 드려 죄송합니다. 접수하신 가로등 고장 건은 현장 확인 후 보수할 예정입니다. 정확한 위치(도로명 주소나 주변 건물명)를 알려 주시면 더 빠르게 처리할 수 있습니다.',
  answer_translated: null,
  consistency: {
    result: 'consistent',
    evidence: [{ source: '민원 처리 안내서 3-2 (예시)', text: '가로등 고장 신고는 현장 확인 후 보수한다.' }],
  },
  field_checks: [
    { key: 'facility_or_work', label: '대상 시설', status: 'sufficient', evidence: '골목 가로등', suggestion: null },
    { key: 'location', label: '발생 위치', status: 'insufficient', evidence: '집 앞 골목', suggestion: '현장을 찾을 수 있도록 도로명 주소나 주변 건물명을 적어 주세요.' },
    { key: 'risk_status', label: '위험·파손 상황', status: 'sufficient', evidence: '어제부터 안 켜져서 밤에 너무 위험해요', suggestion: null },
    { key: 'request', label: '요청 조치', status: 'missing', evidence: null, suggestion: '점검·수리 등 원하는 조치를 적어 주세요.' },
  ],
  guide_message: '고장 난 가로등 위치(예: OO아파트 정문 앞)와 원하는 조치(예: 수리 요청)를 추가하면 더 빨리 처리됩니다.',
  official_channel: EXAMPLE_CHANNEL,
};

const PARKING = {
  translated_text: null,
  classification: { 부서: '교통·주차', 유형: '신고', 긴급도: '일반', 요약: '상가 앞 불법 주정차로 통행 불편이 계속됨' },
  answer_draft:
    '불법 주정차로 불편을 겪고 계셔서 죄송합니다. 해당 구역은 단속 요청으로 접수되며, 정확한 위치와 주로 발생하는 시간대를 알려 주시면 단속에 도움이 됩니다.',
  answer_translated: null,
  consistency: {
    result: 'insufficient_evidence',
    evidence: [{ source: '민원 처리 안내서 2-4 (예시)', text: '불법 주정차 단속은 현장 확인이 가능한 위치 정보가 있어야 한다.' }],
  },
  field_checks: [
    { key: 'traffic_target', label: '교통 관련 대상', status: 'sufficient', evidence: '불법 주정차 차량', suggestion: null },
    { key: 'location', label: '발생 위치', status: 'insufficient', evidence: '상가 앞', suggestion: '상가 이름이나 도로명 주소를 적어 주세요.' },
    { key: 'issue_details', label: '구체적 상황', status: 'sufficient', evidence: '계속 세워져 있어 통행이 어렵습니다', suggestion: null },
    { key: 'request', label: '요청 사항', status: 'missing', evidence: null, suggestion: '단속·계도 등 원하는 조치를 적어 주세요.' },
  ],
  guide_message: '정확한 위치와 주로 발생하는 시간대, 원하는 조치를 추가해 주세요.',
  official_channel: EXAMPLE_CHANNEL,
};

const GAS = {
  translated_text: null,
  classification: { 부서: '안전·재난', 유형: '신고', 긴급도: '긴급', 요약: '아파트 1층 복도에서 가스 냄새가 계속 남' },
  answer_draft:
    '가스 냄새는 즉시 대응이 필요한 위험 상황입니다. 불을 켜거나 끄지 말고 창문을 연 뒤 건물 밖으로 대피하시고, 119에 바로 신고해 주세요. 접수된 민원은 담당자가 확인한 뒤 처리합니다.',
  answer_translated: null,
  consistency: {
    result: 'consistent',
    evidence: [{ source: '민원 처리 안내서 1-1 (예시)', text: '생명·안전 위험 민원은 긴급 처리하고 담당자가 직접 확인한다.' }],
  },
  field_checks: [
    { key: 'facility_or_work', label: '대상 시설', status: 'sufficient', evidence: '아파트 1층 복도', suggestion: null },
    { key: 'location', label: '발생 위치', status: 'insufficient', evidence: '아파트 1층 복도', suggestion: '아파트 이름과 동 번호를 적어 주세요.' },
    { key: 'risk_status', label: '위험 상황', status: 'sufficient', evidence: '가스 냄새가 심하게 나요', suggestion: null },
  ],
  guide_message: '위험하면 먼저 119에 신고하세요. 아파트 이름과 동 번호를 추가하면 현장 확인이 빨라집니다.',
  official_channel: { agency: '소방청 긴급신고 (예시)', url: null, phone: '119' },
};

const TRASH_EN = {
  translated_text: '아파트 앞에 쓰레기봉투가 3일째 쌓여 있는데 아무도 수거하지 않았습니다.',
  classification: { 부서: '환경·청소', 유형: '신고', 긴급도: '일반', 요약: '아파트 앞 쓰레기봉투가 3일째 수거되지 않음' },
  answer_draft:
    '쓰레기 미수거로 불편을 드려 죄송합니다. 해당 지역 수거 업체에 확인해 빠르게 수거하도록 조치하겠습니다. 정확한 주소를 알려 주시면 더 빨리 처리할 수 있습니다.',
  answer_translated:
    'We apologize for the inconvenience. We will contact the collection service for your area and have the trash collected promptly. Providing the exact address will help us process it faster.',
  consistency: {
    result: 'consistent',
    evidence: [{ source: '민원 처리 안내서 4-1 (예시)', text: '생활폐기물 미수거 민원은 수거 업체에 통보해 처리한다.' }],
  },
  field_checks: [
    { key: 'environment_issue', label: '문제 유형', status: 'sufficient', evidence: 'Trash bags have been piled up', suggestion: null },
    { key: 'location', label: '발생 장소', status: 'insufficient', evidence: 'in front of my apartment', suggestion: 'Please add the apartment name or street address.' },
    { key: 'request', label: '요청 조치', status: 'sufficient', evidence: 'nobody has collected them', suggestion: null },
  ],
  guide_message: 'Adding the exact address helps the collection team find the location.',
  official_channel: EXAMPLE_CHANNEL,
};

export function mockAnalyze(text, lang) {
  if (lang !== 'ko') {
    if (lang === 'en' && /trash|garbage/i.test(text)) return TRASH_EN;
    return {
      ...STREETLIGHT,
      translated_text: `(한국어 번역 예시) ${text}`,
      answer_translated: `(역번역 예시) ${STREETLIGHT.answer_draft}`,
    };
  }
  if (/가스|냄새|불이|화재|연기/.test(text)) return GAS;
  if (/주차|주정차|차량/.test(text)) return PARKING;
  return STREETLIGHT;
}

export function mockSubmit(analysis) {
  const d = new Date();
  const ymd = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
  const seq = String(Math.floor(Math.random() * 9000) + 1000);
  const urgent = isUrgent(analysis.classification);
  return {
    receipt_no: `MW-${ymd}-${seq}`,
    department: analysis.classification?.부서,
    status: urgent ? 'pending_review' : 'received',
    message: urgent
      ? '긴급 민원으로 분류되어 담당자가 확인한 뒤 처리합니다.'
      : '담당 부서로 배정되었습니다. 처리 결과는 접수번호로 확인할 수 있습니다.',
  };
}
