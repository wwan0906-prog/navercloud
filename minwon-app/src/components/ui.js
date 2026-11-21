import { ActivityIndicator, StyleSheet, Text, TouchableOpacity, View } from 'react-native';

export const colors = {
  primary: '#1B64DA',
  text: '#111827',
  sub: '#6B7280',
  border: '#E5E7EB',
  bg: '#F5F7FA',
  danger: '#DC2626',
  success: '#0F9D58',
};

export function Card({ children, style }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

export function StepTitle({ step, title, right }) {
  return (
    <View style={styles.stepRow}>
      {step ? <Text style={styles.stepNo}>{step}</Text> : null}
      <Text style={styles.stepTitle}>{title}</Text>
      {right ? <View style={styles.stepRight}>{right}</View> : null}
    </View>
  );
}

export function Chip({ label, color = colors.text, bg = '#F3F4F6', style }) {
  return <Text style={[styles.chip, { color, backgroundColor: bg }, style]}>{label}</Text>;
}

export function Button({ title, onPress, variant = 'primary', disabled, loading, style, color }) {
  const tint = color ?? colors.primary;
  const filled = variant === 'primary';
  return (
    <TouchableOpacity
      style={[
        styles.btn,
        filled ? { backgroundColor: tint } : { borderWidth: 1, borderColor: tint, backgroundColor: '#FFFFFF' },
        (disabled || loading) && styles.btnDisabled,
        style,
      ]}
      onPress={onPress}
      disabled={disabled || loading}
      accessibilityRole="button"
    >
      {loading ? (
        <ActivityIndicator color={filled ? '#FFFFFF' : tint} />
      ) : (
        <Text style={[styles.btnText, { color: filled ? '#FFFFFF' : tint }]}>{title}</Text>
      )}
    </TouchableOpacity>
  );
}

// 음성으로 듣기 / 멈추기 토글 버튼
export function SpeakButton({ active, onPress }) {
  return (
    <TouchableOpacity onPress={onPress} style={[styles.speak, active && styles.speakActive]} hitSlop={6}>
      <Text style={[styles.speakText, active && styles.speakTextActive]}>
        {active ? '■ 멈추기' : '🔊 듣기'}
      </Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#FFFFFF', borderRadius: 12, padding: 16, marginTop: 14,
    borderWidth: 1, borderColor: colors.border,
  },
  stepRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 10, gap: 8 },
  stepNo: {
    width: 22, height: 22, borderRadius: 11, backgroundColor: colors.primary, color: '#FFFFFF',
    textAlign: 'center', lineHeight: 22, fontSize: 12, fontWeight: 'bold', overflow: 'hidden',
  },
  stepTitle: { fontSize: 16, fontWeight: 'bold', color: colors.text, flexShrink: 1 },
  stepRight: { marginLeft: 'auto' },
  chip: {
    fontSize: 12, fontWeight: 'bold', paddingHorizontal: 9, paddingVertical: 3,
    borderRadius: 6, overflow: 'hidden', alignSelf: 'flex-start',
  },
  btn: { paddingVertical: 13, paddingHorizontal: 12, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  btnDisabled: { opacity: 0.5 },
  btnText: { fontWeight: 'bold', fontSize: 15 },
  speak: {
    borderWidth: 1, borderColor: colors.border, borderRadius: 14,
    paddingHorizontal: 10, paddingVertical: 4, backgroundColor: '#FFFFFF',
  },
  speakActive: { borderColor: colors.primary, backgroundColor: '#EFF6FF' },
  speakText: { fontSize: 12, color: colors.text },
  speakTextActive: { color: colors.primary, fontWeight: 'bold' },
});
