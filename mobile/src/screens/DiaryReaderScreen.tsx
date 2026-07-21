import { useCallback, useEffect, useState } from 'react';
import { useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import type { Session } from '@supabase/supabase-js';
import { Heart, ImageIcon, Pause, PenLine, Play, Trash2, Volume2, X } from 'lucide-react-native';
import {
  AccessibilityInfo,
  Alert,
  Animated,
  BackHandler,
  Image,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { colors } from '../components/ui';
import {
  getDiaryEntryMedia,
  listDiaryAddenda,
  removeAddendumMedia,
  removeAddendumText,
  removeTodayEntryMedia,
} from '../lib/api';
import type { DiaryAddendum, DiaryEntry, DiaryMedia } from '../lib/types';
import { formatEntryDate } from './LibraryScreen';

import { useSafeAreaInsets } from 'react-native-safe-area-context';

type DiaryReaderScreenProps = {
  entry: DiaryEntry;
  isToday: boolean;
  session: Session;
  onAddReflection: () => void;
  onClose: () => void;
  onEdit: () => void;
  onEntryUpdated: (entry: DiaryEntry) => void;
};

export function DiaryReaderScreen({
  entry,
  isToday,
  session,
  onAddReflection,
  onClose,
  onEdit,
  onEntryUpdated,
}: DiaryReaderScreenProps) {
  const [addenda, setAddenda] = useState<DiaryAddendum[]>([]);
  const [media, setMedia] = useState<DiaryMedia[]>([]);
  const [loadingMedia, setLoadingMedia] = useState(true);
  const [mediaError, setMediaError] = useState<string | null>(null);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [opacity] = useState(() => new Animated.Value(0));
  const [scale] = useState(() => new Animated.Value(0.985));
  const [fullImage, setFullImage] = useState<DiaryMedia | null>(null);

  useEffect(() => {
    let active = true;
    try {
      void AccessibilityInfo.isReduceMotionEnabled().then((enabled) => {
        if (!active) return;
        setReducedMotion(enabled);
        if (enabled) {
          opacity.setValue(1);
          scale.setValue(1);
          return;
        }
        Animated.parallel([
          Animated.timing(opacity, { duration: 200, toValue: 1, useNativeDriver: Platform.OS !== 'web' }),
          Animated.timing(scale, { duration: 200, toValue: 1, useNativeDriver: Platform.OS !== 'web' }),
        ]).start();
      });
    } catch {}
    return () => {
      active = false;
    };
  }, [opacity, scale]);

  useEffect(() => {
    let active = true;
    async function loadMedia() {
      try {
        const result = await getDiaryEntryMedia(session, entry.id);
        if (active) setMedia(result);
      } catch (error) {
        console.error('Failed to load diary media:', error);
        if (active) setMediaError('Original attachments could not be loaded right now.');
      } finally {
        if (active) setLoadingMedia(false);
      }
    }
    void loadMedia();
    return () => {
      active = false;
    };
  }, [entry.id, session]);

  useEffect(() => {
    let active = true;
    void listDiaryAddenda(session, entry.id)
      .then((result) => {
        if (active) setAddenda(result);
      })
      .catch((error) => console.error('Failed to load reflections:', error));
    return () => {
      active = false;
    };
  }, [entry.id, session]);

  const close = useCallback(() => {
    if (reducedMotion) {
      onClose();
      return;
    }
    Animated.parallel([
      Animated.timing(opacity, { duration: 160, toValue: 0, useNativeDriver: Platform.OS !== 'web' }),
      Animated.timing(scale, { duration: 160, toValue: 0.985, useNativeDriver: Platform.OS !== 'web' }),
    ]).start(({ finished }) => {
      if (finished) onClose();
    });
  }, [onClose, opacity, reducedMotion, scale]);

  useEffect(() => {
    if (Platform.OS !== 'android') return;
    const subscription = BackHandler.addEventListener('hardwareBackPress', () => {
      close();
      return true;
    });
    return () => subscription.remove();
  }, [close]);

  const images = media.filter((item) => item.media_type === 'image');
  const audio = media.filter((item) => item.media_type === 'audio');
  const title = entry.title.trim() || 'Untitled reflection';
  const body = entry.body.trim() || 'No written reflection was saved.';

  const insets = useSafeAreaInsets();

  async function reloadAddenda() {
    try {
      setAddenda(await listDiaryAddenda(session, entry.id));
    } catch (error) {
      console.error('Failed to refresh reflections:', error);
      Alert.alert('Could not update this reflection', 'Please try again.');
    }
  }

  async function removeOriginalMedia(mediaId: string) {
    try {
      const updated = await removeTodayEntryMedia(session, entry.id, mediaId);
      setMedia((current) => current.filter((item) => item.id !== mediaId));
      onEntryUpdated(updated);
    } catch (error) {
      console.error('Failed to remove original attachment:', error);
      Alert.alert('Could not remove this attachment', 'Keep a note or another attachment, then try again.');
    }
  }

  function confirmOriginalMediaRemoval(media: DiaryMedia) {
    Alert.alert(
      'Remove attachment?',
      'This removes the original attachment from today’s entry permanently.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Remove',
          style: 'destructive',
          onPress: () => void removeOriginalMedia(media.id),
        },
      ],
    );
  }

  async function removeReflectionMedia(addendumId: string, mediaId: string) {
    try {
      await removeAddendumMedia(session, addendumId, mediaId);
      await reloadAddenda();
    } catch (error) {
      console.error('Failed to remove reflection attachment:', error);
      Alert.alert('Could not remove this attachment', 'Please try again.');
    }
  }

  async function removeReflectionText(addendumId: string) {
    try {
      await removeAddendumText(session, addendumId);
      await reloadAddenda();
    } catch (error) {
      console.error('Failed to remove reflection text:', error);
      Alert.alert('Could not remove this reflection', 'Please try again.');
    }
  }

  function confirmReflectionMediaRemoval(addendumId: string, mediaId: string) {
    Alert.alert('Remove attachment?', 'This removes only the attachment added in this reflection.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Remove',
        style: 'destructive',
        onPress: () => void removeReflectionMedia(addendumId, mediaId),
      },
    ]);
  }

  function confirmReflectionTextRemoval(addendumId: string) {
    Alert.alert('Remove reflection text?', 'This keeps the original diary entry unchanged.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Remove',
        style: 'destructive',
        onPress: () => void removeReflectionText(addendumId),
      },
    ]);
  }

  return (
    <Animated.View style={[styles.root, { opacity, transform: [{ scale }] }]}>
      <ScrollView 
        contentContainerStyle={[styles.content, { paddingTop: insets.top + 12 }]} 
        contentInsetAdjustmentBehavior="automatic"
      >
        <View style={styles.topBar}>
          <Pressable
            accessibilityHint="Returns to the diary list"
            accessibilityLabel="Close diary entry"
            accessibilityRole="button"
            hitSlop={8}
            onPress={close}
            style={({ pressed }) => [styles.closeButton, pressed && styles.pressed]}
          >
            <X color={colors.leaf} size={20} strokeWidth={4} />
            {/* <Text style={styles.closeLabel}>Close</Text> */}
          </Pressable>
        </View>

        <View style={styles.readerCard}>
          <View style={styles.dateHeader}>
            <Text selectable style={styles.date}>
              {formatEntryDate(entry.local_date)}
            </Text>
            <DayFeelingHeart entry={entry} />
          </View>

          <View style={styles.header}>
            <View accessible={false} style={styles.penDisc}>
              <PenLine color={colors.ink} size={16} strokeWidth={2} />
            </View>
            <Text selectable style={styles.title}>
              {title}
            </Text>
          </View>

          <View style={styles.metadata}>
            {entry.audio_count ? (
              <Volume2 accessibilityLabel="Audio attached" color={colors.slate} size={16} />
            ) : null}
            {entry.image_count ? (
              <View
                accessibilityLabel={`${entry.image_count} ${entry.image_count === 1 ? 'image attached' : 'images attached'}`}
                style={styles.imageMeta}
              >
                <ImageIcon color={colors.slate} size={16} />
                {entry.image_count > 1 ? (
                  <Text style={styles.imageCount}>{entry.image_count}</Text>
                ) : null}
              </View>
            ) : null}
            <Pressable
            accessibilityRole="button"
            onPress={isToday ? onEdit : onAddReflection}
            style={({ pressed }) => [styles.entryAction, pressed && styles.pressed]}
          >
            <Text style={styles.entryActionText}>{isToday ? 'Edit today' : 'Add reflection'}</Text>
          </Pressable>
          </View>

          <Text selectable style={styles.body}>
            {body}
          </Text>

          {loadingMedia ? (
            <Text accessibilityLiveRegion="polite" style={styles.loading}>
              Loading original attachments…
            </Text>
          ) : null}
          {mediaError ? (
            <Text accessibilityLiveRegion="polite" selectable style={styles.error}>
              {mediaError}
            </Text>
          ) : null}

          {images.length ? (
            <View style={styles.gallery}>
              {images.map((image, index) => (
                <ImageWithProvenance
                  image={image}
                  index={index}
                  key={image.id}
                  onOpen={() => setFullImage(image)}
                  onRemove={isToday ? () => confirmOriginalMediaRemoval(image) : undefined}
                />
              ))}
            </View>
          ) : null}

          {audio.map((item, index) => (
            <OriginalAudioPlayer
              audio={item}
              index={index}
              key={item.id}
              onRemove={isToday ? () => confirmOriginalMediaRemoval(item) : undefined}
            />
          ))}

          {addenda.map((addendum, index) => (
            <AddendumBlock
              addendum={addendum}
              index={index}
              key={addendum.id}
              onOpenImage={setFullImage}
              onRemoveMedia={(mediaId) => confirmReflectionMediaRemoval(addendum.id, mediaId)}
              onRemoveText={() => confirmReflectionTextRemoval(addendum.id)}
            />
          ))}
        </View>
      </ScrollView>
      <Modal
        accessibilityViewIsModal
        animationType={reducedMotion ? 'none' : 'fade'}
        onRequestClose={() => setFullImage(null)}
        transparent
        visible={fullImage !== null}
      >
        <View style={styles.fullImageOverlay}>
          <Pressable
            accessibilityLabel="Close full image"
            accessibilityRole="button"
            onPress={() => setFullImage(null)}
            style={({ pressed }) => [styles.fullImageClose, pressed && styles.pressed]}
          >
            <X color="#FFFFFF" size={22} strokeWidth={3} />
          </Pressable>
          {fullImage ? (
            <Image
              accessibilityLabel="Full attached image"
              resizeMode="contain"
              source={{ uri: fullImage.signed_url }}
              style={styles.fullImage}
            />
          ) : null}
        </View>
      </Modal>
    </Animated.View>
  );
}

