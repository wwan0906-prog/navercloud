import React, { useState } from 'react';
import {
  SafeAreaView, ScrollView, View, Text, TextInput,
  TouchableOpacity, ActivityIndicator, StyleSheet, Linking, Alert
} from 'react-native';

// 백엔드 서버 연동 시 USE_MOCK을 false로 바꾸고 실제 서버 주소를 입력하세요.
const USE_MOCK = true;
const API_URL = 'http://서버_공인_IP:8000/api/analyze';

const MOCK_RESPONSE = {
  main_category: '도로·시설물',
  sub_category: '가로등·보안등 고장 신고',
  extracted_info: {
    증상: '가로등 점등 불량',
    발생위치: '미기재',
  },
  validation: {
    status: '불충분',
    missing_fields: ['정확한 위치(도로명 주소 또는 주변 건물명)', '가로등 관리번호(선택)'],
  },
  guide_message:
    '보수팀이 현장을 바로 찾을 수 있도록 고장 난 가로등 위치(예: OO아파트 정문 앞)를 추가해 주세요.',
  official_channel: {
    agency: '안전신문고 공식 접수',
    url: 'https://www.safetyreport.go.kr',
    phone: '110',
  },
};

export default function App() {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const handleAnalyze = async () => {
    if (!text.trim()) {
      Alert.alert('알림', '민원 내용을 입력해 주세요.');
      return;
    }
    setLoading(true);
    setResult(null);

    try {
      if (USE_MOCK) {
        await new Promise((r) => setTimeout(r, 800));
        setResult(MOCK_RESPONSE);
      } else {
        const res = await fetch(API_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ complaint_text: text }),
        });
        const data = await res.json();
        setResult(data);
      }
    } catch (err) {
      Alert.alert('연결 오류', '백엔드 서버와 통신할 수 없습니다.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll}>
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

        <TouchableOpacity style={styles.submitBtn} onPress={handleAnalyze} disabled={loading}>
          <Text style={styles.submitBtnText}>민원 분석 및 보완 가이드 받기</Text>
        </TouchableOpacity>

        {loading && <ActivityIndicator size="large" color="#1B64DA" style={{ marginTop: 24 }} />}

        {/* 분석 결과 표시 */}
        {result && (
          <View style={styles.resultBox}>
            {/* 1. 분류 결과 */}
            <View style={styles.badgeRow}>
              <Text style={styles.badgePrimary}>{result.main_category}</Text>
              <Text style={styles.badgeSecondary}>{result.sub_category}</Text>
            </View>

            {/* 2. 누락·불충분 항목 검증 */}
            <Text style={styles.sectionTitle}>필수 정보 점검 ({result.validation.status})</Text>
            {result.validation.missing_fields.map((item, idx) => (
              <Text key={idx} style={styles.missingItem}>• 누락/보완 필요: {item}</Text>
            ))}

            {/* 3. 맞춤형 보완 안내문 */}
            <Text style={styles.sectionTitle}>맞춤형 보완 안내</Text>
            <View style={styles.guideCard}>
              <Text style={styles.guideText}>{result.guide_message}</Text>
            </View>

            {/* 4. 공식 접수 채널 */}
            <Text style={styles.sectionTitle}>공식 접수 채널 ({result.official_channel.agency})</Text>
            <View style={styles.actionRow}>
              <TouchableOpacity
                style={[styles.linkBtn, { backgroundColor: '#1B64DA' }]}
                onPress={() => Linking.openURL(result.official_channel.url)}
              >
                <Text style={styles.linkBtnText}>웹/앱 바로가기</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.linkBtn, { backgroundColor: '#0F9D58' }]}
                onPress={() => Linking.openURL(`tel:${result.official_channel.phone}`)}
              >
                <Text style={styles.linkBtnText}>전화 문의 ({result.official_channel.phone})</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F7FA' },
  scroll: { padding: 20 },
  header: { fontSize: 22, fontWeight: 'bold', color: '#111827', marginTop: 10 },
  subHeader: { fontSize: 13, color: '#6B7280', marginTop: 4, marginBottom: 16 },
  sampleRow: { flexDirection: 'row', gap: 8, marginBottom: 10 },
  sampleBtn: { backgroundColor: '#E5E7EB', paddingVertical: 6, paddingHorizontal: 10, borderRadius: 6 },
  sampleBtnText: { fontSize: 12, color: '#374151' },
  input: {
    backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#D1D5DB',
    borderRadius: 10, padding: 14, height: 120, textAlignVertical: 'top', fontSize: 15,
  },
  submitBtn: {
    backgroundColor: '#1B64DA', padding: 15, borderRadius: 10,
    alignItems: 'center', marginTop: 12,
  },
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
  badgeSecondary: {
    backgroundColor: '#F3F4F6', color: '#374151',
    paddingHorizontal: 10, paddingVertical: 4, borderRadius: 6, fontSize: 13,
  },
  sectionTitle: { fontSize: 15, fontWeight: 'bold', color: '#111827', marginTop: 14, marginBottom: 6 },
  missingItem: { fontSize: 13, color: '#DC2626', marginBottom: 4 },
  guideCard: { backgroundColor: '#F0FDF4', padding: 12, borderRadius: 8 },
  guideText: { fontSize: 14, color: '#166534', lineHeight: 20 },
  actionRow: { flexDirection: 'row', gap: 10, marginTop: 6 },
  linkBtn: { flex: 1, padding: 12, borderRadius: 8, alignItems: 'center' },
  linkBtnText: { color: '#FFFFFF', fontWeight: 'bold', fontSize: 13 },
});