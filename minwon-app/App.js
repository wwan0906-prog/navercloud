import { useState } from 'react';
import {
  ScrollView, View, Text, TextInput, Image,
  TouchableOpacity, ActivityIndicator, StyleSheet, Linking, Alert
} from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import * as ImagePicker from 'expo-image-picker';

// 백엔드 서버 연동 시 USE_MOCK을 false로 바꾸고 실제 서버 주소를 입력하세요.
const USE_MOCK = true;
const API_URL = 'http://서버_공인_IP:8000/api/analyze';

// 한 번에 첨부할 수 있는 문서 사진 수
const MAX_IMAGES = 5;

// 필드 판정 상태 (민원 필수 정보 기준표 schema 1.0.0의 evaluation_statuses)
const STATUS_META = {
  sufficient: { label: '충족', color: '#15803D', bg: '#DCFCE7' },
  insufficient: { label: '불충분', color: '#B45309', bg: '#FEF3C7' },
  missing: { label: '누락', color: '#DC2626', bg: '#FEE2E2' },
  not_applicable: { label: '해당 없음', color: '#6B7280', bg: '#F3F4F6' },
};
const STATUS_ORDER = { missing: 0, insufficient: 1, sufficient: 2, not_applicable: 3 };

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

function getMockResponse(text) {
  return /주차|주정차|차량/.test(text) ? MOCK_PARKING : MOCK_STREETLIGHT;
}

// 서버로 보낼 파일 정보 (React Native FormData 형식)
function toUploadFile(asset, index) {
  const ext = (asset.uri.split('.').pop() || 'jpg').toLowerCase();
  return {
    uri: asset.uri,
    name: asset.fileName || `document_${index + 1}.${ext}`,
    type: asset.mimeType || 'image/jpeg',
  };
}

function openLink(url) {
  Linking.openURL(url).catch(() => Alert.alert('알림', '링크를 열 수 없습니다.'));
}

