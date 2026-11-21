import { useState } from 'react';
import { Alert, Linking, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import {
  COMPLAINT_TYPES, CONSISTENCY_META, FIELD_STATUS_META, FIELD_STATUS_ORDER,
  RECEIPT_STATUS_META, URGENCY_META, getLanguage,
} from '../config';
import { Button, Card, Chip, SpeakButton, StepTitle, colors } from './ui';

function openLink(url) {
  Linking.openURL(url).catch(() => Alert.alert('알림', '링크를 열 수 없습니다.'));
}

// 외국어 민원의 한국어 번역 (Papago)
export function TranslationCard({ original, translated, lang }) {
  if (!translated) return null;
  return (
    <Card>
      <StepTitle step="①" title="한국어 번역" right={<Chip label={`${getLanguage(lang).label} → 한국어`} />} />
      <Text style={styles.label}>원문</Text>
      <Text style={styles.muted}>{original}</Text>
      <Text style={[styles.label, { marginTop: 8 }]}>번역</Text>
      <Text style={styles.body}>{translated}</Text>
    </Card>
  );
}

// 생명·안전 위험 시 즉시 신고 안내
export function UrgentBanner() {
  return (
    <View style={styles.urgent}>
      <Text style={styles.urgentTitle}>⚠ 긴급 민원으로 분류되었습니다</Text>
      <Text style={styles.urgentText}>
        생명이나 안전이 위험하면 민원 접수보다 먼저 119(화재·가스·구조) 또는 112(범죄·사고)에 신고하세요.
      </Text>
      <View style={styles.urgentRow}>
        <Button title="119 전화" color={colors.danger} style={{ flex: 1 }} onPress={() => openLink('tel:119')} />
        <Button title="112 전화" color={colors.danger} variant="outline" style={{ flex: 1 }} onPress={() => openLink('tel:112')} />
      </View>
    </View>
  );
}

// ② 분류 결과: 부서 · 유형 · 긴급도 · 요약
export function ClassificationCard({ classification }) {
  if (!classification) return null;
  const { 부서, 유형, 긴급도, 요약 } = classification;
  const urgency = URGENCY_META[긴급도];
  return (
    <Card>
      <StepTitle step="②" title="민원 분류" />
      <View style={styles.grid}>
        <View style={styles.cell}>
          <Text style={styles.label}>담당 부서</Text>
          <Text style={styles.value}>{부서}</Text>
        </View>
        <View style={styles.cell}>
          <Text style={styles.label}>유형</Text>
          <Text style={styles.value}>{유형}</Text>
          {COMPLAINT_TYPES[유형] ? <Text style={styles.hint}>{COMPLAINT_TYPES[유형]}</Text> : null}
        </View>
        <View style={styles.cell}>
          <Text style={styles.label}>긴급도</Text>
          {urgency ? <Chip label={긴급도} color={urgency.color} bg={urgency.bg} style={{ marginTop: 2 }} /> : <Text style={styles.value}>{긴급도}</Text>}
          {urgency ? <Text style={styles.hint}>{urgency.desc}</Text> : null}
        </View>
      </View>
      {요약 ? (
        <View style={styles.summary}>
          <Text style={styles.label}>요약</Text>
          <Text style={styles.body}>{요약}</Text>
        </View>
      ) : null}
    </Card>
  );
}

// ③ 답변 초안 + ④ 규정 모순 검사 + ⑥ 역번역·음성 안내
export function AnswerCard({ analysis, lang, speaker }) {
  const foreign = lang !== 'ko' && !!analysis.answer_translated;
  const [showForeign, setShowForeign] = useState(foreign);
  const shownLang = foreign && showForeign ? lang : 'ko';
  const text = shownLang === 'ko' ? analysis.answer_draft : analysis.answer_translated;
  const c = analysis.consistency;
  const meta = c ? CONSISTENCY_META[c.result] : null;

  return (
    <Card>
      <StepTitle
        step="③"
        title="답변 초안"
        right={<SpeakButton active={speaker.speakingKey === 'answer'} onPress={() => speaker.toggle('answer', text, shownLang)} />}
      />
      {foreign && (
        <View style={styles.tabs}>
          {[
            { key: true, label: getLanguage(lang).label },
            { key: false, label: '한국어' },
          ].map((t) => (
            <TouchableOpacity
              key={t.label}
              style={[styles.tab, showForeign === t.key && styles.tabActive]}
              onPress={() => {
                speaker.stop();
                setShowForeign(t.key);
              }}
            >
              <Text style={[styles.tabText, showForeign === t.key && styles.tabTextActive]}>{t.label}</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}
      <Text style={styles.answer}>{text}</Text>
      <Text style={styles.hint}>AI가 작성한 초안이며, 담당 공무원 검토 후 확정됩니다.</Text>

      {c && (
        <View style={styles.check}>
          <View style={styles.checkHead}>
            <Text style={styles.checkTitle}>④ 규정 검사</Text>
            {meta ? <Chip label={meta.label} color={meta.color} bg={meta.bg} /> : <Chip label={c.result} />}
          </View>
          {(c.evidence ?? []).map((ev, i) => (
            <View key={i} style={styles.evidence}>
              <Text style={styles.evidenceSource}>근거: {ev.source}</Text>
              {ev.text ? <Text style={styles.evidenceText}>“{ev.text}”</Text> : null}
            </View>
          ))}
          {c.reason ? <Text style={styles.muted}>{c.reason}</Text> : null}
        </View>
      )}
    </Card>
  );
}

// 필수 정보 점검 (누락·불충분 항목 + 보완 안내)
export function FieldChecksCard({ checks, guideMessage }) {
  if (!checks?.length && !guideMessage) return null;
  const sorted = [...(checks ?? [])].sort(
    (a, b) => (FIELD_STATUS_ORDER[a.status] ?? 9) - (FIELD_STATUS_ORDER[b.status] ?? 9)
  );
  const needsFix = sorted.filter((c) => c.status === 'missing' || c.status === 'insufficient').length;
  return (
    <Card>
      <StepTitle
        title="필수 정보 점검"
        right={
          <Chip
            label={needsFix ? `보완 필요 ${needsFix}건` : '모두 충족'}
            color={needsFix ? colors.danger : '#15803D'}
            bg={needsFix ? '#FEE2E2' : '#DCFCE7'}
          />
        }
      />
      {sorted.map((c) => {
        const meta = FIELD_STATUS_META[c.status] ?? FIELD_STATUS_META.missing;
        const muted = c.status === 'not_applicable';
        return (
          <View key={c.key} style={[styles.field, muted && { opacity: 0.6 }]}>
            <View style={styles.fieldHead}>
              <Chip label={meta.label} color={meta.color} bg={meta.bg} />
              <Text style={styles.fieldLabel}>{c.label}</Text>
            </View>
            {c.evidence && !muted ? <Text style={styles.muted}>원문: “{c.evidence}”</Text> : null}
            {c.suggestion && !muted ? <Text style={styles.suggestion}>→ {c.suggestion}</Text> : null}
          </View>
        );
      })}
      {guideMessage ? (
        <View style={styles.guide}>
          <Text style={styles.guideText}>{guideMessage}</Text>
        </View>
      ) : null}
      {needsFix ? <Text style={styles.hint}>위 내용을 입력창에 보완한 뒤 다시 분석하면 더 정확해집니다.</Text> : null}
    </Card>
  );
}

// ⑤ 접수 결과
export function ReceiptCard({ receipt, speaker }) {
  const meta = RECEIPT_STATUS_META[receipt.status] ?? { label: receipt.status, color: colors.text, bg: '#F3F4F6' };
  const spoken = `접수번호 ${receipt.receipt_no.split('').map((ch) => (ch === '-' ? ',' : ch)).join(' ')}.${receipt.department} 부서로 ${meta.label}. ${receipt.message ?? ''}`;
  return (
    <Card style={styles.receipt}>
      <StepTitle
        step="⑤"
        title="접수 결과"
        right={<SpeakButton active={speaker.speakingKey === 'receipt'} onPress={() => speaker.toggle('receipt', spoken, 'ko')} />}
      />
      <Text style={styles.label}>접수번호</Text>
      <Text style={styles.receiptNo} selectable>{receipt.receipt_no}</Text>
      <View style={styles.receiptRow}>
        <Text style={styles.label}>배정 부서</Text>
        <Text style={styles.value}>{receipt.department}</Text>
      </View>
      <View style={styles.receiptRow}>
        <Text style={styles.label}>처리 상태</Text>
        <Chip label={meta.label} color={meta.color} bg={meta.bg} />
      </View>
      {receipt.message ? <Text style={[styles.body, { marginTop: 8 }]}>{receipt.message}</Text> : null}
    </Card>
  );
}

// 공식 접수 채널: 카테고리 · 웹사이트 · 전화번호
export function ChannelCard({ channel, department }) {
  if (!channel) return null;
  return (
    <Card>
      <StepTitle title="공식 접수 채널" />
      {channel.agency ? <Text style={styles.agency}>{channel.agency}</Text> : null}
      <View style={styles.infoRow}>
        <Text style={styles.infoLabel}>카테고리</Text>
        <Text style={styles.infoValue}>{department}</Text>
      </View>
      {channel.url ? (
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>웹사이트</Text>
          <Text style={[styles.infoValue, styles.link]} onPress={() => openLink(channel.url)}>{channel.url}</Text>
        </View>
      ) : null}
      {channel.phone ? (
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>전화번호</Text>
          <Text style={[styles.infoValue, styles.link]} onPress={() => openLink(`tel:${channel.phone}`)}>{channel.phone}</Text>
        </View>
      ) : null}
      <View style={styles.actionRow}>
        {channel.url ? <Button title="웹/앱 바로가기" style={{ flex: 1 }} onPress={() => openLink(channel.url)} /> : null}
        {channel.phone ? (
          <Button title="전화 걸기" color={colors.success} style={{ flex: 1 }} onPress={() => openLink(`tel:${channel.phone}`)} />
        ) : null}
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  label: { fontSize: 12, color: colors.sub },
  value: { fontSize: 15, fontWeight: 'bold', color: colors.text, marginTop: 2 },
  hint: { fontSize: 11, color: colors.sub, marginTop: 4, lineHeight: 15 },
  body: { fontSize: 14, color: colors.text, lineHeight: 20, marginTop: 2 },
  muted: { fontSize: 12, color: colors.sub, marginTop: 3, lineHeight: 17 },

  urgent: { backgroundColor: '#FEF2F2', borderWidth: 1, borderColor: '#FCA5A5', borderRadius: 12, padding: 14, marginTop: 14 },
  urgentTitle: { fontSize: 15, fontWeight: 'bold', color: '#B91C1C' },
  urgentText: { fontSize: 13, color: '#7F1D1D', marginTop: 4, lineHeight: 19 },
  urgentRow: { flexDirection: 'row', gap: 8, marginTop: 10 },

  grid: { flexDirection: 'row', gap: 8 },
  cell: { flex: 1, backgroundColor: '#F9FAFB', borderRadius: 8, padding: 10 },
  summary: { marginTop: 10, backgroundColor: '#F9FAFB', borderRadius: 8, padding: 10 },

  tabs: { flexDirection: 'row', backgroundColor: '#F3F4F6', borderRadius: 8, padding: 3, marginBottom: 10 },
  tab: { flex: 1, paddingVertical: 6, borderRadius: 6, alignItems: 'center' },
  tabActive: { backgroundColor: '#FFFFFF' },
  tabText: { fontSize: 13, color: colors.sub },
  tabTextActive: { color: colors.text, fontWeight: 'bold' },
  answer: { fontSize: 15, color: colors.text, lineHeight: 23 },

  check: { marginTop: 12, paddingTop: 12, borderTopWidth: 1, borderTopColor: colors.border },
  checkHead: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  checkTitle: { fontSize: 14, fontWeight: 'bold', color: colors.text },
  evidence: { marginTop: 8, borderLeftWidth: 3, borderLeftColor: '#BFDBFE', paddingLeft: 8 },
  evidenceSource: { fontSize: 12, fontWeight: 'bold', color: '#1E40AF' },
  evidenceText: { fontSize: 12, color: '#374151', marginTop: 2, lineHeight: 17 },

  field: { paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#F3F4F6' },
  fieldHead: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  fieldLabel: { flex: 1, fontSize: 14, fontWeight: '600', color: colors.text },
  suggestion: { fontSize: 13, color: '#B45309', marginTop: 3, lineHeight: 18 },
  guide: { backgroundColor: '#F0FDF4', padding: 12, borderRadius: 8, marginTop: 10 },
  guideText: { fontSize: 14, color: '#166534', lineHeight: 20 },

  receipt: { borderColor: '#86EFAC', backgroundColor: '#F7FEF9' },
  receiptNo: { fontSize: 22, fontWeight: 'bold', color: colors.text, letterSpacing: 1, marginTop: 2, marginBottom: 6 },
  receiptRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 6, borderTopWidth: 1, borderTopColor: colors.border },

  agency: { fontSize: 14, fontWeight: 'bold', color: colors.text, marginBottom: 6 },
  infoRow: { flexDirection: 'row', paddingVertical: 7, borderTopWidth: 1, borderTopColor: colors.border },
  infoLabel: { width: 64, fontSize: 13, color: colors.sub },
  infoValue: { flex: 1, fontSize: 13, color: colors.text },
  link: { color: colors.primary, textDecorationLine: 'underline' },
  actionRow: { flexDirection: 'row', gap: 10, marginTop: 10 },
});
