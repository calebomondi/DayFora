import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { Image as ImageIcon, Mic } from 'lucide-react-native';
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import type { Session } from '@supabase/supabase-js';

import { PrimaryButton, ScreenSection, TintedLeadingDisc, colors } from '../components/ui';
import { fetchDiaryExplore, fetchExploreDiscovery, generateDiaryRecap } from '../lib/api';
import type {
  DiaryEntry,
  DiaryExploreResponse,
  DiaryRecap,
  ExploreDiscoveryResponse,
  ExploreMediaItem,
} from '../lib/types';

type Props = {
  session: Session;
  onCapture: () => void;
  onOpenEntry: (entry: DiaryEntry) => void;
  onOpenSearch: () => void;
  onOpenAsk: () => void;
};

export function ExploreDiaryScreen({
  session,
  onCapture,
  onOpenAsk,
  onOpenEntry,
  onOpenSearch,
}: Props) {
  const [selectedDay, setSelectedDay] = useState<DiaryExploreResponse | null>(null);
  const [discovery, setDiscovery] = useState<ExploreDiscoveryResponse | null>(null);
  const [recap, setRecap] = useState<DiaryRecap | null>(null);
  const [recapLoading, setRecapLoading] = useState(false);
  useEffect(() => {
    let active = true;
    void fetchDiaryExplore(session)
      .then((data) => active && setSelectedDay(data))
      .catch((error) => console.error('Failed to load Explore:', error));
    return () => {
      active = false;
    };
  }, [session]);
  useEffect(() => {
    let active = true;
    void fetchExploreDiscovery(session)
      .then((data) => active && setDiscovery(data))
      .catch((error) => console.error('Failed to load Explore discovery:', error));
    return () => {
      active = false;
    };
  }, [session]);

  async function prepareWeeklyRecap() {
    if (recapLoading) return;
    const period = currentWeekPeriod(selectedDay?.selected_date);
    setRecapLoading(true);
    try {
      setRecap(await generateDiaryRecap(session, {
        recap_type: 'weekly',
        period_start_date: period.start,
        period_end_date: period.end,
      }));
    } catch (error) {
      console.error('Failed to prepare diary recap:', error);
    } finally {
      setRecapLoading(false);
    }
  }

  const entry = selectedDay?.entry;
  return (
    <ScrollView contentContainerStyle={styles.content} contentInsetAdjustmentBehavior="automatic">
      <SelectedDayCard
        entry={entry}
        onCapture={onCapture}
        onOpen={() => entry && onOpenEntry(entry)}
      />

      <Pressable
        accessibilityLabel="Ask your diary"
        accessibilityRole="button"
        onPress={onOpenAsk}
        style={styles.ask}
      >
        <TintedLeadingDisc label="Ask your diary" symbol="✦" tone="accent" />
        <View style={styles.askCopy}>
          <Text style={styles.askTitle}>Ask your diary</Text>
          <Text style={styles.askText}>What would you like to revisit?</Text>
        </View>
        <Text style={styles.chevron}>›</Text>
      </Pressable>

      <Pressable
        accessibilityLabel="Search your diary"
        accessibilityRole="button"
        onPress={onOpenSearch}
        style={styles.ask}
      >
        <TintedLeadingDisc label="Search your diary" symbol="🔍" tone="accent" />
        <View style={styles.askCopy}>
          <Text style={styles.askTitle}>Search your diary</Text>
          <Text style={styles.askText}>What are you looking for?</Text>
        </View>
        <Text style={styles.chevron}>›</Text>
      </Pressable>

      <ExploreDiscovery
        discovery={discovery}
        recapAvailable={Boolean(selectedDay?.recap_available)}
        recap={recap}
        recapLoading={recapLoading}
        onPrepareRecap={() => void prepareWeeklyRecap()}
        onOpenEntry={onOpenEntry}
        onOpenSearch={onOpenSearch}
      />
    </ScrollView>
  );
}

