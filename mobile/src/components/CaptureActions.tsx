import { useState } from 'react';
import { Alert, Image, Pressable, StyleSheet, Text, View } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { AudioModule, RecordingPresets, useAudioRecorder, useAudioRecorderState } from 'expo-audio';
import { Images, Square, Circle } from 'lucide-react-native';

import { colors } from './ui';
import { createDirectUploadUrl, uploadFile } from '../lib/api';
import { supabase } from '../lib/supabase';

export function CaptureActions({
  disabled = false,
  onMediaUploaded,
}: {
  disabled?: boolean;
  onMediaUploaded: (mediaItemId: string, mediaType: 'audio' | 'image') => void;
}) {
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const state = useAudioRecorderState(recorder);
  const [stage, setStage] = useState<
    'idle' | 'creating' | 'uploading' | 'ready' | 'failed'
  >('idle');
  const [activeMedia, setActiveMedia] = useState<'audio' | 'image' | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [photoPreviews, setPhotoPreviews] = useState<
    { key: string; uri: string; status: 'uploading' | 'ready' | 'failed' }[]
  >([]);

  async function upload(
    uri: string,
    mediaType: 'audio' | 'image',
    contentType: string,
    extension: string,
    photoKey?: string,
  ) {
    const { data } = await supabase.auth.getSession();
    if (!data.session) return Alert.alert('Sign in is required before uploading a capture.');
    setActiveMedia(mediaType);
    setErrorMessage(null);
    setUploadProgress(null);
    setStage('creating');
    try {
      const target = await createDirectUploadUrl(data.session, {
        media_type: mediaType,
        file_extension: extension,
        content_type: contentType,
      });
      setStage('uploading');
      await uploadFile(target.signed_url, uri, contentType, setUploadProgress);
      onMediaUploaded(target.media_item_id, mediaType);
      if (photoKey)
        setPhotoPreviews((current) =>
          current.map((item) => (item.key === photoKey ? { ...item, status: 'ready' } : item)),
        );
      setStage('ready');
    } catch (error) {
      if (photoKey)
        setPhotoPreviews((current) =>
          current.map((item) => (item.key === photoKey ? { ...item, status: 'failed' } : item)),
        );
      setErrorMessage(error instanceof Error ? error.message : 'The upload could not finish.');
      setStage('failed');
    }
  }

  async function record() {
    if (state.isRecording) {
      await recorder.stop();
      if (recorder.uri) await upload(recorder.uri, 'audio', 'audio/mp4', 'm4a');
      return;
    }
    const permission = await AudioModule.requestRecordingPermissionsAsync();
    if (!permission.granted)
      return Alert.alert('Microphone access is needed to record a voice note.');
    await recorder.prepareToRecordAsync();
    recorder.record();
  }

  async function photo() {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted)
      return Alert.alert('Photo access is needed to attach an image you select.');
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsMultipleSelection: true,
      quality: 0.8,
    });
    if (!result.canceled) {
      const selections = result.assets.map((asset, index) => ({
        asset,
        key: `${asset.uri}-${Date.now()}-${index}`,
      }));
      setPhotoPreviews((current) => [
        ...current,
        ...selections.map(({ asset, key }) => ({ key, uri: asset.uri, status: 'uploading' as const })),
      ]);
      for (const { asset, key } of selections) {
        await upload(
          asset.uri,
          'image',
          asset.mimeType ?? 'image/jpeg',
          asset.fileName?.split('.').pop() ?? 'jpg',
          key,
        );
      }
    }
  }

  const busy = stage === 'creating' || stage === 'uploading';
  const elapsedSeconds = Math.floor(state.durationMillis / 1000);
  const recordingTime = `${Math.floor(elapsedSeconds / 60)}:${String(elapsedSeconds % 60).padStart(2, '0')}`;
  const audioLabel =
    state.isRecording
      ? 'Stop recording'
      : busy && activeMedia === 'audio'
        ? 'Uploading…'
        : 'Record audio';
  const photoLabel =
    busy && activeMedia === 'image'
      ? 'Uploading…'
      : 'Attach photos';

  return (
    <View style={styles.wrap}>
      <View style={styles.actionRow}>
        <Pressable
          accessibilityLabel={
            state.isRecording
              ? `Stop recording. ${recordingTime} recorded.`
              : 'Record a voice note'
          }
          accessibilityRole="button"
          disabled={busy || disabled}
          onPress={record}
          style={({ pressed }) => [
            styles.action,
            state.isRecording && styles.recording,
            (pressed || busy || disabled) && styles.pressed,
          ]}
        >
          {state.isRecording ? (
            <Square color={colors.red} fill={colors.red} size={20} strokeWidth={3} />
          ) : (
            <Circle color={colors.red} fill={colors.red} size={20} strokeWidth={3} />
          )}
          <Text style={styles.actionText}>{audioLabel}</Text>
        </Pressable>
        <Pressable
          accessibilityLabel="Choose a photo to add to today"
          accessibilityRole="button"
          disabled={busy || disabled || state.isRecording}
          onPress={photo}
          style={({ pressed }) => [
            styles.action,
            (pressed || busy || disabled || state.isRecording) && styles.pressed,
          ]}
        >
          <Images color={colors.leaf} size={20} strokeWidth={3} />
          <Text style={styles.actionText}>{photoLabel}</Text>
        </Pressable>
      </View>
      {state.isRecording ? (
        <Text style={styles.recordingHint}>
          Recording now · {recordingTime}. Tap stop when you are ready to continue.
        </Text>
      ) : null}
      {photoPreviews.length ? (
        <View accessibilityLabel={`${photoPreviews.length} selected photo previews`} style={styles.photoGrid}>
          {photoPreviews.map((preview) => (
            <View key={preview.key} style={styles.photoPreview}>
              <Image source={{ uri: preview.uri }} style={styles.photo} />
              {preview.status !== 'ready' ? (
                <View style={styles.photoOverlay}>
                  <Text style={styles.photoOverlayText}>
                    {preview.status === 'failed' ? 'Try again' : 'Uploading…'}
                  </Text>
                </View>
              ) : null}
            </View>
          ))}
        </View>
      ) : null}
      {stage !== 'idle' ? (
        <ProcessingStatus
          errorMessage={errorMessage}
          mediaType={activeMedia}
          progress={uploadProgress}
          stage={stage}
        />
      ) : null}
    </View>
  );
}

