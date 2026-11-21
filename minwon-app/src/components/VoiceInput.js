// ① 음성 입력: 녹음 → 서버(CLOVA Speech Recognition)로 글자 변환 → 입력창에 추가
import { useEffect, useRef, useState } from 'react';
import { Alert, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import {
  RecordingPresets, requestRecordingPermissionsAsync, setAudioModeAsync,
  useAudioRecorder, useAudioRecorderState,
} from 'expo-audio';
import { MAX_RECORDING_SEC } from '../config';
import { transcribeAudio } from '../api';
import { colors } from './ui';

const fmt = (sec) => `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`;

export default function VoiceInput({ lang, supported, disabled, onText, onBusyChange }) {
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const state = useAudioRecorderState(recorder, 250);
  const [converting, setConverting] = useState(false);
  const stoppingRef = useRef(false);
  const recording = state.isRecording;
  const elapsed = Math.floor((state.durationMillis || 0) / 1000);

  useEffect(() => {
    onBusyChange?.(recording || converting);
  }, [recording, converting]);

  const start = async () => {
    if (!supported) {
      Alert.alert('알림', '선택한 언어는 음성 입력을 지원하지 않습니다. 글로 입력해 주세요.');
      return;
    }
    const perm = await requestRecordingPermissionsAsync();
    if (!perm.granted) {
      Alert.alert('권한 필요', '음성으로 입력하려면 마이크 권한을 허용해 주세요.');
      return;
    }
    try {
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
      await recorder.prepareToRecordAsync();
      recorder.record();
    } catch {
      Alert.alert('오류', '녹음을 시작할 수 없습니다.');
    }
  };

  const stop = async () => {
    if (stoppingRef.current) return;
    stoppingRef.current = true;
    try {
      await recorder.stop();
    } catch {
      stoppingRef.current = false;
      return;
    } finally {
      // iOS에서 녹음 모드가 켜져 있으면 소리가 수화기로 나오므로 다시 끕니다.
      await setAudioModeAsync({ allowsRecording: false }).catch(() => {});
    }
    const uri = recorder.uri;
    stoppingRef.current = false;
    if (!uri) return;
    setConverting(true);
    try {
      const text = await transcribeAudio(uri, lang);
      if (text?.trim()) onText(text.trim());
      else Alert.alert('알림', '음성을 알아듣지 못했습니다. 다시 말씀해 주세요.');
    } catch (e) {
      Alert.alert('음성 인식 실패', e.message);
    } finally {
      setConverting(false);
    }
  };

  // CSR 길이 제한에 맞춰 자동 종료
  useEffect(() => {
    if (recording && elapsed >= MAX_RECORDING_SEC) stop();
  }, [recording, elapsed]);

  if (recording) {
    return (
      <TouchableOpacity style={[styles.btn, styles.recording]} onPress={stop}>
        <View style={styles.dot} />
        <Text style={styles.recText}>
          녹음 중 {fmt(elapsed)} / {fmt(MAX_RECORDING_SEC)} · 눌러서 끝내기
        </Text>
      </TouchableOpacity>
    );
  }

  return (
    <TouchableOpacity
      style={[styles.btn, (disabled || converting || !supported) && styles.disabled]}
      onPress={start}
      disabled={disabled || converting}
    >
      <Text style={styles.text}>{converting ? '음성을 글로 바꾸는 중...' : '🎤 음성으로 입력'}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  btn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    borderWidth: 1, borderColor: colors.primary, borderRadius: 8, paddingVertical: 11, backgroundColor: '#FFFFFF',
  },
  disabled: { opacity: 0.5 },
  text: { color: colors.primary, fontWeight: 'bold', fontSize: 14 },
  recording: { borderColor: colors.danger, backgroundColor: '#FEF2F2' },
  dot: { width: 10, height: 10, borderRadius: 5, backgroundColor: colors.danger },
  recText: { color: colors.danger, fontWeight: 'bold', fontSize: 13 },
});