function SelectedDayCard({
  entry,
  onCapture,
  onOpen,
}: {
  entry: DiaryEntry | null | undefined;
  onCapture: () => void;
  onOpen: () => void;
}) {
  const copy = entry
    ? entry.body || attachmentCopy(entry)
    : 'A small note now can become a memory later.';
  return (
    <View style={styles.primaryCard}>
      <Text selectable style={styles.primaryTitle}>
        {entry ? 'Today is held.' : 'Today is still yours.'}
      </Text>
      <Text selectable style={styles.primaryCopy}>
        {copy}
      </Text>
      {entry ? (
        <PrimaryButton onPress={onOpen} tone="leaf">
          Open memory
        </PrimaryButton>
      ) : (
        <PrimaryButton onPress={onCapture} tone="leaf">
          Capture today
        </PrimaryButton>
      )}
    </View>
  );
}

function ExploreDiscovery({
  discovery,
  onPrepareRecap,
  recapAvailable,
  recap,
  recapLoading,
  onOpenEntry,
  onOpenSearch,
}: {
  discovery: ExploreDiscoveryResponse | null;
  recapAvailable: boolean;
  recap: DiaryRecap | null;
  recapLoading: boolean;
  onPrepareRecap: () => void;
  onOpenEntry: (entry: DiaryEntry) => void;
  onOpenSearch: () => void;
}) {
  const contextualEntry = discovery?.on_this_day[0];
  return (
    <View style={styles.discovery}>
      {recapAvailable ? (
        <View style={styles.contextualCard}>
          <Text style={styles.contextualEyebrow}>This week, in brief</Text>
          {recap ? (
            <>
              <Text style={styles.contextualTitle}>
                {recap.insufficient_material ? 'A little more time will give this shape.' : (recap.title || 'A recap of your week')}
              </Text>
              <Text selectable style={styles.contextualCopy}>
                {recap.insufficient_material ? 'There are not enough saved entries in this period for a useful recap yet.' : recap.summary}
              </Text>
              <Text style={styles.recapMeta}>
                {recap.source_count} {recap.source_count === 1 ? 'entry' : 'entries'} · {formatRecapDateRange(recap.period_start_date, recap.period_end_date)}
              </Text>
              {recap.reflection_prompt ? <Text selectable style={styles.recapPrompt}>{recap.reflection_prompt}</Text> : null}
            </>
          ) : (
            <>
              <Text style={styles.contextualTitle}>
                Your saved entries have enough shape for a week-long story.
              </Text>
              <PrimaryButton disabled={recapLoading} onPress={onPrepareRecap} tone="leaf">
                {recapLoading ? 'Preparing your recap…' : 'Read your recap'}
              </PrimaryButton>
            </>
          )}
        </View>
      ) : contextualEntry ? (
        <Pressable
          accessibilityLabel={`Open on this day memory, ${contextualEntry.title}`}
          accessibilityRole="button"
          onPress={() => onOpenEntry(contextualEntry)}
          style={styles.contextualCard}
        >
          <Text style={styles.contextualEyebrow}>On this day</Text>
          <Text style={styles.contextualTitle}>{contextualEntry.title}</Text>
          <Text numberOfLines={1} style={styles.contextualCopy}>
            {contextualEntry.body || attachmentCopy(contextualEntry)}
          </Text>
        </Pressable>
      ) : null}
      <RecentPhotos items={discovery?.recent_photos ?? []} onOpenEntry={onOpenEntry} />
      <RecentAudio items={discovery?.recent_audio ?? []} onOpenEntry={onOpenEntry} />
      {discovery?.saved_recaps.length ? (
        <ScreenSection title="Saved recaps">
          <View>
            {discovery.saved_recaps.slice(0, 3).map((recap) => (
              <View
                key={recap.id ?? `${recap.period_start_date}-${recap.recap_type}`}
                style={styles.recapRow}
              >
                <Text style={styles.recapTitle}>{recap.title || 'A saved recap'}</Text>
                <Text style={styles.recapMeta}>
                  {recap.period_start_date} · {recap.source_count} moments
                </Text>
              </View>
            ))}
          </View>
        </ScreenSection>
      ) : null}
    </View>
  );
}

