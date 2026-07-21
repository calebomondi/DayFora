import { Heart } from 'lucide-react-native';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';


import { PrimaryButton, ScreenHeader, colors } from '../components/ui';
import { CaptureActions } from '../components/CaptureActions';
import type { DayFeeling } from '../lib/types';

export function DiaryEditorScreen({
  title,
  body,
  onTitleChange,
  onBodyChange,
  dayFeeling,
  onDayFeelingChange,
  onBack,
  onSaveEntry,
  onSaveEdit,
  onMediaUploaded,
  isSaving,
  mediaCount,
  mode,
}: {
  title: string;
  body: string;
  onTitleChange: (value: string) => void;
  onBodyChange: (value: string) => void;
  dayFeeling: DayFeeling | null;
  onDayFeelingChange: (value: DayFeeling | null) => void;
  onBack: () => void;
  onSaveEntry: () => void;
  onSaveEdit: () => void;
  onMediaUploaded: (mediaItemId: string, mediaType: 'audio' | 'image') => void;
  isSaving: boolean;
  mediaCount: number;
  mode: 'create' | 'edit';
}) {
  const insets = useSafeAreaInsets();
  const titleWords = title.trim() ? title.trim().split(/\s+/).length : 0;
  const titleTooLong = titleWords > 10;
  return (
    <ScrollView 
      contentContainerStyle={[styles.container, { paddingTop: insets.top + 12 }]} 
      keyboardShouldPersistTaps="handled"
    >
      <ScreenHeader
        eyebrow={
          'Today'
        }
        title={
          mode === 'edit' ? 'Edit today’s entry' : 'Save this day'
        }
        onBack={onBack}
      />
      <Text style={styles.prompt}>
        What happened, changed, or stayed with you? A rough note is enough.
      </Text>
      <TextInput
        accessibilityLabel="Diary title"
        onChangeText={onTitleChange}
        placeholder="Give today a small title"
        placeholderTextColor="#829098"
        style={styles.titleInput}
        value={title}
      />
      <Text style={[styles.wordCount, titleTooLong && styles.wordCountError]}>
        {titleWords}/10 words
      </Text>
      <TextInput
        accessibilityLabel="Diary entry"
        multiline
        onChangeText={onBodyChange}
        placeholder="What happened, changed, or stayed with you?"
        placeholderTextColor="#829098"
        style={styles.bodyInput}
        textAlignVertical="top"
        value={body}
      />
      <View style={styles.feelingSection}>
          <View style={styles.feelingHeader}>
            <Text selectable style={styles.feelingTitle}>How did this day feel?</Text>
            <Pressable
              accessibilityLabel="No mood selected"
              accessibilityRole="radio"
              accessibilityState={{ selected: dayFeeling === null }}
              onPress={() => onDayFeelingChange(null)}
              style={[styles.noMoodButton, dayFeeling === null && styles.noMoodButtonSelected]}
            >
              <Text style={[styles.noMoodText, dayFeeling === null && styles.noMoodTextSelected]}>
                No mood
              </Text>
            </Pressable>
          </View>
          <View accessibilityRole="radiogroup" style={styles.feelingChoices}>
            {DAY_FEELINGS.map((feeling) => {
              const selected = dayFeeling === feeling.value;
              return (
                <Pressable
                  accessibilityLabel={feeling.label}
                  accessibilityRole="radio"
                  accessibilityState={{ selected }}
                  key={feeling.value}
                  onPress={() => onDayFeelingChange(selected ? null : feeling.value)}
                  style={[styles.feelingButton, selected && styles.feelingButtonSelected]}
                >
                  <Heart
                    color={feeling.color}
                    fill={feeling.fill}
                    size={23}
                    strokeWidth={2.25}
                  />
                  <Text style={styles.feelingLabel}>{feeling.shortLabel}</Text>
                </Pressable>
              );
            })}
          </View>
      </View>
      <View style={styles.captureActions}>
        <CaptureActions disabled={!title.trim() || isSaving} onMediaUploaded={onMediaUploaded} />
        {mediaCount ? <Text style={styles.attachmentCopy}>{mediaCount} attachment{mediaCount === 1 ? '' : 's'} ready to save.</Text> : null}
      </View>
      <PrimaryButton
        disabled={
          isSaving ||
          !title.trim() ||
          titleTooLong ||
          (!body.trim() && mediaCount === 0)
        }
        onPress={mode === 'edit' ? onSaveEdit : onSaveEntry}
        tone="leaf"
      >
        {isSaving
          ? 'Saving…'
          : 'Save memory'}
      </PrimaryButton>
      <Text style={styles.footnote}>
        {mode === 'edit'
          ? 'You can add another recording or photo while keeping today’s original words.'
          : 'Your words and original attachments save directly. DayFora does not transcribe or describe them.'}
      </Text>
    </ScrollView>
  );
}

