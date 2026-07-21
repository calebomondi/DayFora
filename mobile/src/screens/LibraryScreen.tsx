import { useEffect, useMemo, useRef, useState } from 'react';
import { useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import {
  ArrowUp,
  ChevronLeft,
  ChevronRight,
  Heart,
  Images,
  Pause,
  PenLine,
  Play,
  Plus,
  Search,
  Volume2,
} from 'lucide-react-native';
import {
  NativeScrollEvent,
  NativeSyntheticEvent,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors } from '../components/ui';
import type { DiaryEntry, DiaryMediaPreview } from '../lib/types';

type LibraryScreenProps = {
  entries: DiaryEntry[];
  timelineStartDate: string | null;
  scrollOffset: number;
  showCaptureToday: boolean;
  onCaptureToday: () => void;
  onOpenEntry: (entry: DiaryEntry) => void;
  onSearch: () => void;
  onScrollOffsetChange: (offset: number) => void;
};

export function LibraryScreen({
  entries,
  timelineStartDate,
  scrollOffset,
  showCaptureToday,
  onCaptureToday,
  onOpenEntry,
  onSearch,
  onScrollOffsetChange,
}: LibraryScreenProps) {
  const scrollRef = useRef<ScrollView>(null);
  const initialScrollOffset = useRef(scrollOffset);
  const [pageState, setPageState] = useState({ entryFingerprint: '', index: 0 });
  const [expandedGapIds, setExpandedGapIds] = useState<ReadonlySet<string>>(() => new Set());
  const [showScrollToTop, setShowScrollToTop] = useState(scrollOffset > 280);
  const timelinePages = useMemo(
    () => paginateTimeline(buildDiaryTimeline(entries, timelineStartDate)),
    [entries, timelineStartDate],
  );
  const entryFingerprint = entries.map((entry) => `${entry.id}:${entry.local_date}`).join('|');
  const activePage = Math.min(
    pageState.entryFingerprint === entryFingerprint ? pageState.index : 0,
    timelinePages.length - 1,
  );
  const visibleFeedItems = useMemo(
    () => buildDiaryFeedItems(timelinePages[activePage] ?? [], expandedGapIds),
    [activePage, expandedGapIds, timelinePages],
  );
  const insets = useSafeAreaInsets();

  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({ y: initialScrollOffset.current, animated: false });
    });
    return () => cancelAnimationFrame(frame);
  }, []);

  function handleScroll(event: NativeSyntheticEvent<NativeScrollEvent>) {
    const offset = event.nativeEvent.contentOffset.y;
    onScrollOffsetChange(offset);
    const shouldShow = offset > 280;
    setShowScrollToTop((current) => (current === shouldShow ? current : shouldShow));
  }

  function goToPage(nextPage: number) {
    setPageState({ entryFingerprint, index: nextPage });
    scrollRef.current?.scrollTo({ y: 0, animated: true });
  }

  function scrollToTop() {
    scrollRef.current?.scrollTo({ y: 0, animated: true });
  }

  function toggleMissedDays(gapId: string) {
    setExpandedGapIds((current) => {
      const next = new Set(current);
      if (next.has(gapId)) next.delete(gapId);
      else next.add(gapId);
      return next;
    });
  }

  return (
    <View style={styles.root}>
      <ScrollView
        ref={scrollRef}
        contentContainerStyle={styles.scrollContent}
        contentInsetAdjustmentBehavior="automatic"
        onScroll={handleScroll}
        scrollEventThrottle={16}
        stickyHeaderIndices={[0]}
      >
        <View style={styles.stickyHeader}>
          <View style={styles.toolbar}>
            <Text accessibilityRole="header" style={styles.entriesLabel}>Entries</Text>
            <Pressable
              accessibilityLabel="Search memories"
              accessibilityRole="button"
              onPress={onSearch}
              style={({ pressed }) => [styles.searchButton, pressed && styles.pressed]}
            >
              <Search color={colors.leaf} size={25} strokeWidth={3} />
            </Pressable>
          </View>
        </View>

        <View style={styles.content}>
          {showCaptureToday ? (
            <View style={styles.captureBanner}>
              <View style={styles.captureCopy}>
                <Text selectable style={styles.captureTitle}>Capture today</Text>
                <Text selectable style={styles.captureText}>
                  Add a written note, voice note, or image and keep today archived & memorable.
                </Text>
              </View>
              <Pressable
                accessibilityLabel="Capture today"
                accessibilityRole="button"
                onPress={onCaptureToday}
                style={({ pressed }) => [styles.captureButton, pressed && styles.pressed]}
              >
                <Plus color="#FFFFFF" size={22} strokeWidth={2.5} />
              </Pressable>
            </View>
          ) : null}

          <View style={styles.list}>
              {visibleFeedItems.map((item) =>
                item.kind === 'entry' ? (
                  <DiaryExcerptCard
                    entry={item.entry}
                    key={item.entry.id}
                    onPress={() => onOpenEntry(item.entry)}
                  />
                ) : item.kind === 'passed' ? (
                  <PassedDayCard key={item.localDate} localDate={item.localDate} />
                ) : item.kind === 'missed-group' ? (
                  <MissedDaysSummaryCard
                    count={item.count}
                    gapId={item.id}
                    key={item.id}
                    onPress={() => toggleMissedDays(item.id)}
                  />
                ) : (
                  <Pressable
                    accessibilityLabel={`Hide ${item.count} missed days`}
                    accessibilityRole="button"
                    key={item.id}
                    onPress={() => toggleMissedDays(item.id)}
                    style={({ pressed }) => [styles.hideMissedDays, pressed && styles.pressed]}
                  >
                    <Text style={styles.hideMissedDaysText}>Hide missed days</Text>
                  </Pressable>
                ),
              )}
          </View>

          {timelinePages.length > 1 ? (
            <View style={styles.pagination}>
              <Pressable
                accessibilityLabel="Previous diary entries"
                accessibilityRole="button"
                disabled={activePage === 0}
                onPress={() => goToPage(activePage - 1)}
                style={({ pressed }) => [
                  styles.pageButton,
                  activePage === 0 && styles.pageButtonDisabled,
                  pressed && activePage > 0 && styles.pressed,
                ]}
              >
                <ChevronLeft color={colors.leaf} size={19} strokeWidth={2.5} />
                <Text style={styles.pageButtonLabel}>Newer</Text>
              </Pressable>
              <Text selectable style={styles.pageStatus}>
                Page {activePage + 1} of {timelinePages.length}
              </Text>
              <Pressable
                accessibilityLabel="Older diary entries"
                accessibilityRole="button"
                disabled={activePage === timelinePages.length - 1}
                onPress={() => goToPage(activePage + 1)}
                style={({ pressed }) => [
                  styles.pageButton,
                  activePage === timelinePages.length - 1 && styles.pageButtonDisabled,
                  pressed && activePage < timelinePages.length - 1 && styles.pressed,
                ]}
              >
                <Text style={styles.pageButtonLabel}>Older</Text>
                <ChevronRight color={colors.leaf} size={19} strokeWidth={2.5} />
              </Pressable>
            </View>
          ) : null}
        </View>
      </ScrollView>

      {showScrollToTop ? (
        <Pressable
          accessibilityHint="Returns to the top of your diary"
          accessibilityLabel="Back to top"
          accessibilityRole="button"
          onPress={scrollToTop}
          style={[styles.scrollToTop, { bottom: Math.max(insets.bottom, 14) + 84 }]}
        >
          <ArrowUp color="#FFFFFF" size={20} strokeWidth={2.75} />
        </Pressable>
      ) : null}
    </View>
  );
}

