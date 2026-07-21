import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { PrimaryButton, colors } from '../components/ui';

export function OnboardingScreen({ onContinue }: { onContinue: () => Promise<void> }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function complete() {
    setSaving(true);
    setError(null);
    try {
      await onContinue();
    } catch {
      setError('We could not save your welcome. Please try again.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.wordmark}>DAYFORA</Text>
      <View style={styles.moment}><Text style={styles.momentMark}>✦</Text></View>
      <Text style={styles.title}>Make room for the{`\n`}days that matter.</Text>
      <Text style={styles.copy}>
        Save a thought, voice note, or photo directly. Your memories stay private and in your own words.
      </Text>
      <View style={styles.promise}>
        <Text style={styles.promiseLabel}>Private by default</Text>
        <Text style={styles.promiseText}>Nothing is shared, and you can delete what you no longer want to keep. DayFora never scans your camera roll.</Text>
      </View>
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <PrimaryButton disabled={saving} onPress={complete} tone="leaf">{saving ? 'Saving…' : 'Continue'}</PrimaryButton>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { backgroundColor: colors.canvas, flex: 1, justifyContent: 'flex-end', padding: 24, paddingBottom: 42 },
  wordmark: { color: colors.leaf, fontSize: 13, fontWeight: '800', letterSpacing: 2, marginBottom: 28 },
  moment: { alignItems: 'center', backgroundColor: colors.accentWash, borderRadius: 44, height: 88, justifyContent: 'center', marginBottom: 24, width: 88 },
  momentMark: { color: colors.leaf, fontSize: 32 },
  title: { color: colors.ink, fontSize: 40, fontWeight: '700', letterSpacing: -1.5, lineHeight: 46 },
  copy: { color: colors.slate, fontSize: 18, lineHeight: 27, marginBottom: 26, marginTop: 18 },
  promise: { backgroundColor: colors.surface, borderRadius: 20, gap: 7, marginBottom: 32, padding: 18 },
  promiseLabel: { color: colors.ink, fontSize: 16, fontWeight: '700' },
  promiseText: { color: colors.ink, fontSize: 15, lineHeight: 22 },
  error: { color: colors.coral, fontSize: 14, lineHeight: 20, marginBottom: 10 },
});