function RecentPhotos({
  items,
  onOpenEntry,
}: {
  items: ExploreMediaItem[];
  onOpenEntry: (entry: DiaryEntry) => void;
}) {
  return (
    <ScreenSection title="Photos">
      {items.length ? (
        <View style={styles.photoGrid}>
          {items.map((item) => (
            <Pressable
              accessibilityLabel={`Open photo from ${item.title}`}
              accessibilityRole="button"
              key={item.media_item_id}
              onPress={() => onOpenEntry(mediaEntry(item))}
              style={styles.photoTile}
            >
              <Image
                accessibilityLabel={`Photo from ${item.title}`}
                source={{ uri: item.signed_url }}
                style={styles.photo}
              />
            </Pressable>
          ))}
        </View>
      ) : (
        <EmptyMedia
          icon={<ImageIcon color={colors.slate} size={19} />}
          text="No photos saved yet. A photo you choose to keep will appear here."
        />
      )}
    </ScreenSection>
  );
}
function RecentAudio({
  items,
  onOpenEntry,
}: {
  items: ExploreMediaItem[];
  onOpenEntry: (entry: DiaryEntry) => void;
}) {
  return (
    <ScreenSection title="Voice notes">
      {items.length ? (
        <View>
          {items.map((item) => (
            <Pressable
              accessibilityLabel={`Open voice note from ${item.title}`}
              accessibilityRole="button"
              key={item.media_item_id}
              onPress={() => onOpenEntry(mediaEntry(item))}
              style={styles.audioRow}
            >
              <View style={styles.audioDisc}>
                <Mic color={colors.leaf} size={19} />
              </View>
              <View style={styles.audioCopy}>
                <Text numberOfLines={1} style={styles.audioTitle}>
                  {item.title}
                </Text>
                <Text style={styles.audioMeta}>{item.local_date} · Voice note</Text>
              </View>
              <Text style={styles.chevron}>›</Text>
            </Pressable>
          ))}
        </View>
      ) : (
        <EmptyMedia
          icon={<Mic color={colors.slate} size={19} />}
          text="No voice notes saved yet. A recording you keep will appear here."
        />
      )}
    </ScreenSection>
  );
}
function EmptyMedia({ icon, text }: { icon: ReactNode; text: string }) {
  return (
    <View style={styles.emptyMedia}>
      {icon}
      <Text style={styles.emptyMediaText}>{text}</Text>
    </View>
  );
}
function mediaEntry(item: ExploreMediaItem): DiaryEntry {
  return {
    id: item.entry_id,
    title: item.title,
    body: '',
    mood: null,
    day_feeling: null,
    local_date: item.local_date,
    status: 'approved',
    source_badge: 'user_written',
    audio_count: 0,
    image_count: 0,
    addenda_count: 0,
    preview_images: [],
    preview_audio: null,
  };
}
function attachmentCopy(entry: DiaryEntry) {
  return entry.audio_count
    ? entry.image_count
      ? 'Voice note and photos attached.'
      : 'Voice note attached.'
    : 'Photos attached.';
}

function currentWeekPeriod(selectedDate?: string) {
  const date = selectedDate ? new Date(`${selectedDate}T12:00:00`) : new Date();
  const start = new Date(date);
  start.setDate(date.getDate() - date.getDay());
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  return { start: localDateString(start), end: localDateString(end) };
}

function localDateString(value: Date) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;
}