type DiaryTimelineItem =
  | { kind: 'entry'; entry: DiaryEntry }
  | { kind: 'passed'; localDate: string };

type DiaryFeedItem =
  | DiaryTimelineItem
  | { kind: 'missed-group'; id: string; count: number }
  | { kind: 'hide-missed-days'; id: string; count: number };

function buildDiaryTimeline(
  entries: DiaryEntry[],
  timelineStartDate: string | null,
): DiaryTimelineItem[] {
  const entryByDate = new Map(entries.map((entry) => [entry.local_date, entry]));
  const today = startOfDay(new Date());
  const earliestEntry = entries.reduce<Date | null>((earliest, entry) => {
    const entryDate = new Date(`${entry.local_date}T12:00:00`);
    return !earliest || entryDate < earliest ? entryDate : earliest;
  }, null);
  const fallbackStart = new Date(today);
  fallbackStart.setDate(today.getDate() - (entries.length ? 59 : 6));
  const accountStart = timelineStartDate
    ? startOfDay(new Date(`${timelineStartDate}T12:00:00`))
    : null;
  const firstDate = accountStart && accountStart <= today
    ? accountStart
    : earliestEntry && earliestEntry < fallbackStart
      ? earliestEntry
      : fallbackStart;
  const timeline: DiaryTimelineItem[] = [];

  for (const day = new Date(today); day >= firstDate; day.setDate(day.getDate() - 1)) {
    const localDate = toLocalDate(day);
    const entry = entryByDate.get(localDate);
    if (entry) timeline.push({ kind: 'entry', entry });
    else if (day < today) timeline.push({ kind: 'passed', localDate });
  }

  return timeline;
}

