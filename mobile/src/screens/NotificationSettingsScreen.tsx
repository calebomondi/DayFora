import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from 'react-native';
import type { Session } from '@supabase/supabase-js';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { PrimaryButton, ScreenHeader, colors } from '../components/ui';
import { getNotificationPreferences, updateNotificationPreferences } from '../lib/api';
import type { NotificationPreferences } from '../lib/types';

export function NotificationSettingsScreen({
  session,
  onBack,
}: {
  session: Session;
  onBack: () => void;
}) {
  const [prefs, setPrefs] = useState<NotificationPreferences | null>(null);
  const [saving, setSaving] = useState(false);
  const insets = useSafeAreaInsets();

  useEffect(() => {
    let active = true;
    async function loadInitialPreferences() {
      try {
        const data = await getNotificationPreferences(session);
        if (active) setPrefs(data);
      } catch (err) {
        console.error('Failed to load prefs:', err);
      }
    }
    void loadInitialPreferences();
    return () => {
      active = false;
    };
  }, [session]);

  async function save() {
    if (!prefs) return;
    setSaving(true);
    try {
      await updateNotificationPreferences(session, prefs);
    } catch (err) {
      console.error('Failed to save prefs:', err);
    } finally {
      setSaving(false);
    }
  }

  function update<K extends keyof NotificationPreferences>(
    key: K,
    value: NotificationPreferences[K],
  ) {
    if (!prefs) return;
    setPrefs({ ...prefs, [key]: value });
  }

  if (!prefs)
    return (
      <View style={styles.loading}>
        <ActivityIndicator color={colors.leaf} />
      </View>
    );

  return (
    <ScrollView
      contentContainerStyle={[styles.container, { paddingTop: insets.top + 12 }]}
      contentInsetAdjustmentBehavior="automatic"
      keyboardShouldPersistTaps="handled"
    >
      <ScreenHeader eyebrow="Make space, gently" title="Notifications" onBack={onBack} />
      <Text style={styles.intro}>
        Choose a moment that feels kind. You can change or turn these off anytime.
      </Text>
      <View style={styles.group}>
        <ReminderToggle
          copy="A small moment to remember today?"
          label="Daily diary reminder"
          value={prefs.diary_enabled}
          onValueChange={(value) => update('diary_enabled', value)}
        />
        {prefs.diary_enabled ? (
          <TimeRow
            label="Reminder time"
            value={prefs.diary_reminder_time ?? ''}
            onChangeText={(value) => update('diary_reminder_time', value)}
          />
        ) : null}
      </View>
      <View style={styles.group}>
        <ReminderToggle
          copy="Your week has a story. Take a quiet look."
          label="Weekly recap"
          value={prefs.weekly_recap_enabled}
          onValueChange={(value) => update('weekly_recap_enabled', value)}
        />
        {prefs.weekly_recap_enabled ? (
          <View style={styles.timeRow}>
            <Text style={styles.timeLabel}>Recap day</Text>
            <TextInput
              accessibilityLabel="Weekly recap day"
              keyboardType="number-pad"
              onChangeText={(value) => update('weekly_recap_day', parseInt(value, 10) || null)}
              placeholder="1–7"
              placeholderTextColor="#829098"
              style={styles.timeInput}
              value={prefs.weekly_recap_day?.toString() ?? ''}
            />
          </View>
        ) : null}
      </View>
      <PrimaryButton onPress={save} tone="leaf">
        {saving ? 'Saving…' : 'Save preferences'}
      </PrimaryButton>
    </ScrollView>
  );
}

function ReminderToggle({
  label,
  copy,
  value,
  onValueChange,
}: {
  label: string;
  copy: string;
  value: boolean;
  onValueChange: (value: boolean) => void;
}) {
  return (
    <View style={styles.row}>
      <View style={styles.rowText}>
        <Text style={styles.label}>{label}</Text>
        <Text style={styles.hint}>{copy}</Text>
      </View>
      <Switch
        accessibilityLabel={label}
        onValueChange={onValueChange}
        trackColor={{ true: colors.leaf }}
        value={value}
      />
    </View>
  );
}

function TimeRow({
  label,
  value,
  onChangeText,
}: {
  label: string;
  value: string;
  onChangeText: (value: string) => void;
}) {
  return (
    <View style={styles.timeRow}>
      <Text style={styles.timeLabel}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        onChangeText={onChangeText}
        placeholder="HH:MM"
        placeholderTextColor="#829098"
        style={styles.timeInput}
        value={value}
      />
    </View>
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
  loading: {
    alignItems: 'center',
    backgroundColor: colors.canvas,
    flex: 1,
    justifyContent: 'center',
  },
  intro: { color: colors.slate, fontSize: 16, lineHeight: 23, marginTop: -12 },
  group: { backgroundColor: colors.surface, borderRadius: 20, overflow: 'hidden' },
  row: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    minHeight: 78,
    padding: 16,
  },
  rowText: { flex: 1, gap: 4, marginRight: 12 },
  label: { color: colors.ink, fontSize: 16, fontWeight: '700' },
  hint: { color: colors.slate, fontSize: 13, lineHeight: 18 },
  timeRow: {
    alignItems: 'center',
    borderTopColor: colors.line,
    borderTopWidth: StyleSheet.hairlineWidth,
    flexDirection: 'row',
    justifyContent: 'space-between',
    minHeight: 62,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  timeLabel: { color: colors.slate, fontSize: 15 },
  timeInput: {
    backgroundColor: colors.paper,
    borderColor: colors.line,
    borderRadius: 10,
    borderWidth: 1,
    color: colors.ink,
    fontSize: 16,
    fontWeight: '600',
    minHeight: 40,
    paddingHorizontal: 12,
    textAlign: 'center',
    width: 82,
  },
});
