import { useEffect, useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import type { Session } from '@supabase/supabase-js';
import { StyleSheet, Text, useColorScheme, View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import * as SplashScreen from 'expo-splash-screen';
import { useFonts, Kalam_700Bold } from '@expo-google-fonts/kalam';
import { ABeeZee_400Regular } from '@expo-google-fonts/abeezee';
import { PatrickHand_400Regular } from '@expo-google-fonts/patrick-hand';

import { AppTabBar, type MainTab } from './src/components/AppTabBar';
import { RootTopBar } from './src/components/RootTopBar';
import { colors, PrimaryButton } from './src/components/ui';
import { AuthScreen } from './src/screens/AuthScreen';
import { DiaryAddendumScreen } from './src/screens/DiaryAddendumScreen';
import { DiaryEditorScreen } from './src/screens/DiaryEditorScreen';
import { DiaryReaderScreen } from './src/screens/DiaryReaderScreen';
import { DiarySearchScreen } from './src/screens/DiarySearchScreen';
import { ExploreAskScreen } from './src/screens/ExploreAskScreen';
import { ExploreDiaryScreen } from './src/screens/ExploreDiaryScreen';
import { LibraryScreen } from './src/screens/LibraryScreen';
import { NotificationSettingsScreen } from './src/screens/NotificationSettingsScreen';
import { OnboardingScreen } from './src/screens/OnboardingScreen';
import { ProfileScreen } from './src/screens/ProfileScreen';
import {
  completeOnboarding,
  createDirectEntry,
  getProfile,
  listDiaryEntries,
  updateDirectEntry,
} from './src/lib/api';
import { registerForPushNotifications } from './src/lib/notifications';
import { supabase } from './src/lib/supabase';
import type { DayFeeling, DiaryEntry } from './src/lib/types';

type Screen =
  | MainTab
  | 'onboarding'
  | 'editor'
  | 'addendum'
  | 'diary-reader'
  | 'diary-search'
  | 'explore-ask'
  | 'profile'
  | 'settings';

SplashScreen.preventAutoHideAsync();

export default function App() {
  const colorScheme = useColorScheme();
  const [session, setSession] = useState<Session | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [profileReady, setProfileReady] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [profileRefresh, setProfileRefresh] = useState(0);
  const [needsOnboarding, setNeedsOnboarding] = useState(false);
  const [screen, setScreen] = useState<Screen>('explore');
  const [utilityReturnTab, setUtilityReturnTab] = useState<MainTab>('explore');
  const [entries, setEntries] = useState<DiaryEntry[]>([]);
  const [selectedEntry, setSelectedEntry] = useState<DiaryEntry | null>(null);
  const [readerReturnScreen, setReaderReturnScreen] = useState<'diary' | 'diary-search' | 'explore'>('explore');
  const [entryTitle, setEntryTitle] = useState('');
  const [entryBody, setEntryBody] = useState('');
  const [entryMood, setEntryMood] = useState<DayFeeling | null>(null);
  const [editorMediaIds, setEditorMediaIds] = useState<string[]>([]);
  const [editorMode, setEditorMode] = useState<'create' | 'edit'>('create');
  const [editorSaving, setEditorSaving] = useState(false);
  const [diaryStartDate, setDiaryStartDate] = useState<string | null>(null);
  const [diaryScrollOffset, setDiaryScrollOffset] = useState(0);

  const [fontsLoaded, fontError] = useFonts({
    Kalam_700Bold,
    ABeeZee_400Regular,
    PatrickHand_400Regular,
  });

  useEffect(() => {
    if (fontsLoaded || fontError) void SplashScreen.hideAsync();
  }, [fontError, fontsLoaded]);

  useEffect(() => {
    void supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setAuthReady(true);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, nextSession) =>
      setSession(nextSession),
    );
    return () => listener.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (session) void registerForPushNotifications(session);
  }, [session]);

  useEffect(() => {
    let active = true;
    if (!session) {
      setProfileReady(true);
      setNeedsOnboarding(false);
      setScreen('explore');
      return () => {
        active = false;
      };
    }
    setProfileReady(false);
    setProfileError(null);
    void getProfile(session)
      .then((profile) => {
        if (!active) return;
        setNeedsOnboarding(!profile.onboarding_completed_at);
        setDiaryStartDate(localDateFromTimestamp(profile.created_at));
        setScreen(profile.onboarding_completed_at ? 'explore' : 'onboarding');
      })
      .catch((error) => {
        console.error('Failed to load profile:', error);
        if (active) setProfileError('We could not load your account state.');
      })
      .finally(() => active && setProfileReady(true));
    return () => {
      active = false;
    };
  }, [profileRefresh, session]);

  useEffect(() => {
    if (!session || screen !== 'diary') return;
    let active = true;
    void listDiaryEntries(session)
      .then((loaded) => active && setEntries(loaded))
      .catch((error) => console.error('Failed to load diary history:', error));
    return () => {
      active = false;
    };
  }, [screen, session]);

  function openComposer() {
    setEditorMode('create');
    setEntryTitle('');
    setEntryBody('');
    setEntryMood(null);
    setEditorMediaIds([]);
    setScreen('editor');
  }

  function openTodayEdit(entry: DiaryEntry) {
    setEditorMode('edit');
    setEntryTitle(entry.title);
    setEntryBody(entry.body ?? '');
    setEntryMood(fromV1Mood(entry.mood));
    setEditorMediaIds([]);
    setSelectedEntry(entry);
    setScreen('editor');
  }

  async function saveEntry() {
    if (!session || !entryTitle.trim() || (!entryBody.trim() && !editorMediaIds.length)) return;
    setEditorSaving(true);
    try {
      const payload = {
        title: entryTitle.trim(),
        body: entryBody.trim() || undefined,
        mood: toV1Mood(entryMood),
        media_item_ids: editorMediaIds,
      };
      const saved =
        editorMode === 'edit' && selectedEntry
          ? await updateDirectEntry(session, selectedEntry.id, payload)
          : await createDirectEntry(session, payload);
      setSelectedEntry(saved);
      setEntries((current) => [saved, ...current.filter((entry) => entry.id !== saved.id)]);
      setScreen('diary-reader');
    } catch (error) {
      console.error('Failed to save diary entry:', error);
    } finally {
      setEditorSaving(false);
    }
  }

  async function finishOnboarding() {
    if (!session) return;
    await completeOnboarding(session);
    setNeedsOnboarding(false);
    setScreen('explore');
  }

  function openEntry(entry: DiaryEntry, returnScreen: 'diary' | 'diary-search' | 'explore') {
    setSelectedEntry(entry);
    setReaderReturnScreen(returnScreen);
    setScreen('diary-reader');
  }

  if (!fontsLoaded && !fontError) return null;
  if (!authReady || (session && !profileReady)) return <LoadingScreen />;
  if (!session) return <AuthScreen />;
  if (profileError) return <ProfileError onRetry={() => setProfileRefresh((value) => value + 1)} />;
  if (needsOnboarding || screen === 'onboarding') return <OnboardingScreen onContinue={finishOnboarding} />;

  if (screen === 'editor') {
    return <SafeAreaProvider><DiaryEditorScreen title={entryTitle} body={entryBody} onTitleChange={setEntryTitle} onBodyChange={setEntryBody} dayFeeling={entryMood} onDayFeelingChange={setEntryMood} mode={editorMode} onBack={() => setScreen(editorMode === 'edit' ? 'diary-reader' : 'explore')} onSaveEntry={saveEntry} onSaveEdit={saveEntry} onMediaUploaded={(mediaItemId) => setEditorMediaIds((current) => [...current, mediaItemId])} isSaving={editorSaving} mediaCount={editorMediaIds.length} /></SafeAreaProvider>;
  }
  if (screen === 'diary-reader' && selectedEntry) {
    return <SafeAreaProvider><DiaryReaderScreen entry={selectedEntry} isToday={selectedEntry.local_date === localDate()} session={session} onAddReflection={() => setScreen('addendum')} onClose={() => setScreen(readerReturnScreen)} onEdit={() => openTodayEdit(selectedEntry)} onEntryUpdated={(updated) => {
      setSelectedEntry(updated);
      setEntries((current) => current.map((item) => item.id === updated.id ? updated : item));
    }} /></SafeAreaProvider>;
  }
  if (screen === 'addendum' && selectedEntry) {
    return <SafeAreaProvider><DiaryAddendumScreen entry={selectedEntry} session={session} onBack={() => setScreen('diary-reader')} onSaved={() => setScreen('diary-reader')} /></SafeAreaProvider>;
  }
  if (screen === 'diary-search') {
    return <SafeAreaProvider><DiarySearchScreen onBack={() => setScreen('explore')} onOpenEntry={(entry) => openEntry(entry, 'diary-search')} session={session} /></SafeAreaProvider>;
  }
  if (screen === 'explore-ask') {
    return <SafeAreaProvider><ExploreAskScreen session={session} onBack={() => setScreen('explore')} onOpenDiary={(entryId) => {
      void listDiaryEntries(session).then((loaded) => {
        setEntries(loaded);
        const entry = loaded.find((item) => item.id === entryId);
        if (entry) openEntry(entry, 'explore');
      }).catch((error) => console.error('Failed to open diary source:', error));
    }} /></SafeAreaProvider>;
  }
  if (screen === 'profile') {
    return <SafeAreaProvider><ProfileScreen displayName={profileDisplayName(session)} email={session.user.email} onBack={() => setScreen(utilityReturnTab)} onSignOut={() => void supabase.auth.signOut().catch((error) => console.error('Failed to sign out:', error))} /></SafeAreaProvider>;
  }
  if (screen === 'settings') {
    return <SafeAreaProvider><NotificationSettingsScreen session={session} onBack={() => setScreen(utilityReturnTab)} /></SafeAreaProvider>;
  }

  const activeTab: MainTab = screen === 'diary' ? 'diary' : 'explore';
  const mainContent = activeTab === 'diary'
    ? <LibraryScreen entries={entries} timelineStartDate={diaryStartDate} scrollOffset={diaryScrollOffset} showCaptureToday={!entries.some((entry) => entry.local_date === localDate())} onCaptureToday={openComposer} onOpenEntry={(entry) => openEntry(entry, 'diary')} onSearch={() => setScreen('diary-search')} onScrollOffsetChange={setDiaryScrollOffset} />
    : <ExploreDiaryScreen session={session} onCapture={openComposer} onOpenSearch={() => setScreen('diary-search')} onOpenAsk={() => setScreen('explore-ask')} onOpenEntry={(entry) => openEntry(entry, 'explore')} />;

  return <SafeAreaProvider><View style={styles.root}><StatusBar style={colorScheme === 'dark' ? 'light' : 'dark'} /><RootTopBar onOpenProfile={() => { setUtilityReturnTab(activeTab); setScreen('profile'); }} onOpenSettings={() => { setUtilityReturnTab(activeTab); setScreen('settings'); }} /><View style={styles.mainContent}>{mainContent}</View><AppTabBar activeTab={activeTab} onSelect={setScreen} /></View></SafeAreaProvider>;
}