function paginateTimeline(timeline: DiaryTimelineItem[], pageSize = 20): DiaryTimelineItem[][] {
  const pages: DiaryTimelineItem[][] = [[]];
  let entryCount = 0;

  timeline.forEach((item) => {
    pages[pages.length - 1].push(item);
    if (item.kind !== 'entry') return;
    entryCount += 1;
    if (entryCount === pageSize) {
      entryCount = 0;
      pages.push([]);
    }
  });

  if (pages[pages.length - 1].length === 0) pages.pop();
  return pages.length ? pages : [[]];
}

function buildDiaryFeedItems(
  timeline: DiaryTimelineItem[],
  expandedGapIds: ReadonlySet<string>,
): DiaryFeedItem[] {
  const result: DiaryFeedItem[] = [];

  for (let index = 0; index < timeline.length; index += 1) {
    const item = timeline[index];
    if (item.kind !== 'passed') {
      result.push(item);
      continue;
    }

    const missedDays: Extract<DiaryTimelineItem, { kind: 'passed' }>[] = [item];
    while (timeline[index + 1]?.kind === 'passed') {
      index += 1;
      missedDays.push(timeline[index] as Extract<DiaryTimelineItem, { kind: 'passed' }>);
    }

    if (missedDays.length === 1) {
      result.push(item);
      continue;
    }

    const id = `missed-${missedDays[0].localDate}-${missedDays[missedDays.length - 1].localDate}`;
    if (expandedGapIds.has(id)) {
      result.push({ kind: 'hide-missed-days', id, count: missedDays.length });
      result.push(...missedDays);
    } else {
      result.push({ kind: 'missed-group', id, count: missedDays.length });
    }
  }

  return result;
}

function MissedDaysSummaryCard({
  count,
  gapId,
  onPress,
}: {
  count: number;
  gapId: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityHint="Reveals each passed day so you can reflect on it"
      accessibilityLabel={`Show ${count} missed days`}
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [styles.missedDaysCard, pressed && styles.pressed]}
      testID={gapId}
    >
      <View accessible={false} style={styles.passedDisc}>
        <PenLine color={colors.slate} size={16} strokeWidth={2} />
      </View>
      <View style={styles.missedDaysCopy}>
        <Text selectable style={styles.missedDaysTitle}>
          Missed {count} days consecutively
        </Text>
        <Text selectable style={styles.missedDaysText}>
          Tap to see those days and make room for a reflection.
        </Text>
      </View>
      <ChevronRight color={colors.leaf} size={20} strokeWidth={2.5} />
    </Pressable>
  );
}

