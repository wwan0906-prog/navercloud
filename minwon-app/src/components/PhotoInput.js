// ① 문서 사진 입력: 촬영/앨범 → 서버(CLOVA OCR)로 글자 인식 → 입력창에 추가
import { Alert, Image, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { MAX_IMAGES } from '../config';
import { recognizeImage } from '../api';
import { colors } from './ui';

// photos: [{ uri, asset, status: 'loading' | 'done' | 'error' }]
export default function PhotoInput({ photos, setPhotos, disabled, onText }) {
  const updatePhoto = (uri, patch) =>
    setPhotos((prev) => prev.map((p) => (p.uri === uri ? { ...p, ...patch } : p)));

  const runOcr = async (asset) => {
    updatePhoto(asset.uri, { status: 'loading' });
    try {
      const text = await recognizeImage(asset);
      updatePhoto(asset.uri, { status: 'done' });
      if (text?.trim()) onText(text.trim());
      else Alert.alert('알림', '사진에서 글자를 찾지 못했습니다. 더 밝고 가깝게 찍어 주세요.');
    } catch (e) {
      updatePhoto(asset.uri, { status: 'error' });
      Alert.alert('글자 인식 실패', e.message);
    }
  };

  const addAssets = (assets) => {
    const room = MAX_IMAGES - photos.length;
    if (assets.length > room) Alert.alert('알림', `사진은 최대 ${MAX_IMAGES}장까지 첨부할 수 있습니다.`);
    const accepted = assets.slice(0, room);
    setPhotos((prev) => [...prev, ...accepted.map((a) => ({ uri: a.uri, asset: a, status: 'loading' }))]);
    accepted.forEach(runOcr);
  };

  const checkRoom = () => {
    if (photos.length >= MAX_IMAGES) {
      Alert.alert('알림', `사진은 최대 ${MAX_IMAGES}장까지 첨부할 수 있습니다.`);
      return false;
    }
    return true;
  };

  const takePhoto = async () => {
    if (!checkRoom()) return;
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) {
      Alert.alert('권한 필요', '문서를 촬영하려면 카메라 권한을 허용해 주세요.');
      return;
    }
    const shot = await ImagePicker.launchCameraAsync({ mediaTypes: ['images'], quality: 0.8 });
    if (!shot.canceled) addAssets(shot.assets);
  };

  const pickFromLibrary = async () => {
    if (!checkRoom()) return;
    const picked = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsMultipleSelection: true,
      selectionLimit: MAX_IMAGES - photos.length,
      quality: 0.8,
    });
    if (!picked.canceled) addAssets(picked.assets);
  };

  return (
    <View>
      <View style={styles.row}>
        <TouchableOpacity style={[styles.btn, disabled && styles.disabled]} onPress={takePhoto} disabled={disabled}>
          <Text style={styles.btnText}>📷 문서 촬영</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.btn, disabled && styles.disabled]} onPress={pickFromLibrary} disabled={disabled}>
          <Text style={styles.btnText}>🖼 앨범에서 선택</Text>
        </TouchableOpacity>
      </View>

      {photos.length > 0 && (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.thumbRow}>
          {photos.map((p) => (
            <View key={p.uri} style={styles.thumbWrap}>
              <Image source={{ uri: p.uri }} style={styles.thumb} />
              <Text
                style={[styles.thumbStatus, p.status === 'error' && styles.thumbError]}
                onPress={p.status === 'error' ? () => runOcr(p.asset) : undefined}
              >
                {p.status === 'loading' ? '인식 중...' : p.status === 'error' ? '다시 시도' : '인식 완료'}
              </Text>
              <TouchableOpacity
                style={styles.remove}
                onPress={() => setPhotos((prev) => prev.filter((x) => x.uri !== p.uri))}
                hitSlop={8}
              >
                <Text style={styles.removeText}>✕</Text>
              </TouchableOpacity>
            </View>
          ))}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', gap: 8 },
  btn: {
    flex: 1, borderWidth: 1, borderColor: colors.primary, borderRadius: 8,
    paddingVertical: 11, alignItems: 'center', backgroundColor: '#FFFFFF',
  },
  disabled: { opacity: 0.5 },
  btnText: { color: colors.primary, fontWeight: 'bold', fontSize: 14 },
  thumbRow: { marginTop: 10 },
  thumbWrap: { marginRight: 10, paddingTop: 6, paddingRight: 6, alignItems: 'center' },
  thumb: { width: 72, height: 72, borderRadius: 8, backgroundColor: colors.border },
  thumbStatus: { fontSize: 11, color: colors.sub, marginTop: 3 },
  thumbError: { color: colors.danger, textDecorationLine: 'underline' },
  remove: {
    position: 'absolute', top: 0, right: 0, width: 22, height: 22, borderRadius: 11,
    backgroundColor: colors.text, alignItems: 'center', justifyContent: 'center',
  },
  removeText: { color: '#FFFFFF', fontSize: 11, fontWeight: 'bold' },
});