function AddendumBlock({
  addendum,
  index,
  onOpenImage,
  onRemoveMedia,
  onRemoveText,
}: {
  addendum: DiaryAddendum;
  index: number;
  onOpenImage: (image: DiaryMedia) => void;
  onRemoveMedia: (mediaId: string) => void;
  onRemoveText: () => void;
}) {
  const label = new Intl.DateTimeFormat(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(new Date(addendum.created_at));
  const images = addendum.media.filter((item) => item.media_type === 'image');
  const audio = addendum.media.filter((item) => item.media_type === 'audio');
  return (
    <View style={styles.addendum}>
      <View style={styles.addendumDivider} />
      <Text style={styles.addendumLabel}>Added on {label}</Text>
      {addendum.body ? (
        <>
          <Text selectable style={styles.addendumBody}>
            {addendum.body}
          </Text>
          <Pressable
            accessibilityLabel="Remove reflection text"
            accessibilityRole="button"
            onPress={onRemoveText}
            style={({ pressed }) => [styles.removeTextButton, pressed && styles.pressed]}
          >
            <Trash2 color={colors.slate} size={15} strokeWidth={2.25} />
            <Text style={styles.removeTextLabel}>Remove text</Text>
          </Pressable>
        </>
      ) : null}
      {images.length ? (
        <View style={styles.gallery}>
          {images.map((image, imageIndex) => (
            <ImageWithProvenance
              image={image}
              index={imageIndex}
              key={image.id}
              onOpen={() => onOpenImage(image)}
              onRemove={() => onRemoveMedia(image.id)}
            />
          ))}
        </View>
      ) : null}
      {audio.map((item, audioIndex) => (
        <OriginalAudioPlayer
          audio={item}
          index={index + audioIndex}
          key={item.id}
          onRemove={() => onRemoveMedia(item.id)}
          removeAccessibilityLabel={`Remove voice note added in this reflection ${audioIndex + 1}`}
        />
      ))}
    </View>
  );
}

function ImageWithProvenance({
  image,
  index,
  onOpen,
  onRemove,
}: {
  image: DiaryMedia;
  index: number;
  onOpen: () => void;
  onRemove?: () => void;
}) {
  return (
    <View style={styles.imageWrap}>
      <Pressable
        accessibilityHint="Opens this image full screen"
        accessibilityLabel={`Open attached image ${index + 1}`}
        accessibilityRole="button"
        onPress={onOpen}
        style={({ pressed }) => [pressed && styles.pressed]}
      >
        <Image
          accessible={false}
          resizeMode="cover"
          source={{ uri: image.signed_url }}
          style={styles.image}
        />
      </Pressable>
      {onRemove ? (
        <Pressable
          accessibilityLabel={`Remove attached image ${index + 1}`}
          accessibilityRole="button"
          onPress={onRemove}
          style={({ pressed }) => [styles.imageRemoveButton, pressed && styles.pressed]}
        >
          <Trash2 color="#FFFFFF" size={15} strokeWidth={2.5} />
        </Pressable>
      ) : null}
    </View>
  );
}

function OriginalAudioPlayer({
  audio,
  index,
  onRemove,
  removeAccessibilityLabel,
}: {
  audio: DiaryMedia;
  index: number;
  onRemove?: () => void;
  removeAccessibilityLabel?: string;
}) {
  const player = useAudioPlayer(audio.signed_url, { updateInterval: 250 });
  const status = useAudioPlayerStatus(player);
  const progress = status.duration > 0 ? Math.min(status.currentTime / status.duration, 1) : 0;
  const duration = formatDuration(status.duration);

  function togglePlayback() {
    if (status.playing) player.pause();
    else player.play();
  }

  return (
    <View style={styles.audioBlock}>
      <View style={styles.audioHeader}>
        <View accessible={false} style={styles.audioDisc}>
          <Volume2 color={colors.ink} size={18} />
        </View>
        <View style={styles.audioTitleWrap}>
          <Text style={styles.audioTitle}>Original voice note {index + 1}</Text>
          <Text style={styles.audioDuration}>{duration}</Text>
        </View>
        <Pressable
          accessibilityHint="Plays the original attached voice note"
          accessibilityLabel={`${status.playing ? 'Pause' : 'Play'} original voice note ${index + 1}, ${duration}`}
          accessibilityRole="button"
          onPress={togglePlayback}
          style={({ pressed }) => [styles.playButton, pressed && styles.pressed]}
        >
          {status.playing ? (
            <Pause color="#FFFFFF" fill="#FFFFFF" size={17} />
          ) : (
            <Play color="#FFFFFF" fill="#FFFFFF" size={17} />
          )}
        </Pressable>
        {onRemove ? (
          <Pressable
            accessibilityLabel={removeAccessibilityLabel ?? `Remove original voice note ${index + 1}`}
            accessibilityRole="button"
            onPress={onRemove}
            style={({ pressed }) => [styles.removeMediaButton, pressed && styles.pressed]}
          >
            <Trash2 color={colors.slate} size={18} strokeWidth={2.25} />
          </Pressable>
        ) : null}
      </View>
      <View
        accessibilityLabel={`Audio progress ${Math.round(progress * 100)} percent`}
        style={styles.progressTrack}
      >
        <View style={[styles.progressFill, { width: `${progress * 100}%` }]} />
      </View>
      <Text style={styles.progressTime}>
        {formatDuration(status.currentTime)} / {duration}
      </Text>
      {status.error ? (
        <Text style={styles.error}>This recording could not play right now.</Text>
      ) : null}
    </View>
  );
}


function formatDuration(value: number) {
  const totalSeconds = Number.isFinite(value) ? Math.max(0, Math.floor(value)) : 0;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

function DayFeelingHeart({ entry }: { entry: DiaryEntry }) {
  const mood = entry.mood ?? entry.day_feeling;
  const heart = heartPresentation(mood);
  if (!heart) return null;
  return (
    <View accessibilityLabel={heart.label} accessibilityRole="image" style={styles.feelingHeart}>
      <Heart color={heart.color} fill={heart.fill} size={20} />
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

const styles = StyleSheet.create({
  root: { backgroundColor: colors.canvas, flex: 1 },
  content: { backgroundColor: colors.canvas, flexGrow: 1, padding: 20, paddingBottom: 36 },
  topBar: { alignItems: 'flex-end', minHeight: 44, paddingBottom: 12 },
  closeButton: {
    alignItems: 'center',
    flexDirection: 'row',
    // gap: 7,
    justifyContent: 'center',
    borderRadius: 22,
    minHeight: 44,
    width: 44,
    paddingHorizontal: 8,
    backgroundColor: colors.accentWash,
  },
  closeLabel: { color: colors.leaf, fontSize: 16, fontWeight: '700' },
  readerCard: {
    backgroundColor: colors.paper,
    borderCurve: 'continuous',
    borderRadius: 24,
    gap: 22,
    padding: 20,
  },
  dateHeader: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between', gap: 10 },
  feelingHeart: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 18,
    height: 36,
    justifyContent: 'center',
    width: 36,
  },
  header: { alignItems: 'flex-start', flexDirection: 'row', gap: 10 },
  penDisc: {
    alignItems: 'center',
    backgroundColor: colors.diary,
    borderRadius: 22,
    height: 42,
    justifyContent: 'center',
    width: 42,
  },
  title: {
    color: colors.ink,
    flex: 1,
    fontFamily: 'Kalam_700Bold',
    fontSize: 28,
    letterSpacing: -0.35,
    // lineHeight: 30,
  },
  date: {
    color: colors.slate,
    fontSize: 15,
    fontWeight: '600',
    maxWidth: 82,
    paddingTop: 3,
    textAlign: 'right',
  },
  metadata: { alignItems: 'center', flexDirection: 'row', flexWrap: 'wrap', gap: 9, minHeight: 28 },
  entryAction: {
    alignSelf: 'flex-start',
    minHeight: 44,
    justifyContent: 'center',
    paddingHorizontal: 2,
  },
  entryActionText: { color: colors.leaf, fontSize: 15, fontWeight: '700' },
  imageMeta: { alignItems: 'center', flexDirection: 'row', gap: 3 },
  imageCount: {
    color: colors.slate,
    fontSize: 13,
    fontVariant: ['tabular-nums'],
    fontWeight: '700',
  },
  body: { color: colors.ink, fontFamily: 'PatrickHand_400Regular', fontSize: 22, lineHeight: 29 },
  loading: { color: colors.slate, fontSize: 14, lineHeight: 21 },
  error: { color: colors.slate, fontSize: 14, lineHeight: 21 },
  gallery: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  imageWrap: { gap: 7, minWidth: 130, position: 'relative', width: '48%' },
  image: {
    backgroundColor: colors.surface,
    borderCurve: 'continuous',
    borderRadius: 16,
    height: 154,
    width: '100%',
  },
  imageRemoveButton: {
    alignItems: 'center',
    backgroundColor: 'rgba(25, 34, 27, 0.72)',
    borderRadius: 18,
    height: 36,
    justifyContent: 'center',
    position: 'absolute',
    right: 8,
    top: 8,
    width: 36,
  },
  fullImageOverlay: {
    alignItems: 'center',
    backgroundColor: 'rgba(16, 23, 18, 0.94)',
    flex: 1,
    justifyContent: 'center',
    padding: 20,
  },
  fullImage: { height: '88%', width: '100%' },
  fullImageClose: {
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.18)',
    borderRadius: 22,
    height: 44,
    justifyContent: 'center',
    position: 'absolute',
    right: 20,
    top: 54,
    width: 44,
    zIndex: 1,
  },
  provenanceBlock: { gap: 4 },
  provenanceLabel: { color: colors.slate, fontSize: 12, fontWeight: '700' },
  provenanceText: { color: colors.slate, fontSize: 14, lineHeight: 21 },
  audioBlock: {
    backgroundColor: colors.surface,
    borderCurve: 'continuous',
    borderRadius: 18,
    gap: 10,
    padding: 14,
  },
  addendum: { gap: 14 },
  addendumDivider: { backgroundColor: colors.line, height: StyleSheet.hairlineWidth, marginTop: 4 },
  addendumLabel: { color: colors.slate, fontSize: 13, fontWeight: '700' },
  addendumBody: { color: colors.ink, fontSize: 17, lineHeight: 27 },
  removeTextButton: { alignItems: 'center', alignSelf: 'flex-start', flexDirection: 'row', gap: 5, minHeight: 36 },
  removeTextLabel: { color: colors.slate, fontSize: 13, fontWeight: '700' },
  audioHeader: { alignItems: 'center', flexDirection: 'row', gap: 10 },
  audioDisc: {
    alignItems: 'center',
    backgroundColor: colors.diary,
    borderRadius: 20,
    height: 40,
    justifyContent: 'center',
    width: 40,
  },
  audioTitleWrap: { flex: 1, gap: 2 },
  audioTitle: { color: colors.ink, fontSize: 15, fontWeight: '700' },
  audioDuration: { color: colors.slate, fontSize: 13, fontVariant: ['tabular-nums'] },
  playButton: {
    alignItems: 'center',
    backgroundColor: colors.leaf,
    borderRadius: 22,
    height: 44,
    justifyContent: 'center',
    width: 44,
  },
  removeMediaButton: {
    alignItems: 'center',
    borderRadius: 22,
    height: 44,
    justifyContent: 'center',
    width: 44,
  },
  progressTrack: { backgroundColor: colors.line, borderRadius: 999, height: 4, overflow: 'hidden' },
  progressFill: { backgroundColor: colors.leaf, borderRadius: 999, height: '100%' },
  progressTime: {
    alignSelf: 'flex-end',
    color: colors.slate,
    fontSize: 12,
    fontVariant: ['tabular-nums'],
  },
  pressed: { opacity: 0.72, transform: [{ scale: 0.96 }] },
});