function ProcessingStatus({
  errorMessage,
  mediaType,
  progress,
  stage,
}: {
  errorMessage: string | null;
  mediaType: 'audio' | 'image' | null;
  progress: number | null;
  stage: 'creating' | 'uploading' | 'ready' | 'failed';
}) {
  if (stage === 'ready' && mediaType === 'image') return null;
  const mediaName = mediaType === 'audio' ? 'audio' : 'photo';
  const state = {
    creating: ['•', `Creating a private ${mediaName} capture`],
    uploading: ['•', `Uploading your ${mediaName} privately${progress !== null ? ` (${progress}%)` : '…'}`],
    ready: ['✓', `Your ${mediaName} is attached privately`],
    failed: ['!', errorMessage ?? 'Upload could not finish. Please try again.'],
  } as const;
  const [mark, defaultCopy] = state[stage];
  const copy = defaultCopy;

  return (
    <View
      accessibilityLiveRegion="polite"
      style={[styles.status, stage === 'failed' && styles.statusFailed]}
    >
      <Text style={styles.statusMark}>{mark}</Text>
      <Text style={styles.statusText}>{copy}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 10 },
  actionRow: { flexDirection: 'row', gap: 10 },
  action: {
    alignItems: 'center',
    backgroundColor: colors.accentWash,
    borderRadius: 16,
    flex: 1,
    flexDirection: 'row',
    gap: 8,
    justifyContent: 'center',
    minHeight: 52,
    paddingHorizontal: 12,
  },
  recording: { backgroundColor: colors.red },
  actionSymbol: { color: colors.leaf, fontSize: 16 },
  actionText: { color: colors.ink, fontSize: 15, fontWeight: '700' },
  recordingHint: { color: colors.red, fontSize: 13, lineHeight: 18 },
  status: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 14,
    flexDirection: 'row',
    gap: 8,
    padding: 12,
  },
  statusFailed: { backgroundColor: '#F7ECE8' },
  statusMark: { color: colors.leaf, fontSize: 16, fontWeight: '700' },
  statusText: { color: colors.slate, flex: 1, fontSize: 14, lineHeight: 19 },
  pressed: { opacity: 0.58 },
  photoGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  photoPreview: {
    aspectRatio: 1,
    borderRadius: 12,
    overflow: 'hidden',
    width: '30%',
  },
  photo: { height: '100%', width: '100%' },
  photoOverlay: {
    alignItems: 'center',
    backgroundColor: 'rgba(20, 30, 22, 0.48)',
    bottom: 0,
    justifyContent: 'center',
    left: 0,
    position: 'absolute',
    right: 0,
    top: 0,
  },
  photoOverlayText: { color: '#FFFFFF', fontSize: 12, fontWeight: '700' },
});
