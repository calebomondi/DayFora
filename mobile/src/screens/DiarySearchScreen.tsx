import { useEffect, useMemo, useState } from 'react';
import type { Session } from '@supabase/supabase-js';
import { CircleChevronLeft, Images, Search, Volume2, X } from 'lucide-react-native';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors } from '../components/ui';
import { searchExplore } from '../lib/api';
import type { DiaryEntry } from '../lib/types';
import { formatEntryDate } from './LibraryScreen';

type TimeFilter = 'all' | 'week';
type MediaFilter = 'audio' | 'image' | null;
type MoodFilter = 'happy_fun' | 'sad_dull' | 'mixed' | 'quiet' | null;

export function DiarySearchScreen({
  onBack,
  onOpenEntry,
  session,
}: {
  onBack: () => void;
  onOpenEntry: (entry: DiaryEntry) => void;
  session: Session;
}) {
  const [query, setQuery] = useState('');
  const [timeFilter, setTimeFilter] = useState<TimeFilter>('all');
  const [mediaFilter, setMediaFilter] = useState<MediaFilter>(null);
  const [moodFilter, setMoodFilter] = useState<MoodFilter>(null);
  const [results, setResults] = useState<DiaryEntry[] | null>(null);
  const [resultsKey, setResultsKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const naturalDate = useMemo(() => parseDatePhrase(query), [query]);
  const normalizedQuery = naturalDate ? removeDatePhrase(query).trim() : query.trim();
  const dateFrom = naturalDate?.from ?? (timeFilter === 'week' ? startOfWeek() : undefined);
  const dateTo =
    naturalDate?.to ?? (timeFilter === 'week' ? localDateString(new Date()) : undefined);
  const hasCriteria = true;
  const searchKey = JSON.stringify({ dateFrom, dateTo, mediaFilter, moodFilter, normalizedQuery, timeFilter });
  const visibleResults = hasCriteria && resultsKey === searchKey ? results : null;

  useEffect(() => {
    if (!hasCriteria) {
      return;
    }
    let active = true;
    const timer = setTimeout(() => {
      setLoading(true);
      void searchExplore(session, {
        query: normalizedQuery || undefined,
        date_from: dateFrom,
        date_to: dateTo,
        media_type: mediaFilter ?? undefined,
        mood: moodFilter ?? undefined,
      })
        .then((found) => {
          if (active) {
            setResults(found);
            setResultsKey(searchKey);
          }
        })
        .catch((error) => {
          console.error('Failed to search diary:', error);
          if (active) {
            setResults([]);
            setResultsKey(searchKey);
          }
        })
        .finally(() => active && setLoading(false));
    }, 260);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [dateFrom, dateTo, hasCriteria, mediaFilter, moodFilter, normalizedQuery, searchKey, session]);

  const insets = useSafeAreaInsets();

  return (
    <ScrollView
      contentContainerStyle={[styles.container, { paddingTop: insets.top + 12 }]}
      contentInsetAdjustmentBehavior="automatic"
      keyboardShouldPersistTaps="handled"
    >
      <View style={styles.header}>
        <Pressable
          accessibilityLabel="Back to diary"
          accessibilityRole="button"
          onPress={onBack}
          style={styles.backButton}
        >
          <CircleChevronLeft
            color={colors.leaf}
            size={30}
            strokeWidth={3}
            style={styles.backheaderButton}
          />
        </Pressable>
        <Text selectable style={styles.title}>
          Search memories
        </Text>
      </View>
      <View style={styles.searchField}>
        <Search color={colors.slate} size={19} />
        <TextInput
          accessibilityLabel="Search diary memories"
          autoFocus
          onChangeText={setQuery}
          placeholder="What are you looking for?"
          placeholderTextColor={colors.slate}
          style={styles.input}
          value={query}
        />
        {query ? (
          <Pressable
            accessibilityLabel="Clear search"
            accessibilityRole="button"
            onPress={() => setQuery('')}
          >
            <X color={colors.slate} size={18} />
          </Pressable>
        ) : null}
      </View>
      <View style={styles.filterRow}>
        <FilterChip
          active={timeFilter === 'all'}
          label="All time"
          onPress={() => setTimeFilter('all')}
        />
        <FilterChip
          active={timeFilter === 'week'}
          label="This week"
          onPress={() => setTimeFilter(timeFilter === 'week' ? 'all' : 'week')}
        />
        <FilterChip
          active={mediaFilter === 'image'}
          label="Photos"
          onPress={() => setMediaFilter(mediaFilter === 'image' ? null : 'image')}
        />
        <FilterChip
          active={mediaFilter === 'audio'}
          label="Audio"
          onPress={() => setMediaFilter(mediaFilter === 'audio' ? null : 'audio')}
        />
        <FilterChip active={moodFilter === 'happy_fun'} label="Happy/fun" onPress={() => setMoodFilter(moodFilter === 'happy_fun' ? null : 'happy_fun')} />
        <FilterChip active={moodFilter === 'sad_dull'} label="Sad/dull" onPress={() => setMoodFilter(moodFilter === 'sad_dull' ? null : 'sad_dull')} />
        <FilterChip active={moodFilter === 'mixed'} label="Mixed" onPress={() => setMoodFilter(moodFilter === 'mixed' ? null : 'mixed')} />
        <FilterChip active={moodFilter === 'quiet'} label="Quiet" onPress={() => setMoodFilter(moodFilter === 'quiet' ? null : 'quiet')} />
      </View>
      {naturalDate ? (
        <View style={styles.visibleDate}>
          <Text style={styles.visibleDateText}>{naturalDate.label}</Text>
        </View>
      ) : null}

      {loading ? (
        <Text accessibilityLiveRegion="polite" style={styles.status}>
          Searching your approved memories…
        </Text>
      ) : null}
      {visibleResults ? (
        <SearchResults
          results={visibleResults}
          onOpenEntry={onOpenEntry}
        />
      ) : !loading ? (
        <Text selectable style={styles.hint}>
          Search entry titles, dates, photos, voice notes, or an explicit mood.
        </Text>
      ) : null}
    </ScrollView>
  );
}

function SearchResults({
  onOpenEntry,
  results,
}: {
  onOpenEntry: (entry: DiaryEntry) => void;
  results: DiaryEntry[];
}) {
  if (!results.length)
    return (
      <Text selectable style={styles.hint}>
        No approved memories match these filters.
      </Text>
    );
  const range = `${formatShortDate(results[results.length - 1].local_date)} – ${formatShortDate(results[0].local_date)}`;
  return (
    <View style={styles.resultsWrap}>
      <Text selectable style={styles.resultMeta}>
        Found across {results.length} {results.length === 1 ? 'entry' : 'entries'} · {range}
      </Text>
      <Text style={styles.matchesTitle}>Matching entries</Text>
      <View style={styles.resultsList}>
        {results.map((entry) => (
          <Pressable
            accessibilityRole="button"
            key={entry.id}
            onPress={() => onOpenEntry(entry)}
            style={({ pressed }) => [styles.resultRow, pressed && styles.pressed]}
          >
            <View style={styles.resultCopy}>
              <Text selectable style={styles.resultDate}>{formatEntryDate(entry.local_date)}</Text>
              <Text selectable style={styles.resultTitle}>
                {entry.title || 'Untitled reflection'}
              </Text>
              {entry.audio_count || entry.image_count ? (
                <View
                  accessibilityLabel={`${entry.image_count} ${entry.image_count === 1 ? 'image' : 'images'} and ${entry.audio_count} ${entry.audio_count === 1 ? 'voice note' : 'voice notes'} attached`}
                  style={styles.resultAttachments}
                >
                  {entry.image_count ? (
                    <View accessible={false} style={styles.resultAttachment}>
                      <Images color={colors.slate} size={16} strokeWidth={2.5} />
                      <Text style={styles.resultAttachmentCount}>{entry.image_count}</Text>
                    </View>
                  ) : null}
                  {entry.audio_count ? (
                    <View accessible={false} style={styles.resultAttachment}>
                      <Volume2 color={colors.slate} size={16} strokeWidth={2.5} />
                      <Text style={styles.resultAttachmentCount}>{entry.audio_count}</Text>
                    </View>
                  ) : null}
                </View>
              ) : null}
            </View>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

function FilterChip({
  active,
  label,
  onPress,
}: {
  active: boolean;
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
      onPress={onPress}
      style={({ pressed }) => [styles.chip, active && styles.chipActive, pressed && styles.pressed]}
    >
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </Pressable>
  );
}

function localDateString(value: Date) {
  const year = value.getFullYear();
  const month = `${value.getMonth() + 1}`.padStart(2, '0');
  const day = `${value.getDate()}`.padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function startOfWeek() {
  const today = new Date();
  today.setDate(today.getDate() - today.getDay());
  return localDateString(today);
}

function parseDatePhrase(value: string): { from: string; label: string; to: string } | null {
  const range = value.match(/\b(\d{4}-\d{2}-\d{2})\s*(?:to|–|—|-)\s*(\d{4}-\d{2}-\d{2})\b/i);
  if (range) {
    const [first, second] = [range[1], range[2]].sort();
    return {
      from: first,
      to: second,
      label: `${formatShortDate(first)} – ${formatShortDate(second)}`,
    };
  }
  const exactDate = value.match(/\b\d{4}-\d{2}-\d{2}\b/);
  if (exactDate) {
    return { from: exactDate[0], to: exactDate[0], label: formatShortDate(exactDate[0]) };
  }
  if (!/last\s+sunday/i.test(value)) return null;
  const today = new Date();
  const daysSinceSunday = today.getDay() || 7;
  today.setDate(today.getDate() - daysSinceSunday);
  const date = localDateString(today);
  return { from: date, to: date, label: `Last Sunday · ${formatShortDate(date)}` };
}

function removeDatePhrase(value: string) {
  return value
    .replace(/\b\d{4}-\d{2}-\d{2}\s*(?:to|–|—|-)\s*\d{4}-\d{2}-\d{2}\b/gi, '')
    .replace(/\b\d{4}-\d{2}-\d{2}\b/g, '')
    .replace(/last\s+sunday/gi, '');
}

function formatShortDate(localDate: string) {
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(
    new Date(`${localDate}T12:00:00`),
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.canvas,
    flexGrow: 1,
    gap: 16,
    padding: 20,
    paddingBottom: 40,
  },
  backheaderButton: { backgroundColor: colors.accentWash, borderRadius: 999 },
  header: { alignItems: 'center', flexDirection: 'row', gap: 10, minHeight: 44 },
  backButton: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 22,
    height: 44,
    justifyContent: 'center',
    width: 44,
  },
  title: { color: colors.ink, fontSize: 25, fontWeight: '700' },
  searchField: {
    alignItems: 'center',
    backgroundColor: colors.paper,
    borderColor: colors.line,
    borderRadius: 16,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 9,
    minHeight: 52,
    paddingHorizontal: 14,
  },
  input: { color: colors.ink, flex: 1, fontSize: 18, paddingVertical: 12 },
  filterRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  activityFilters: { gap: 8 },
  chip: {
    backgroundColor: colors.surface,
    borderRadius: 999,
    minHeight: 36,
    justifyContent: 'center',
    paddingHorizontal: 13,
  },
  chipActive: { backgroundColor: colors.accentWash },
  chipText: { color: colors.slate, fontSize: 13, fontWeight: '700' },
  chipTextActive: { color: colors.leaf },
  visibleDate: {
    alignSelf: 'flex-start',
    backgroundColor: colors.accentWash,
    borderRadius: 999,
    paddingHorizontal: 11,
    paddingVertical: 7,
  },
  visibleDateText: { color: colors.leaf, fontSize: 13, fontWeight: '700' },
  status: { color: colors.slate, fontSize: 15 },
  hint: { color: colors.slate, fontSize: 15, lineHeight: 22 },
  resultsWrap: { gap: 14 },
  resultMeta: { color: colors.slate, fontSize: 13, fontWeight: '700' },
  recapOffer: {
    backgroundColor: colors.surface,
    borderCurve: 'continuous',
    borderRadius: 18,
    gap: 4,
    padding: 15,
  },
  recapOfferTitle: { color: colors.ink, fontSize: 16, fontWeight: '700' },
  recapOfferCopy: { color: colors.slate, fontSize: 13, lineHeight: 19 },
  recapCard: {
    backgroundColor: colors.paper,
    borderCurve: 'continuous',
    borderRadius: 18,
    gap: 8,
    padding: 16,
  },
  recapLabel: { color: colors.slate, fontSize: 12, fontWeight: '700' },
  recapText: { color: colors.ink, fontSize: 16, lineHeight: 23 },
  recapMeta: { color: colors.slate, fontSize: 12 },
  matchesTitle: { color: colors.ink, fontSize: 17, fontWeight: '700', marginTop: 4 },
  resultsList: {
    backgroundColor: colors.surface,
    borderCurve: 'continuous',
    borderRadius: 20,
    overflow: 'hidden',
  },
  resultRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 10,
    minHeight: 74,
    paddingHorizontal: 15,
    paddingVertical: 12,
  },
  resultCopy: { flex: 1, gap: 5 },
  resultTitle: { color: colors.ink, fontSize: 18, fontWeight: '700' },
  resultDate: {
    color: colors.slate,
    fontSize: 14,
    fontWeight: '700',
  },
  resultAttachments: { alignItems: 'center', flexDirection: 'row', gap: 10, minHeight: 20 },
  resultAttachment: { alignItems: 'center', flexDirection: 'row', gap: 4 },
  resultAttachmentCount: {
    color: colors.slate,
    fontSize: 13,
    fontVariant: ['tabular-nums'],
    fontWeight: '700',
  },
  pressed: { opacity: 0.7 },
});
