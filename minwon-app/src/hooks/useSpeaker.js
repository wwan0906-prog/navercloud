// ⑥ 음성 안내. 지금은 기기 내장 음성(expo-speech)으로 읽습니다.
// 백엔드 연동 시 CLOVA Voice 음성(mp3)을 재생하도록 speak 안쪽만 바꾸면 됩니다.
import { useCallback, useEffect, useState } from 'react';
import * as Speech from 'expo-speech';
import { getLanguage } from '../config';

export function useSpeaker() {
  // 지금 읽고 있는 항목의 key (버튼 상태 표시용)
  const [speakingKey, setSpeakingKey] = useState(null);

  const stop = useCallback(() => {
    Speech.stop();
    setSpeakingKey(null);
  }, []);

  useEffect(() => stop, [stop]);

  const speak = useCallback(
    (key, text, lang) => {
      Speech.stop();
      if (!text) return;
      setSpeakingKey(key);
      const done = () => setSpeakingKey((k) => (k === key ? null : k));
      Speech.speak(text, {
        language: getLanguage(lang).speech,
        onDone: done,
        onStopped: done,
        onError: done,
      });
    },
    []
  );

  const toggle = useCallback(
    (key, text, lang) => (speakingKey === key ? stop() : speak(key, text, lang)),
    [speakingKey, speak, stop]
  );

  return { speakingKey, toggle, stop };
}
