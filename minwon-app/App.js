import { useRef, useState } from 'react';
import { Alert, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';

import { LANGUAGES, formatCategory, getLanguage, isUrgent } from './src/config';
import { SAMPLES } from './src/mock';
import { analyzeComplaint, submitComplaint } from './src/api';
import { useSpeaker } from './src/hooks/useSpeaker';
import { Button, Card, StepTitle, colors } from './src/components/ui';
import VoiceInput from './src/components/VoiceInput';
import PhotoInput from './src/components/PhotoInput';
import {
  AnswerCard, ChannelCard, ClassificationCard, FieldChecksCard,
  ReceiptCard, TranslationCard, UrgentBanner,
} from './src/components/Results';

const MAX_TEXT = 2000;
const STAGES = ['입력', '분류', '답변', '검사', '접수', '안내'];

export default function App() {
  const [lang, setLang] = useState('ko');
  const [text, setText] = useState('');
  const [photos, setPhotos] = useState([]);
  const [voiceBusy, setVoiceBusy] = useState(false);

  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [analyzedInput, setAnalyzedInput] = useState(null); // 분석에 사용한 { text, lang }
  const [analysisId, setAnalysisId] = useState(0);

  const [submitting, setSubmitting] = useState(false);
  const [receipt, setReceipt] = useState(null);

  const speaker = useSpeaker();
  const scrollRef = useRef(null);
  const resultY = useRef(0);

  const language = getLanguage(lang);
  const ocrBusy = photos.some((p) => p.status === 'loading');
  const inputBusy = voiceBusy || ocrBusy;
  const stale = !!analysis && (analyzedInput?.text !== text.trim() || analyzedInput?.lang !== lang);
  const urgent = isUrgent(analysis?.classification);

  const stage = receipt ? 5 : analysis ? 3 : 0;

  // 음성·사진에서 인식한 글자를 입력창 끝에 이어 붙임 (사용자가 직접 고칠 수 있음)
  const appendText = (t) =>
    setText((prev) => {
      const base = prev.trim();
      return (base ? `${base}\n${t}` : t).slice(0, MAX_TEXT);
    });

  // 필수 정보 점검에서 입력한 보완 내용을 민원 입력창에 반영 (선택: 바로 다시 분석)
  const applySupplement = (lines, reanalyze) => {
    if (!lines.length) return;
    const base = text.trim();
    const next = [base, ...lines].filter(Boolean).join('\n').slice(0, MAX_TEXT);
    setText(next);
    if (reanalyze) handleAnalyze(next);
    else scrollRef.current?.scrollTo({ y: 0, animated: true });
  };

  const handleAnalyze = async (override) => {
    const input = (typeof override === 'string' ? override : text).trim();
    if (!input) {
      Alert.alert('알림', '민원 내용을 입력하거나 음성·문서 사진으로 추가해 주세요.');
      return;
    }
    speaker.stop();
    setAnalyzing(true);
    setReceipt(null);
    try {
      const result = await analyzeComplaint(input, lang);
      setAnalysis(result);
      setAnalyzedInput({ text: input, lang });
      setAnalysisId((n) => n + 1);
      setTimeout(() => scrollRef.current?.scrollTo({ y: resultY.current - 12, animated: true }), 150);
    } catch (e) {
      Alert.alert('분석 실패', e.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const r = await submitComplaint(analyzedInput.text, analyzedInput.lang, analysis);
      setReceipt(r);
    } catch (e) {
      Alert.alert('접수 실패', e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const reset = () => {
    speaker.stop();
    setText('');
    setPhotos([]);
    setAnalysis(null);
    setAnalyzedInput(null);
    setReceipt(null);
    scrollRef.current?.scrollTo({ y: 0, animated: true });
  };

  const fillSample = (s) => {
    setLang(s.lang);
    setText(s.text);
  };

  return (
    <SafeAreaProvider>
      <StatusBar style="dark" />
      <SafeAreaView style={styles.container} edges={['top', 'left', 'right']}>
        <ScrollView
          ref={scrollRef}
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled"
          automaticallyAdjustKeyboardInsets
        >
          <Text style={styles.header}>AI 민원 창구</Text>
          <Text style={styles.subHeader}>
            글·음성·사진·외국어로 민원을 넣으면 AI가 분류하고, 규정에 맞는 답변 초안을 만들어 접수까지 도와드립니다.
          </Text>

          {/* 백엔드 연동 후 삭제 */}
          <View style={styles.mockBanner}>
            <Text style={styles.mockText}>목업 모드 · 서버 연결 전 예시 데이터로 동작합니다</Text>
          </View>

          {/* 진행 단계 */}
          <View style={styles.stages}>
            {STAGES.map((s, i) => (
              <View key={s} style={styles.stageItem}>
                <View style={[styles.stageDot, i <= stage && styles.stageDotOn]} />
                <Text style={[styles.stageText, i <= stage && styles.stageTextOn]}>{s}</Text>
              </View>
            ))}
          </View>

          {/* ① 입력 */}
          <Card>
            <StepTitle step="①" title="민원 입력" />

            <Text style={styles.fieldLabel}>입력 언어</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.langRow}>
              {LANGUAGES.map((l) => (
                <TouchableOpacity
                  key={l.code}
                  style={[styles.langChip, lang === l.code && styles.langChipOn]}
                  onPress={() => setLang(l.code)}
                  disabled={inputBusy}
                >
                  <Text style={[styles.langText, lang === l.code && styles.langTextOn]}>{l.label}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
            {lang !== 'ko' && (
              <Text style={styles.hint}>외국어 민원은 한국어로 번역해 처리하고, 답변은 {language.label}로 다시 번역해 드립니다.</Text>
            )}

            <Text style={[styles.fieldLabel, { marginTop: 12 }]}>예시로 채우기</Text>
            <View style={styles.sampleRow}>
              {SAMPLES.map((s) => (
                <TouchableOpacity key={s.label} style={styles.sampleBtn} onPress={() => fillSample(s)} disabled={inputBusy}>
                  <Text style={styles.sampleBtnText}>{s.label}</Text>
                </TouchableOpacity>
              ))}
            </View>

            <TextInput
              style={styles.input}
              multiline
              placeholder={language.placeholder}
              placeholderTextColor="#9CA3AF"
              value={text}
              onChangeText={setText}
              maxLength={MAX_TEXT}
              editable={!analyzing}
            />
            <View style={styles.inputFoot}>
              <Text style={styles.hint}>음성·사진에서 인식한 글자는 입력창에 추가되며 직접 고칠 수 있어요.</Text>
              <Text style={styles.count}>{text.length}/{MAX_TEXT}</Text>
            </View>

            <View style={{ marginTop: 10 }}>
              <VoiceInput
                lang={lang}
                disabled={analyzing || ocrBusy}
                onText={appendText}
                onBusyChange={setVoiceBusy}
              />
            </View>
            <View style={{ marginTop: 8 }}>
              <PhotoInput photos={photos} setPhotos={setPhotos} disabled={analyzing || voiceBusy} onText={appendText} />
            </View>
          </Card>

          <Button
            title={analysis && !stale ? '다시 분석하기' : 'AI 분석 받기'}
            onPress={() => handleAnalyze()}
            loading={analyzing}
            disabled={inputBusy || !text.trim()}
            style={{ marginTop: 14 }}
          />
          {analyzing && <Text style={styles.loadingText}>분류 → 답변 초안 작성 → 규정 검사 중입니다...</Text>}

          {/* 결과 */}
          {analysis && (
            <View onLayout={(e) => (resultY.current = e.nativeEvent.layout.y)}>
              {stale && (
                <View style={styles.stale}>
                  <Text style={styles.staleText}>입력 내용이 바뀌었습니다. 다시 분석해야 접수할 수 있어요.</Text>
                </View>
              )}

              <TranslationCard original={analyzedInput.text} translated={analysis.translated_text} lang={analyzedInput.lang} />
              {urgent && <UrgentBanner />}
              <ClassificationCard classification={analysis.classification} />
              <AnswerCard key={analysisId} analysis={analysis} lang={analyzedInput.lang} speaker={speaker} />
              <FieldChecksCard
                key={`checks-${analysisId}`}
                checks={analysis.field_checks}
                guideMessage={analysis.guide_message}
                onApply={applySupplement}
                disabled={analyzing || !!receipt}
              />

              {/* ⑤ 접수 */}
              {receipt ? (
                <ReceiptCard receipt={receipt} speaker={speaker} />
              ) : (
                <Card>
                  <StepTitle step="⑤" title="접수하기" />
                  <Text style={styles.body}>
                    위 분류와 답변 초안으로 민원을 접수합니다. 접수번호가 발급되고 {analysis.classification?.분야} 분야 담당으로 배정됩니다.
                  </Text>
                  {urgent && (
                    <Text style={styles.urgentNote}>긴급 민원은 자동 처리하지 않고 담당자가 확인한 뒤 처리합니다.</Text>
                  )}
                  <Button
                    title="이 내용으로 접수하기"
                    onPress={handleSubmit}
                    loading={submitting}
                    disabled={stale || analyzing}
                    style={{ marginTop: 12 }}
                  />
                </Card>
              )}

              <ChannelCard channel={analysis.official_channel} department={formatCategory(analysis.classification)} />

              <Button title="새 민원 작성" variant="outline" onPress={reset} style={{ marginTop: 16 }} />
            </View>
          )}
        </ScrollView>
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  scroll: { padding: 20, paddingBottom: 48 },
  header: { fontSize: 24, fontWeight: 'bold', color: colors.text, marginTop: 6 },
  subHeader: { fontSize: 13, color: colors.sub, marginTop: 4, lineHeight: 19 },

  mockBanner: { backgroundColor: '#FEF9C3', borderRadius: 8, paddingVertical: 6, paddingHorizontal: 10, marginTop: 12 },
  mockText: { fontSize: 12, color: '#854D0E' },

  stages: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 16, paddingHorizontal: 4 },
  stageItem: { alignItems: 'center', flex: 1 },
  stageDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: '#D1D5DB' },
  stageDotOn: { backgroundColor: colors.primary },
  stageText: { fontSize: 11, color: '#9CA3AF', marginTop: 4 },
  stageTextOn: { color: colors.primary, fontWeight: 'bold' },

  fieldLabel: { fontSize: 12, color: colors.sub, marginBottom: 6 },
  hint: { fontSize: 11, color: colors.sub, marginTop: 6, lineHeight: 15, flexShrink: 1 },
  body: { fontSize: 14, color: colors.text, lineHeight: 20 },

  langRow: { flexGrow: 0 },
  langChip: {
    borderWidth: 1, borderColor: '#D1D5DB', borderRadius: 16, paddingVertical: 6, paddingHorizontal: 12,
    marginRight: 6, backgroundColor: '#FFFFFF',
  },
  langChipOn: { borderColor: colors.primary, backgroundColor: '#EFF6FF' },
  langText: { fontSize: 13, color: '#374151' },
  langTextOn: { color: colors.primary, fontWeight: 'bold' },

  sampleRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 10 },
  sampleBtn: { backgroundColor: '#E5E7EB', paddingVertical: 6, paddingHorizontal: 10, borderRadius: 6 },
  sampleBtnText: { fontSize: 12, color: '#374151' },

  input: {
    backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#D1D5DB', color: colors.text,
    borderRadius: 10, padding: 14, minHeight: 130, textAlignVertical: 'top', fontSize: 15, lineHeight: 21,
  },
  inputFoot: { flexDirection: 'row', justifyContent: 'space-between', gap: 8 },
  count: { fontSize: 11, color: '#9CA3AF', marginTop: 6 },

  loadingText: { fontSize: 12, color: colors.sub, textAlign: 'center', marginTop: 8 },

  stale: { backgroundColor: '#FFF7ED', borderWidth: 1, borderColor: '#FDBA74', borderRadius: 8, padding: 10, marginTop: 14 },
  staleText: { fontSize: 13, color: '#9A3412' },
  urgentNote: { fontSize: 13, color: '#B91C1C', marginTop: 8, fontWeight: '600' },
});