function PassedDayCard({ localDate }: { localDate: string }) {
  const relativeDate = formatEntryDate(localDate);
  return (
    <View style={styles.passedCard}>
      <View style={styles.dateHeader}>
        <Text selectable style={styles.date}>
          {relativeDate}
        </Text>
      </View>
      <View style={styles.passedHeader}>
        <View accessible={false} style={styles.passedDisc}>
          <PenLine color={colors.slate} size={16} strokeWidth={2} />
        </View>
        <Text selectable style={styles.title}>This day passed quietly</Text>
      </View>
      <Text selectable style={styles.excerpt}>You did not save a memory that day.</Text>
    </View>
  );
}

function DayFeelingHeart({ entry }: { entry: DiaryEntry }) {
  const mood = entry.mood ?? entry.day_feeling;
  const presentation = heartPresentation(mood);
  if (!presentation) return null;
  return (
    <View accessibilityLabel={presentation.label} accessibilityRole="image" style={styles.dayFeelingHeart}>
      <Heart color={presentation.color} fill={presentation.fill} size={21} strokeWidth={2.25} />
    </View>
  );
}

function heartPresentation(mood: string | null) {
  switch (mood) {
    case 'happy_fun':
    case 'loved':
      return { color: '#C94850', fill: '#C94850', label: 'Happy or fun day' };
    case 'sad_dull':
    case 'low':
      return { color: '#4F7FC1', fill: '#4F7FC1', label: 'Sad or dull day' };
    case 'mixed':
      return { color: '#D47A31', fill: '#D47A31', label: 'Mixed feelings day' };
    case 'quiet':
      return { color: colors.slate, fill: colors.paper, label: 'Nothing much day' };
    default:
      return null;
  }
}

function DiaryExcerptCard({ entry, onPress }: { entry: DiaryEntry; onPress: () => void }) {
  const relativeDate = formatEntryDate(entry.local_date);
  const mediaDescription = attachmentDescription(entry);
  const title = entry.title.trim() || 'Untitled reflection';
  const body = entry.body.trim() || (entry.audio_count ? 'Voice note attached' : 'Photos attached');

  return (
    <Pressable
      accessibilityHint="Opens this diary entry in a full reader"
      accessibilityLabel={`${title}. ${relativeDate}.${mediaDescription ? ` ${mediaDescription}.` : ''}`}
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
    >
      <View style={styles.dateHeader}>
        <Text selectable style={styles.date}>
          {relativeDate}
        </Text>
        <DayFeelingHeart entry={entry} />
      </View>
      <View style={styles.header}>
        <View accessible={false} style={styles.penDisc}>
          <PenLine color={colors.ink} size={17} strokeWidth={2} />
        </View>
        <Text selectable style={styles.title}>
          {title}
        </Text>
      </View>
      <Text ellipsizeMode="tail" numberOfLines={3} selectable style={styles.excerpt}>
        {body}
      </Text>
      <CardAttachmentPreviews entry={entry} />
      {entry.addenda_count ? (
        <View style={styles.metadata}>
          <Text style={styles.addendaMarker}>
            + {entry.addenda_count} {entry.addenda_count === 1 ? 'reflection' : 'reflections'}
          </Text>
        </View>
      ) : null}
    </Pressable>
  );
}