function formatRecapDateRange(start: string, end: string) {
  const startDate = new Date(`${start}T12:00:00`);
  const endDate = new Date(`${end}T12:00:00`);
  const dayMonth = (value: Date) => `${String(value.getDate()).padStart(2, '0')}/${String(value.getMonth() + 1).padStart(2, '0')}`;
  const withYear = (value: Date) => `${dayMonth(value)}/${value.getFullYear()}`;
  return startDate.getFullYear() === endDate.getFullYear()
    ? `${dayMonth(startDate)}–${dayMonth(endDate)}`
    : `${withYear(startDate)}–${withYear(endDate)}`;
}

const styles = StyleSheet.create({
  content: {
    backgroundColor: colors.canvas,
    flexGrow: 1,
    gap: 18,
    padding: 24,
    paddingBottom: 112,
  },
  primaryCard: {
    backgroundColor: colors.surface,
    borderCurve: 'continuous',
    borderRadius: 22,
    gap: 10,
    padding: 20,
  },
  primaryTitle: { color: colors.ink, fontSize: 23, fontWeight: '700' },
  primaryCopy: { color: colors.slate, fontSize: 16, lineHeight: 22 },
  discovery: { gap: 18 },
  contextualCard: {
    backgroundColor: colors.paper,
    borderCurve: 'continuous',
    borderRadius: 20,
    gap: 5,
    padding: 18,
  },
  contextualEyebrow: { color: colors.leaf, fontSize: 13, fontWeight: '700' },
  contextualTitle: { color: colors.ink, fontSize: 17, fontWeight: '700', lineHeight: 23 },
  contextualCopy: { color: colors.slate, fontSize: 15 },
  search: {
    alignItems: 'center',
    backgroundColor: colors.paper,
    borderRadius: 18,
    flexDirection: 'row',
    gap: 10,
    minHeight: 52,
    paddingHorizontal: 16,
  },
  searchText: { color: colors.ink, flex: 1, fontSize: 16, fontWeight: '600' },
  chevron: { color: colors.slate, fontSize: 26 },
  photoGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 3, padding: 12 },
  photoTile: { aspectRatio: 1, borderRadius: 10, overflow: 'hidden', width: '32.7%' },
  photo: { backgroundColor: colors.surface, height: '100%', width: '100%' },
  emptyMedia: { alignItems: 'center', flexDirection: 'row', gap: 10, padding: 16 },
  emptyMediaText: { color: colors.slate, flex: 1, fontSize: 15, lineHeight: 21 },
  audioRow: { alignItems: 'center', flexDirection: 'row', gap: 12, minHeight: 68, padding: 14 },
  audioDisc: {
    alignItems: 'center',
    backgroundColor: colors.accentWash,
    borderRadius: 22,
    height: 44,
    justifyContent: 'center',
    width: 44,
  },
  audioCopy: { flex: 1, gap: 3 },
  audioTitle: { color: colors.ink, fontSize: 16, fontWeight: '700' },
  audioMeta: { color: colors.slate, fontSize: 14 },
  recapRow: { gap: 3, padding: 14 },
  recapTitle: { color: colors.ink, fontSize: 16, fontWeight: '700' },
  recapMeta: { color: colors.slate, fontSize: 14 },
  recapPrompt: { color: colors.leaf, fontSize: 14, fontWeight: '600', lineHeight: 20 },
  recapSources: { gap: 8, marginTop: 4 },
  recapSource: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    gap: 2,
    paddingHorizontal: 11,
    paddingVertical: 9,
  },
  recapSourceDate: { color: colors.slate, fontSize: 12, fontWeight: '600' },
  recapSourceTitle: { color: colors.ink, fontSize: 14, fontWeight: '700' },
  pressed: { opacity: 0.72 },
  ask: {
    alignItems: 'center',
    backgroundColor: colors.paper,
    borderRadius: 22,
    flexDirection: 'row',
    gap: 12,
    padding: 16,
  },
  askCopy: { flex: 1, gap: 3 },
  askTitle: { color: colors.ink, fontSize: 17, fontWeight: '700' },
  askText: { color: colors.slate, fontSize: 15 },
});