const DAY_FEELINGS: {
  value: DayFeeling;
  label: string;
  shortLabel: string;
  color: string;
  fill: string;
}[] = [
  { value: 'loved', label: 'Loved this day', shortLabel: 'Loved it', color: '#C94850', fill: '#C94850' },
  { value: 'low', label: 'Sad or dull day', shortLabel: 'Low day', color: '#4F7FC1', fill: '#4F7FC1' },
  { value: 'mixed', label: 'Mixed feelings day', shortLabel: 'Mixed', color: '#D47A31', fill: '#D47A31' },
  { value: 'quiet', label: 'Nothing much day', shortLabel: 'Nothing much', color: colors.slate, fill: colors.paper },
];


const styles = StyleSheet.create({
  container: { backgroundColor: colors.canvas, flexGrow: 1, padding: 24, paddingBottom: 40 },
  prompt: { color: colors.slate, fontSize: 17, lineHeight: 25, marginBottom: 18 },
  titleInput: {
    backgroundColor: colors.paper,
    borderColor: colors.line,
    borderRadius: 16,
    borderWidth: 1,
    color: colors.ink,
    fontSize: 22,
    fontFamily: 'Kalam_700Bold',
    marginBottom: 12,
    minHeight: 56,
    padding: 16,
  },
  wordCount: { color: colors.slate, fontSize: 13, marginBottom: 10, textAlign: 'right' },
  wordCountError: { color: '#C94850' },
  bodyInput: {
    backgroundColor: colors.paper,
    borderColor: colors.line,
    borderRadius: 16,
    borderWidth: 1,
    color: colors.ink,
    fontFamily: 'PatrickHand_400Regular',
    fontSize: 20,
    lineHeight: 26,
    minHeight: 230,
    padding: 16,
  },
  feelingSection: { gap: 10, marginTop: 16 },
  feelingHeader: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between' },
  feelingTitle: { color: colors.ink, fontSize: 16, fontWeight: '700' },
  noMoodButton: { borderRadius: 999, minHeight: 36, justifyContent: 'center', paddingHorizontal: 11 },
  noMoodButtonSelected: { backgroundColor: colors.accentWash },
  noMoodText: { color: colors.slate, fontSize: 13, fontWeight: '700' },
  noMoodTextSelected: { color: colors.leaf },
  feelingChoices: { flexDirection: 'row', gap: 8 },
  feelingButton: {
    alignItems: 'center',
    borderColor: colors.line,
    borderCurve: 'continuous',
    borderRadius: 14,
    borderWidth: 1,
    flex: 1,
    gap: 5,
    justifyContent: 'center',
    minHeight: 70,
    paddingHorizontal: 4,
    paddingVertical: 8,
  },
  feelingButtonSelected: { backgroundColor: colors.accentWash, borderColor: colors.leaf },
  feelingLabel: { color: colors.slate, fontSize: 11, fontWeight: '700', textAlign: 'center' },
  captureActions: { marginBottom: 14, marginTop: 14 },
  attachmentCopy: { color: colors.slate, fontSize: 14 },
  footnote: { color: colors.slate, fontSize: 15, marginTop: 14, textAlign: 'center' },
});