function CardAttachmentPreviews({ entry }: { entry: DiaryEntry }) {
  const remainingImages = Math.max(entry.image_count - entry.preview_images.length, 0);
  const remainingAudio = Math.max(entry.audio_count - (entry.preview_audio ? 1 : 0), 0);
  if (!entry.image_count && !entry.audio_count) return null;

  return (
    <View style={styles.previewSection}>
      {entry.preview_images.length ? (
        <View style={styles.imagePreviewSection}>
          {remainingImages ? (
            <View
              accessibilityLabel={`${remainingImages} more ${remainingImages === 1 ? 'image' : 'images'} attached`}
              style={styles.remainingAttachmentCount}
            >
              <Images color={colors.slate} size={15} strokeWidth={2.5} />
              <Text style={styles.remainingAttachmentText}>+{remainingImages}</Text>
            </View>
          ) : null}
          <View accessibilityLabel={`${entry.image_count} ${entry.image_count === 1 ? 'photo' : 'photos'} attached`} style={styles.cardGallery}>
            {entry.preview_images.map((image, index) => (
              <Image
                accessibilityLabel={`Attached photo ${index + 1}`}
                key={image.id}
                resizeMode="cover"
                source={{ uri: image.signed_url }}
                style={styles.cardImage}
              />
            ))}
          </View>
        </View>
      ) : entry.image_count ? (
        <AttachmentIndicators entry={{ ...entry, audio_count: 0 }} />
      ) : null}
      {entry.preview_audio ? (
        <CardAudioPreview audio={entry.preview_audio} remaining={remainingAudio} />
      ) : entry.audio_count ? (
        <AttachmentIndicators entry={{ ...entry, image_count: 0 }} />
      ) : null}
    </View>
  );
}

function CardAudioPreview({
  audio,
  remaining,
}: {
  audio: DiaryMediaPreview;
  remaining: number;
}) {
  const player = useAudioPlayer(audio.signed_url, { updateInterval: 250 });
  const status = useAudioPlayerStatus(player);

  function togglePlayback(event: { stopPropagation: () => void }) {
    event.stopPropagation();
    if (status.playing) player.pause();
    else player.play();
  }

  return (
    <Pressable
      accessibilityHint="Plays the first original voice note without opening the diary reader"
      accessibilityLabel={`${status.playing ? 'Pause' : 'Play'} voice note${remaining ? `; ${remaining} more attached` : ''}`}
      accessibilityRole="button"
      onPress={togglePlayback}
      style={({ pressed }) => [styles.cardAudioPreview, pressed && styles.pressed]}
    >
      <View accessible={false} style={styles.cardAudioDisc}>
        <Volume2 color={colors.ink} size={16} strokeWidth={2.5} />
      </View>
      <Text style={styles.cardAudioLabel}>Voice note</Text>
      {remaining ? (
        <View accessible={false} style={styles.remainingAttachmentCount}>
          <Volume2 color={colors.slate} size={14} strokeWidth={2.5} />
          <Text style={styles.remainingAttachmentText}>+{remaining}</Text>
        </View>
      ) : null}
      {status.playing ? (
        <Pause color={colors.leaf} fill={colors.leaf} size={18} />
      ) : (
        <Play color={colors.leaf} fill={colors.leaf} size={18} />
      )}
    </Pressable>
  );
}

function AttachmentIndicators({ entry }: { entry: DiaryEntry }) {
  if (!entry.audio_count && !entry.image_count) return null;
  return (
    <View accessible={false} style={styles.attachments}>
      {entry.audio_count ? <Volume2 color={colors.slate} size={18} strokeWidth={3} /> : null}
      {entry.image_count ? (
        <View style={styles.imageIndicator}>
          <Images color={colors.slate} size={18} strokeWidth={3} />
          {entry.image_count > 1 ? <Text style={styles.count}>{entry.image_count}</Text> : null}
        </View>
      ) : null}
    </View>
  );
}

function attachmentDescription(entry: DiaryEntry) {
  const attachments: string[] = [];
  if (entry.audio_count) {
    attachments.push(`${entry.audio_count} ${entry.audio_count === 1 ? 'audio attachment' : 'audio attachments'}`);
  }
  if (entry.image_count) {
    attachments.push(`${entry.image_count} ${entry.image_count === 1 ? 'image attachment' : 'image attachments'}`);
  }
  return attachments.join(', ');
}

