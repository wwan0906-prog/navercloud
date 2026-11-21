// 백엔드 없이 화면을 확인할 때 쓰는 목업 응답 (서버 주소가 없거나 EXPO_PUBLIC_USE_MOCK=true 일 때만 사용)
// 실제 서버를 쓰면 이 값들은 쓰이지 않고, 접수 채널·필수 정보는 백엔드 DB(guide_seed.json)에서 옵니다.

// 목업 응답. 백엔드 응답 형식(약속안):
// {
//   main_category: string,              // 18개 대분류 중 하나 (세부 유형 없음)
//   field_checks: [{ key, label, status, evidence, suggestion }],
//   guide_message: string,
//   official_channel: { agency, url, phone },
// }
// 접수 채널 정보는 화면 확인용 예시이며, 실제 값은 백엔드 DB의 공식 출처를 따릅니다.
const MOCK_CHANNEL = {
  agency: '안전신문고',
  url: 'https://www.safetyreport.go.kr',
  phone: '110',
};

const MOCK_STREETLIGHT = {
  main_category: '안전건설',
  field_checks: [
    {
      key: 'facility_or_work', label: '대상 시설·공사', status: 'sufficient',
      evidence: '골목 가로등', suggestion: null,
    },
    {
      key: 'location', label: '발생 위치', status: 'insufficient',
      evidence: '집 앞 골목',
      suggestion: '현장을 찾을 수 있도록 도로명 주소나 주변 건물명을 적어 주세요.',
    },
    {
      key: 'risk_status', label: '위험·파손 상황', status: 'sufficient',
      evidence: '어제부터 안 켜져서 밤에 너무 위험해요', suggestion: null,
    },
    {
      key: 'request', label: '요청 조치', status: 'missing', evidence: null,
      suggestion: '점검·수리 등 원하는 조치를 적어 주세요.',
    },
  ],
  guide_message:
    '보수팀이 현장을 바로 찾을 수 있도록 고장 난 가로등 위치(예: OO아파트 정문 앞)와 원하는 조치(예: 수리 요청)를 추가해 주세요.',
  official_channel: MOCK_CHANNEL,
};

const MOCK_PARKING = {
  main_category: '교통',
  field_checks: [
    {
      key: 'traffic_target', label: '교통 관련 대상·유형', status: 'sufficient',
      evidence: '불법 주정차 차량', suggestion: null,
    },
    {
      key: 'location_or_route', label: '발생 위치·노선', status: 'insufficient',
      evidence: '상가 앞',
      suggestion: '상가 이름이나 도로명 주소를 적어 주세요.',
    },
    {
      key: 'issue_details', label: '교통 문제의 구체적 상황', status: 'sufficient',
      evidence: '계속 세워져 있어 통행이 어렵습니다', suggestion: null,
    },
    {
      key: 'request', label: '요청 사항', status: 'missing', evidence: null,
      suggestion: '단속·계도 등 원하는 조치를 적어 주세요.',
    },
  ],
  guide_message:
    '단속반이 현장을 찾을 수 있도록 정확한 위치와 주로 발생하는 시간대, 원하는 조치를 추가해 주세요.',
  official_channel: MOCK_CHANNEL,
};

export function getMockResponse(text) {
  return /주차|주정차|차량/.test(text) ? MOCK_PARKING : MOCK_STREETLIGHT;
}