export default function App() {
  const [text, setText] = useState('');
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const addImages = (assets) => {
    setImages((prev) => {
      const merged = [...prev, ...assets];
      if (merged.length > MAX_IMAGES) {
        Alert.alert('알림', `사진은 최대 ${MAX_IMAGES}장까지 첨부할 수 있습니다.`);
      }
      return merged.slice(0, MAX_IMAGES);
    });
  };

  const pickFromLibrary = async () => {
    if (images.length >= MAX_IMAGES) {
      Alert.alert('알림', `사진은 최대 ${MAX_IMAGES}장까지 첨부할 수 있습니다.`);
      return;
    }
    const picked = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsMultipleSelection: true,
      selectionLimit: MAX_IMAGES - images.length,
      quality: 0.8,
    });
    if (!picked.canceled) addImages(picked.assets);
  };

  const takePhoto = async () => {
    if (images.length >= MAX_IMAGES) {
      Alert.alert('알림', `사진은 최대 ${MAX_IMAGES}장까지 첨부할 수 있습니다.`);
      return;
    }
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) {
      Alert.alert('권한 필요', '문서를 촬영하려면 카메라 권한을 허용해 주세요.');
      return;
    }
    const shot = await ImagePicker.launchCameraAsync({
      mediaTypes: ['images'],
      quality: 0.8,
    });
    if (!shot.canceled) addImages(shot.assets);
  };

  const removeImage = (uri) => {
    setImages((prev) => prev.filter((img) => img.uri !== uri));
  };

  const handleAnalyze = async () => {
    if (!text.trim() && images.length === 0) {
      Alert.alert('알림', '민원 내용을 입력하거나 문서 사진을 첨부해 주세요.');
      return;
    }
    setLoading(true);
    setResult(null);

    try {
      if (USE_MOCK) {
        await new Promise((r) => setTimeout(r, 800));
        setResult(getMockResponse(text));
      } else {
        // 민원 텍스트와 문서 사진(OCR용)을 multipart/form-data로 함께 전송
        const form = new FormData();
        form.append('complaint_text', text);
        images.forEach((img, i) => form.append('files', toUploadFile(img, i)));

        const res = await fetch(API_URL, { method: 'POST', body: form });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        setResult(await res.json());
      }
    } catch (err) {
      Alert.alert('연결 오류', '백엔드 서버와 통신할 수 없습니다.');
    } finally {
      setLoading(false);
    }
  };

  const channel = result?.official_channel;
  const checks = [...(result?.field_checks ?? [])].sort(
    (a, b) => (STATUS_ORDER[a.status] ?? 9) - (STATUS_ORDER[b.status] ?? 9)
  );
  const needsFix = checks.filter((c) => c.status === 'missing' || c.status === 'insufficient').length;

  return (
    <SafeAreaProvider>
      <StatusBar style="dark" />
      <SafeAreaView style={styles.container}>
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <Text style={styles.header}>AI 민원 작성 도우미</Text>
          <Text style={styles.subHeader}>민원을 입력하면 누락된 필수 정보와 공식 접수처를 안내합니다.</Text>

          {/* 시연용 빠른 입력 버튼 */}
          <View style={styles.sampleRow}>
            <TouchableOpacity
              style={styles.sampleBtn}
              onPress={() => setText('집 앞 골목 가로등이 어제부터 안 켜져서 밤에 너무 위험해요.')}
            >
              <Text style={styles.sampleBtnText}>예시1: 가로등 고장</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.sampleBtn}
              onPress={() => setText('상가 앞에 불법 주정차 차량이 계속 세워져 있어 통행이 어렵습니다.')}
            >
              <Text style={styles.sampleBtnText}>예시2: 불법주차</Text>
            </TouchableOpacity>
          </View>

          {/* 민원 입력창 */}
          <TextInput
            style={styles.input}
            multiline
            placeholder="민원 내용을 자유롭게 작성해 주세요..."
            value={text}
            onChangeText={setText}
          />

          {/* 문서 사진 첨부 (OCR) */}
          <View style={styles.uploadBox}>
            <View style={styles.uploadHeader}>
              <Text style={styles.uploadTitle}>문서 사진 첨부</Text>
              <Text style={styles.uploadCount}>{images.length}/{MAX_IMAGES}</Text>
            </View>
            <Text style={styles.uploadHint}>
              고지서·공문·신청서 등을 찍어 올리면 글자를 읽어 민원 분석에 함께 사용합니다.
            </Text>
            <View style={styles.uploadBtnRow}>
              <TouchableOpacity style={styles.uploadBtn} onPress={takePhoto}>
                <Text style={styles.uploadBtnText}>카메라로 촬영</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.uploadBtn} onPress={pickFromLibrary}>
                <Text style={styles.uploadBtnText}>앨범에서 선택</Text>
              </TouchableOpacity>
            </View>

            {images.length > 0 && (
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.thumbRow}>
                {images.map((img) => (
                  <View key={img.uri} style={styles.thumbWrap}>
                    <Image source={{ uri: img.uri }} style={styles.thumb} />
                    <TouchableOpacity
                      style={styles.thumbRemove}
                      onPress={() => removeImage(img.uri)}
                      hitSlop={8}
                    >
                      <Text style={styles.thumbRemoveText}>✕</Text>
                    </TouchableOpacity>
                  </View>
                ))}
              </ScrollView>
            )}
          </View>

          <TouchableOpacity
            style={[styles.submitBtn, loading && styles.submitBtnDisabled]}
            onPress={handleAnalyze}
            disabled={loading}
          >
            <Text style={styles.submitBtnText}>민원 분석 및 보완 가이드 받기</Text>
          </TouchableOpacity>

          {loading && <ActivityIndicator size="large" color="#1B64DA" style={{ marginTop: 24 }} />}

          {/* 분석 결과 표시 */}
          {result && (
            <View style={styles.resultBox}>
              {/* 1. 분류 결과 */}
              <View style={styles.badgeRow}>
                <Text style={styles.badgePrimary}>{result.main_category}</Text>
              </View>

              {/* 2. 필수 정보 항목별 점검 */}
              <Text style={styles.sectionTitle}>
                필수 정보 점검{' '}
                <Text style={needsFix ? styles.summaryWarn : styles.summaryOk}>
                  {needsFix ? `보완 필요 ${needsFix}건` : '모두 충족'}
                </Text>
              </Text>
              {checks.map((c) => {
                const meta = STATUS_META[c.status] ?? STATUS_META.missing;
                const muted = c.status === 'not_applicable';
                return (
                  <View key={c.key} style={[styles.checkItem, muted && styles.checkItemMuted]}>
                    <View style={styles.checkHeader}>
                      <Text style={[styles.statusChip, { color: meta.color, backgroundColor: meta.bg }]}>
                        {meta.label}
                      </Text>
                      <Text style={styles.checkLabel}>{c.label}</Text>
                    </View>
                    {c.evidence && !muted ? (
                      <Text style={styles.checkEvidence}>원문: “{c.evidence}”</Text>
                    ) : null}
                    {c.suggestion && !muted ? (
                      <Text style={styles.checkSuggestion}>→ {c.suggestion}</Text>
                    ) : null}
                  </View>
                );
              })}

              {/* 3. 맞춤형 보완 안내문 */}
              <Text style={styles.sectionTitle}>맞춤형 보완 안내</Text>
              <View style={styles.guideCard}>
                <Text style={styles.guideText}>{result.guide_message}</Text>
              </View>

              {/* 4. 공식 접수 채널: 카테고리 · 웹사이트 · 전화번호 */}
              {channel && (
                <>
                  <Text style={styles.sectionTitle}>공식 접수 채널</Text>
                  <View style={styles.channelCard}>
                    <Text style={styles.channelAgency}>{channel.agency}</Text>

                    <View style={styles.infoRow}>
                      <Text style={styles.infoLabel}>카테고리</Text>
                      <Text style={styles.infoValue}>{result.main_category}</Text>
                    </View>

                    {channel.url ? (
                      <View style={styles.infoRow}>
                        <Text style={styles.infoLabel}>웹사이트</Text>
                        <Text style={[styles.infoValue, styles.infoLink]} onPress={() => openLink(channel.url)}>
                          {channel.url}
                        </Text>
                      </View>
                    ) : null}

                    {channel.phone ? (
                      <View style={styles.infoRow}>
                        <Text style={styles.infoLabel}>전화번호</Text>
                        <Text style={[styles.infoValue, styles.infoLink]} onPress={() => openLink(`tel:${channel.phone}`)}>
                          {channel.phone}
                        </Text>
                      </View>
                    ) : null}

                    <View style={styles.actionRow}>
                      {channel.url ? (
                        <TouchableOpacity
                          style={[styles.linkBtn, { backgroundColor: '#1B64DA' }]}
                          onPress={() => openLink(channel.url)}
                        >
                          <Text style={styles.linkBtnText}>웹/앱 바로가기</Text>
                        </TouchableOpacity>
                      ) : null}
                      {channel.phone ? (
                        <TouchableOpacity
                          style={[styles.linkBtn, { backgroundColor: '#0F9D58' }]}
                          onPress={() => openLink(`tel:${channel.phone}`)}
                        >
                          <Text style={styles.linkBtnText}>전화 걸기</Text>
                        </TouchableOpacity>
                      ) : null}
                    </View>
                  </View>
                </>
              )}
            </View>
          )}
        </ScrollView>
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F7FA' },
  scroll: { padding: 20, paddingBottom: 40 },
  header: { fontSize: 22, fontWeight: 'bold', color: '#111827', marginTop: 10 },
  subHeader: { fontSize: 13, color: '#6B7280', marginTop: 4, marginBottom: 16 },
  sampleRow: { flexDirection: 'row', gap: 8, marginBottom: 10 },
  sampleBtn: { backgroundColor: '#E5E7EB', paddingVertical: 6, paddingHorizontal: 10, borderRadius: 6 },
  sampleBtnText: { fontSize: 12, color: '#374151' },
  input: {
    backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#D1D5DB',
    borderRadius: 10, padding: 14, height: 120, textAlignVertical: 'top', fontSize: 15,
  },

  uploadBox: {
    backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#D1D5DB', borderStyle: 'dashed',
    borderRadius: 10, padding: 14, marginTop: 12,
  },
  uploadHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  uploadTitle: { fontSize: 15, fontWeight: 'bold', color: '#111827' },
  uploadCount: { fontSize: 12, color: '#6B7280' },
  uploadHint: { fontSize: 12, color: '#6B7280', marginTop: 4, lineHeight: 17 },
  uploadBtnRow: { flexDirection: 'row', gap: 8, marginTop: 10 },
  uploadBtn: {
    flex: 1, borderWidth: 1, borderColor: '#1B64DA', borderRadius: 8,
    paddingVertical: 10, alignItems: 'center',
  },
  uploadBtnText: { color: '#1B64DA', fontWeight: 'bold', fontSize: 13 },
  thumbRow: { marginTop: 12 },
  thumbWrap: { marginRight: 10, paddingTop: 6, paddingRight: 6 },
  thumb: { width: 76, height: 76, borderRadius: 8, backgroundColor: '#E5E7EB' },
  thumbRemove: {
    position: 'absolute', top: 0, right: 0, width: 22, height: 22, borderRadius: 11,
    backgroundColor: '#111827', alignItems: 'center', justifyContent: 'center',
  },
  thumbRemoveText: { color: '#FFFFFF', fontSize: 11, fontWeight: 'bold' },

  submitBtn: {
    backgroundColor: '#1B64DA', padding: 15, borderRadius: 10,
    alignItems: 'center', marginTop: 12,
  },
  submitBtnDisabled: { opacity: 0.6 },
  submitBtnText: { color: '#FFFFFF', fontWeight: 'bold', fontSize: 16 },
  resultBox: {
    backgroundColor: '#FFFFFF', borderRadius: 12, padding: 16, marginTop: 20,
    borderWidth: 1, borderColor: '#E5E7EB',
  },
  badgeRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 12 },
  badgePrimary: {
    backgroundColor: '#DBEAFE', color: '#1E40AF', fontWeight: 'bold',
    paddingHorizontal: 10, paddingVertical: 4, borderRadius: 6, fontSize: 13,
  },
  sectionTitle: { fontSize: 15, fontWeight: 'bold', color: '#111827', marginTop: 14, marginBottom: 6 },
  summaryWarn: { fontSize: 13, color: '#DC2626' },
  summaryOk: { fontSize: 13, color: '#15803D' },
  checkItem: { paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#F3F4F6' },
  checkItemMuted: { opacity: 0.6 },
  checkHeader: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  statusChip: {
    fontSize: 11, fontWeight: 'bold', paddingHorizontal: 8, paddingVertical: 2,
    borderRadius: 4, overflow: 'hidden',
  },
  checkLabel: { flex: 1, fontSize: 14, color: '#111827', fontWeight: '600' },
  checkEvidence: { fontSize: 12, color: '#6B7280', marginTop: 4, marginLeft: 2 },
  checkSuggestion: { fontSize: 13, color: '#B45309', marginTop: 3, marginLeft: 2, lineHeight: 18 },
  guideCard: { backgroundColor: '#F0FDF4', padding: 12, borderRadius: 8 },
  guideText: { fontSize: 14, color: '#166534', lineHeight: 20 },

  channelCard: { backgroundColor: '#F9FAFB', borderRadius: 8, padding: 12, borderWidth: 1, borderColor: '#E5E7EB' },
  channelAgency: { fontSize: 14, fontWeight: 'bold', color: '#111827', marginBottom: 8 },
  infoRow: { flexDirection: 'row', paddingVertical: 6, borderTopWidth: 1, borderTopColor: '#E5E7EB' },
  infoLabel: { width: 64, fontSize: 13, color: '#6B7280' },
  infoValue: { flex: 1, fontSize: 13, color: '#111827' },
  infoLink: { color: '#1B64DA', textDecorationLine: 'underline' },

  actionRow: { flexDirection: 'row', gap: 10, marginTop: 10 },
  linkBtn: { flex: 1, padding: 12, borderRadius: 8, alignItems: 'center' },
  linkBtnText: { color: '#FFFFFF', fontWeight: 'bold', fontSize: 13 },
});
