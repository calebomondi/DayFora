import { useState } from 'react';
import { AudioModule, RecordingPresets, useAudioRecorder, useAudioRecorderState } from 'expo-audio';
import * as ImagePicker from 'expo-image-picker';
import type { Session } from '@supabase/supabase-js';
import { Alert, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { PrimaryButton, colors, ScreenHeaderReflect } from '../components/ui';
import { createAddendumUploadUrl, createDiaryAddendum, uploadFile } from '../lib/api';
import type { DiaryEntry } from '../lib/types';

import { useSafeAreaInsets } from 'react-native-safe-area-context';

type StagedMedia = {
  contentType: string;
  extension: string;
  mediaType: 'audio' | 'image';
  uri: string;
};

export function DiaryAddendumScreen({
  entry,
  session,
  onBack,
  onSaved,
}: {
  entry: DiaryEntry;
  session: Session;
  onBack: () => void;
  onSaved: () => void;
}) {
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recorderState = useAudioRecorderState(recorder);
  const [body, setBody] = useState('');
  const [media, setMedia] = useState<StagedMedia[]>([]);
  const [saving, setSaving] = useState(false);
  const elapsedSeconds = Math.floor(recorderState.durationMillis / 1000);
  const recordingTime = `${Math.floor(elapsedSeconds / 60)}:${String(elapsedSeconds % 60).padStart(2, '0')}`;

  async function record() {
    if (recorderState.isRecording) {
      await recorder.stop();
      const audioUri = recorder.uri;
      if (audioUri) {
        setMedia((current) => [
          ...current,
          { uri: audioUri, mediaType: 'audio', contentType: 'audio/mp4', extension: 'm4a' },
        ]);
      }
      return;
    }
    const permission = await AudioModule.requestRecordingPermissionsAsync();
    if (!permission.granted) {
      Alert.alert('Microphone access is needed to add a voice reflection.');
      return;
    }
    await recorder.prepareToRecordAsync();
    recorder.record();
  }

  async function choosePhoto() {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      Alert.alert('Photo access is needed to attach an image you select.');
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 0.8,
    });
    if (result.canceled) return;
    const asset = result.assets[0];
    setMedia((current) => [
      ...current,
      {
        uri: asset.uri,
        mediaType: 'image',
        contentType: asset.mimeType ?? 'image/jpeg',
        extension: asset.fileName?.split('.').pop() ?? 'jpg',
      },
    ]);
  }

  async function save() {
    if (!body.trim() && !media.length) return;
    setSaving(true);
    try {
      const addendum = await createDiaryAddendum(session, entry.id, body);
      for (const item of media) {
        const target = await createAddendumUploadUrl(session, addendum.id, {
          media_type: item.mediaType,
          file_extension: item.extension,
          content_type: item.contentType,
        });
        await uploadFile(target.signed_url, item.uri, item.contentType);
      }
      onSaved();
    } catch (error) {
      console.error('Failed to add reflection:', error);
      Alert.alert('Your reflection could not be added', 'Please try again.');
    } finally {
      setSaving(false);
    }
  }

  const insets = useSafeAreaInsets();

  return (
    <ScrollView
      contentContainerStyle={[styles.container, { paddingTop: insets.top + 12 }]}
      contentInsetAdjustmentBehavior="automatic"
      keyboardShouldPersistTaps="handled"
    >
      <ScreenHeaderReflect
        onBack={onBack}
        title={`${entry.title}`}
      />
      <Text selectable style={styles.note}>
        Your original entry stays exactly as it was. This reflection will appear below it with
        today’s timestamp.
      </Text>
      <TextInput
        accessibilityLabel="Reflection text"
        multiline
        onChangeText={setBody}
        placeholder="What stayed with you after that day?"
        placeholderTextColor={colors.slate}
        style={styles.input}
        textAlignVertical="top"
        value={body}
      />
      <View style={styles.actions}>
        <Pressable
          accessibilityRole="button"
          disabled={saving}
          onPress={record}
          style={({ pressed }) => [
            styles.mediaAction,
            recorderState.isRecording && styles.recording,
            pressed && styles.pressed,
          ]}
        >
          <Text style={styles.mediaActionText}>
            {recorderState.isRecording ? 'Stop recording' : 'Record audio'}
          </Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          disabled={saving || recorderState.isRecording}
          onPress={choosePhoto}
          style={({ pressed }) => [styles.mediaAction, pressed && styles.pressed]}
        >
          <Text style={styles.mediaActionText}>Attach photo</Text>
        </Pressable>
      </View>
      {recorderState.isRecording ? (
        <Text style={styles.recordingHint}>
          Recording now · {recordingTime}
        </Text>
      ) : null}
      {media.length ? (
        <Text selectable style={styles.mediaCount}>
          {media.length} attachment{media.length === 1 ? '' : 's'} ready to add
        </Text>
      ) : null}
      <PrimaryButton
        disabled={saving || (!body.trim() && !media.length)}
        onPress={save}
        tone="leaf"
      >
        {saving ? 'Adding reflection…' : 'Add reflection'}
      </PrimaryButton>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.canvas,
    flexGrow: 1,
    gap: 16,
    padding: 24,
    paddingBottom: 40,
  },
  note: { color: colors.slate, fontSize: 16, lineHeight: 23 },
  input: {
    backgroundColor: colors.paper,
    borderColor: colors.line,
    borderCurve: 'continuous',
    borderRadius: 18,
    borderWidth: 1,
    color: colors.ink,
    fontFamily: 'PatrickHand_400Regular',
    fontSize: 22,
    lineHeight: 26,
    minHeight: 210,
    padding: 16,
  },
  actions: { flexDirection: 'row', gap: 10 },
  mediaAction: {
    alignItems: 'center',
    backgroundColor: colors.accentWash,
    borderRadius: 999,
    flex: 1,
    justifyContent: 'center',
    minHeight: 52,
    paddingHorizontal: 12,
  },
  recording: { backgroundColor: colors.accentWash },
  recordingHint: { color: colors.slate, fontSize: 14 },
  mediaActionText: { color: colors.ink, fontSize: 15, fontWeight: '700' },
  mediaCount: { color: colors.slate, fontSize: 14 },
  pressed: { opacity: 0.68 },
});