export function formatEntryDate(localDate: string, currentDate = new Date()) {
  const entryDate = new Date(`${localDate}T12:00:00`);
  const today = startOfDay(currentDate);
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (sameDay(entryDate, today)) return 'Today';
  if (sameDay(entryDate, yesterday)) return 'Yesterday';

  const weekStart = new Date(today);
  weekStart.setDate(today.getDate() - today.getDay());
  if (entryDate >= weekStart && entryDate <= today) {
    return new Intl.DateTimeFormat(undefined, { weekday: 'long' }).format(entryDate);
  }
  return new Intl.DateTimeFormat(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  }).format(entryDate);
}

function startOfDay(value: Date) {
  const result = new Date(value);
  result.setHours(0, 0, 0, 0);
  return result;
}

function sameDay(left: Date, right: Date) {
  return left.getFullYear() === right.getFullYear()
    && left.getMonth() === right.getMonth()
    && left.getDate() === right.getDate();
}

function toLocalDate(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

const styles = StyleSheet.create({
  root: { backgroundColor: colors.canvas, flex: 1 },
  scrollContent: { backgroundColor: colors.canvas, flexGrow: 1, paddingBottom: 132 },
  stickyHeader: { backgroundColor: colors.canvas, paddingBottom: 12, paddingHorizontal: 20, paddingTop: 20 },
  content: { gap: 16, paddingHorizontal: 20, paddingTop: 4 },
  toolbar: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    minHeight: 44,
  },
  entriesLabel: { color: colors.ink, fontSize: 20, fontWeight: '700', paddingVertical: 10 },
  segment: {
    alignItems: 'center',
    borderRadius: 999,
    justifyContent: 'center',
    minHeight: 38,
    paddingHorizontal: 16,
  },
  segmentSelected: { backgroundColor: colors.paper },
  segmentLabel: { color: colors.slate, fontSize: 16, fontWeight: '700' },
  segmentLabelSelected: { color: colors.leaf },
  segmentPressed: { opacity: 0.7 },
  searchButton: {
    alignItems: 'center',
    backgroundColor: colors.accentWash,
    borderRadius: 22,
    height: 44,
    justifyContent: 'center',
    width: 44,
  },
  captureBanner: {
    alignItems: 'center',
    backgroundColor: colors.paper,
    borderCurve: 'continuous',
    borderRadius: 20,
    flexDirection: 'row',
    gap: 12,
    padding: 15,
  },
  captureCopy: { flex: 1, gap: 3 },
  captureTitle: { color: colors.leaf, fontSize: 20, fontWeight: '700' },
  captureText: { color: colors.slate, fontSize: 16, lineHeight: 20 },
  captureButton: {
    alignItems: 'center',
    backgroundColor: colors.leaf,
    borderRadius: 999,
    height: 44,
    justifyContent: 'center',
    width: 44,
  },
  list: { gap: 12 },
  card: {
    backgroundColor: colors.accentWash,
    borderCurve: 'continuous',
    borderRadius: 22,
    boxShadow: '0 1px 2px rgba(28, 37, 30, 0.05)',
    gap: 15,
    minHeight: 176,
    paddingHorizontal: 18,
    paddingVertical: 18,
  },
  passedCard: {
    backgroundColor: colors.surface,
    borderCurve: 'continuous',
    borderRadius: 22,
    boxShadow: '0 1px 2px rgba(28, 37, 30, 0.05)',
    gap: 12,
    paddingHorizontal: 18,
    paddingVertical: 18,
  },
  missedDaysCard: {
    alignItems: 'center',
    backgroundColor: colors.orange,
    borderColor: colors.line,
    borderCurve: 'continuous',
    borderRadius: 22,
    borderWidth: StyleSheet.hairlineWidth,
    flexDirection: 'row',
    gap: 12,
    minHeight: 88,
    padding: 16,
  },
  missedDaysCopy: { flex: 1, gap: 3 },
  missedDaysTitle: { color: colors.ink, fontSize: 16, fontWeight: '700' },
  missedDaysText: { color: colors.slate, fontSize: 14, lineHeight: 20 },
  hideMissedDays: {
    alignSelf: 'flex-start',
    justifyContent: 'center',
    minHeight: 40,
    paddingHorizontal: 4,
  },
  hideMissedDaysText: { color: colors.leaf, fontSize: 15, fontWeight: '700' },
  dateHeader: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between' },
  dayFeelingHeart: { alignItems: 'center', height: 28, justifyContent: 'center', width: 28 },
  passedHeader: { alignItems: 'center', flexDirection: 'row', gap: 10 },
  header: { alignItems: 'center', flexDirection: 'row', gap: 10 },
  penDisc: {
    alignItems: 'center',
    backgroundColor: colors.diary,
    borderRadius: 20,
    height: 40,
    justifyContent: 'center',
    width: 40,
  },
  passedDisc: {
    alignItems: 'center',
    backgroundColor: colors.paper,
    borderRadius: 20,
    height: 40,
    justifyContent: 'center',
    width: 40,
  },
  title: {
    color: colors.ink,
    flex: 1,
    fontFamily: 'Kalam_700Bold',
    fontSize: 22,
    lineHeight: 22,
  },
  date: { color: colors.slate, fontSize: 15, fontWeight: '600', maxWidth: 96, textAlign: 'right' },
  excerpt: {
    color: colors.slate,
    fontFamily: 'PatrickHand_400Regular',
    fontSize: 22,
    lineHeight: 24,
    paddingRight: 5,
  },
  reflectButton: { alignSelf: 'flex-start', justifyContent: 'center', minHeight: 40 },
  reflectButtonText: { color: colors.leaf, fontSize: 15, fontWeight: '700' },
  metadata: {
    alignItems: 'center',
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    minHeight: 28,
  },
  previewSection: { gap: 10 },
  imagePreviewSection: { gap: 7 },
  cardGallery: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  cardImage: {
    backgroundColor: colors.surface,
    borderCurve: 'continuous',
    borderRadius: 12,
    height: 88,
    width: '31.5%',
  },
  remainingAttachmentCount: { alignItems: 'center', alignSelf: 'flex-start', flexDirection: 'row', gap: 3 },
  remainingAttachmentText: { color: colors.slate, fontSize: 13, fontVariant: ['tabular-nums'], fontWeight: '700' },
  cardAudioPreview: {
    alignItems: 'center',
    alignSelf: 'flex-start',
    backgroundColor: colors.surface,
    borderCurve: 'continuous',
    borderRadius: 16,
    flexDirection: 'row',
    gap: 8,
    minHeight: 48,
    paddingHorizontal: 10,
  },
  cardAudioDisc: {
    alignItems: 'center',
    backgroundColor: colors.diary,
    borderRadius: 14,
    height: 28,
    justifyContent: 'center',
    width: 28,
  },
  cardAudioLabel: { color: colors.ink, fontSize: 14, fontWeight: '700' },
  attachments: { alignItems: 'center', flexDirection: 'row', gap: 8, minHeight: 28 },
  imageIndicator: { alignItems: 'center', flexDirection: 'row', gap: 3 },
  count: { color: colors.slate, fontSize: 13, fontVariant: ['tabular-nums'], fontWeight: '700' },
  addendaMarker: { color: colors.slate, fontSize: 14, fontWeight: '700' },
  pagination: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 6,
    marginTop: 4,
  },
  pageButton: { alignItems: 'center', flexDirection: 'row', gap: 3, minHeight: 44, paddingHorizontal: 4 },
  pageButtonDisabled: { opacity: 0.35 },
  pageButtonLabel: { color: colors.leaf, fontSize: 15, fontWeight: '700' },
  pageStatus: { color: colors.slate, fontSize: 13, fontVariant: ['tabular-nums'], fontWeight: '600' },
  scrollToTop: {
    alignItems: 'center',
    backgroundColor: colors.leaf,
    borderRadius: 24,
    boxShadow: '0 4px 12px rgba(28, 37, 30, 0.18)',
    height: 48,
    justifyContent: 'center',
    position: 'absolute',
    right: 24,
    width: 48,
  },
  pressed: { opacity: 0.72, transform: [{ scale: 0.992 }] },
});