function localDate() {
  const value = new Date();
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;
}

function localDateFromTimestamp(timestamp: string | null) {
  if (!timestamp) return null;
  const value = new Date(timestamp);
  if (Number.isNaN(value.getTime())) return null;
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;
}

function profileDisplayName(session: Session) {
  const metadata = session.user.user_metadata as Record<string, unknown>;
  return ['display_name', 'full_name', 'name'].map((key) => metadata[key]).find((value): value is string => typeof value === 'string' && Boolean(value.trim()))?.trim() || session.user.email?.split('@')[0] || 'Your DayFora account';
}

function toV1Mood(feeling: DayFeeling | null): 'happy_fun' | 'sad_dull' | 'mixed' | 'quiet' | null {
  if (feeling === 'loved') return 'happy_fun';
  if (feeling === 'low') return 'sad_dull';
  return feeling;
}

function fromV1Mood(mood: string | null): DayFeeling | null {
  if (mood === 'happy_fun') return 'loved';
  if (mood === 'sad_dull') return 'low';
  return mood === 'mixed' || mood === 'quiet' ? mood : null;
}

function LoadingScreen() { return <View style={styles.loading}><Text style={styles.loadingText}>Opening your private space…</Text></View>; }
function ProfileError({ onRetry }: { onRetry: () => void }) { return <View style={styles.loading}><Text style={styles.errorTitle}>Your space is not ready yet.</Text><Text style={styles.errorCopy}>Check your connection and try again.</Text><PrimaryButton onPress={onRetry} tone="leaf">Try again</PrimaryButton></View>; }

const styles = StyleSheet.create({
  root: { backgroundColor: colors.canvas, flex: 1 },
  mainContent: { flex: 1 },
  loading: { alignItems: 'center', backgroundColor: colors.canvas, flex: 1, gap: 12, justifyContent: 'center', padding: 28 },
  loadingText: { color: colors.slate, fontSize: 16 },
  errorTitle: { color: colors.ink, fontSize: 23, fontWeight: '700' },
  errorCopy: { color: colors.slate, fontSize: 16, marginBottom: 8 },
});
