import type { Session } from '@supabase/supabase-js';
import Constants from 'expo-constants';
import { File, UploadType } from 'expo-file-system';
import { fetch as expoFetch } from 'expo/fetch';
import { supabase } from './supabase';
import type { Activity, ActivityEvent, ActivityRecap, ActivitySearchResult, Capture, CaptureProcessResponse, Checkin, DayFeeling, DiaryAddendum, DiaryAskResponse, DiaryEntry, DiaryExploreResponse, DiaryMedia, DiaryRecap, DiaryRecapRequest, Draft, DraftReviewDecision, ExploreAskResponse, ExploreBriefing, ExploreDiscoveryResponse, NotificationPreferences, Profile, ReviewResponse, TodayResponse } from './types';

function resolvedApiBaseUrl(): string | undefined {
  const configuredUrl = process.env.EXPO_PUBLIC_API_BASE_URL;
  if (!configuredUrl || !configuredUrl.includes('://10.0.2.2')) return configuredUrl;

  // 10.0.2.2 is Android Emulator-only. Expo Go's LAN manifest exposes the
  // development machine address that a real phone on the same Wi-Fi can reach.
  const hostUri = Constants.expoConfig?.hostUri;
  if (!hostUri) return configuredUrl;

  try {
    const metroHost = new URL(hostUri.includes('://') ? hostUri : `http://${hostUri}`).hostname;
    return configuredUrl.replace('10.0.2.2', metroHost);
  } catch {
    return configuredUrl;
  }
}

export async function apiRequest<T>(session: Session, path: string, init: RequestInit = {}): Promise<T> {
  const baseUrl = resolvedApiBaseUrl();
  if (!baseUrl) throw new Error('Missing EXPO_PUBLIC_API_BASE_URL');
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${session.access_token}`, 'Content-Type': 'application/json', ...init.headers },
  });
  if (!response.ok) {
    // A deleted account can leave an access token in native storage. Clear this
    // device's session so Supabase emits SIGNED_OUT and the app returns to Auth.
    if (response.status === 401 || response.status === 403) {
      await supabase.auth.signOut({ scope: 'local' }).catch(() => undefined);
    }
    throw new Error(`Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export async function fetchToday(session: Session, localDate?: string): Promise<TodayResponse> {
  const query = localDate ? `?local_date=${encodeURIComponent(localDate)}` : '';
  return apiRequest<TodayResponse>(session, `/v1/today${query}`);
}

export async function fetchExplore(session: Session, localDate?: string): Promise<ExploreBriefing> {
  const query = localDate ? `?date=${encodeURIComponent(localDate)}` : '';
  return apiRequest<ExploreBriefing>(session, `/v1/explore${query}`);
}

export async function fetchDiaryExplore(session: Session, localDate?: string): Promise<DiaryExploreResponse> {
  const query = localDate ? `?date=${encodeURIComponent(localDate)}` : '';
  return apiRequest<DiaryExploreResponse>(session, `/v1/explore${query}`);
}

export async function askDiary(session: Session, query: string): Promise<DiaryAskResponse> {
  return apiRequest<DiaryAskResponse>(session, '/v1/explore/ask', { method: 'POST', body: JSON.stringify({ query }) });
}

export async function dismissAgentInsight(session: Session, insightId: string): Promise<void> {
  await apiRequest<void>(session, `/v1/agent-insights/${insightId}/dismiss`, { method: 'POST' });
}

export async function askAboutStory(
  session: Session,
  filters: { query?: string; date_from?: string; date_to?: string; activity_id?: string; media_type?: 'audio' | 'image' },
): Promise<ExploreAskResponse> {
  return apiRequest<ExploreAskResponse>(session, '/v1/explore/ask', {
    method: 'POST',
    body: JSON.stringify(filters),
  });
}

export async function getProfile(session: Session): Promise<Profile> {
  return apiRequest<Profile>(session, '/v1/profile');
}

export async function completeOnboarding(session: Session): Promise<Profile> {
  return apiRequest<Profile>(session, '/v1/profile/onboarding-complete', { method: 'POST' });
}

export async function listDiaryEntries(session: Session): Promise<DiaryEntry[]> {
  return apiRequest<DiaryEntry[]>(session, '/v1/entries?limit=20');
}

export async function fetchExploreDiscovery(session: Session): Promise<ExploreDiscoveryResponse> {
  return apiRequest<ExploreDiscoveryResponse>(session, '/v1/explore/discover');
}

export async function searchExplore(
  session: Session,
  filters: { query?: string; date_from?: string; date_to?: string; mood?: 'happy_fun' | 'sad_dull' | 'mixed' | 'quiet'; media_type?: 'audio' | 'image' },
): Promise<DiaryEntry[]> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  return apiRequest<DiaryEntry[]>(session, `/v1/explore/search?${params.toString()}`);
}

export type DirectEntryPayload = {
  local_date?: string;
  title: string;
  body?: string;
  mood?: 'happy_fun' | 'sad_dull' | 'mixed' | 'quiet' | null;
  media_item_ids?: string[];
};

export async function createDirectEntry(session: Session, payload: DirectEntryPayload): Promise<DiaryEntry> {
  return apiRequest<DiaryEntry>(session, '/v1/entries', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateDirectEntry(
  session: Session,
  entryId: string,
  payload: DirectEntryPayload,
): Promise<DiaryEntry> {
  return apiRequest<DiaryEntry>(session, `/v1/entries/${entryId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function createDirectUploadUrl(
  session: Session,
  payload: { media_type: 'audio' | 'image'; file_extension: string; content_type: string },
): Promise<{ media_item_id: string; storage_path: string; signed_url: string; token: string }> {
  return apiRequest(session, '/v1/media/upload-url', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getDiaryEntryMedia(session: Session, entryId: string): Promise<DiaryMedia[]> {
  return apiRequest<DiaryMedia[]>(session, `/v1/entries/${entryId}/media`);
}

export async function listDiaryAddenda(session: Session, entryId: string): Promise<DiaryAddendum[]> {
  return apiRequest<DiaryAddendum[]>(session, `/v1/entries/${entryId}/addenda`);
}

export async function removeTodayEntryMedia(
  session: Session,
  entryId: string,
  mediaId: string,
): Promise<DiaryEntry> {
  return apiRequest<DiaryEntry>(session, `/v1/entries/${entryId}/media/${mediaId}`, {
    method: 'DELETE',
  });
}

export async function removeAddendumMedia(
  session: Session,
  addendumId: string,
  mediaId: string,
): Promise<{ deleted: boolean; addendum_deleted: boolean }> {
  return apiRequest(session, `/v1/addenda/${addendumId}/media/${mediaId}`, { method: 'DELETE' });
}

export async function removeAddendumText(
  session: Session,
  addendumId: string,
): Promise<{ deleted: boolean; addendum_deleted: boolean }> {
  return apiRequest(session, `/v1/addenda/${addendumId}`, {
    method: 'PATCH',
    body: JSON.stringify({ body: null }),
  });
}

export async function createDiaryAddendum(
  session: Session,
  entryId: string,
  body?: string,
): Promise<DiaryAddendum> {
  return apiRequest<DiaryAddendum>(session, `/v1/entries/${entryId}/addenda`, {
    method: 'POST',
    body: JSON.stringify({ body: body?.trim() || null }),
  });
}

export async function createAddendumUploadUrl(
  session: Session,
  addendumId: string,
  payload: { media_type: 'audio' | 'image'; file_extension: string; content_type: string },
): Promise<{ media_item_id: string; storage_path: string; signed_url: string; token: string }> {
  return apiRequest(session, `/v1/addenda/${addendumId}/upload-url`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function searchDiaryEntries(
  session: Session,
  filters: {
    query?: string;
    date_from?: string;
    date_to?: string;
    media_type?: 'audio' | 'image';
    activity_id?: string;
  },
): Promise<DiaryEntry[]> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  return apiRequest<DiaryEntry[]>(session, `/v1/diary/search?${params.toString()}`);
}

export async function createActivity(
  session: Session,
  payload: { title: string; purpose?: string; start_date: string; end_date?: string; cadence_type: 'daily' | 'weekdays'; reminder_time?: string | null; cadence_config?: Record<string, unknown> }
): Promise<Activity> {
  return apiRequest<Activity>(session, '/v1/activities', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function upsertTodayEntry(
  session: Session,
  payload: { title: string; body: string; mood?: string; day_feeling?: DayFeeling | null }
): Promise<DiaryEntry> {
  return apiRequest<DiaryEntry>(session, '/v1/entries/today', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function createCapture(
  session: Session,
  payload: {
    initiated_from: 'diary' | 'activity';
    requested_activity_id?: string;
    raw_text?: string;
    local_date?: string;
    day_feeling?: DayFeeling | null;
  }
): Promise<Capture> {
  return apiRequest<Capture>(session, '/v1/captures', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function createUploadUrl(
  session: Session,
  captureId: string,
  payload: { media_type: 'audio' | 'image'; file_extension: string; content_type: string }
): Promise<{ media_item_id: string; storage_path: string; signed_url: string; token: string }> {
  return apiRequest(session, `/v1/captures/${captureId}/upload-url`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export type CaptureProgress = {
  message: string;
  stage: string;
};

export async function processCapture(
  session: Session,
  captureId: string,
  onProgress?: (progress: CaptureProgress) => void,
): Promise<CaptureProcessResponse> {
  const baseUrl = resolvedApiBaseUrl();
  if (!baseUrl) throw new Error('Missing EXPO_PUBLIC_API_BASE_URL');

  const response = await expoFetch(`${baseUrl}/v1/captures/${captureId}/process/events`, {
    method: 'POST',
    headers: {
      Accept: 'text/event-stream',
      Authorization: `Bearer ${session.access_token}`,
    },
  });
  if (!response.ok) throw new Error(`Capture processing could not start (${response.status})`);
  if (!response.body) throw new Error('This device could not receive capture progress updates.');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let completed: CaptureProcessResponse | null = null;

  const processEvent = (eventText: string) => {
    const event = eventText.match(/^event:\s*(.+)$/m)?.[1]?.trim() ?? 'message';
    const dataText = eventText
      .split(/\r?\n/)
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trimStart())
      .join('\n');
    if (!dataText) return;
    const data = JSON.parse(dataText) as CaptureProgress | CaptureProcessResponse | { detail?: string };
    if (event === 'progress') onProgress?.(data as CaptureProgress);
    if (event === 'complete') completed = data as CaptureProcessResponse;
    if (event === 'error') {
      throw new Error((data as { detail?: string }).detail ?? 'Capture processing could not finish.');
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    let boundary = buffer.match(/\r?\n\r?\n/);
    while (boundary?.index !== undefined) {
      processEvent(buffer.slice(0, boundary.index));
      buffer = buffer.slice(boundary.index + boundary[0].length);
      boundary = buffer.match(/\r?\n\r?\n/);
    }
    if (done) break;
  }

  if (buffer.trim()) processEvent(buffer);
  if (completed) return completed;
  throw new Error('Capture processing ended before a result was returned.');
}

export async function getDraft(session: Session, entryId: string): Promise<Draft> {
  return apiRequest<Draft>(session, `/v1/entries/${entryId}/draft`);
}

export async function reviewDraft(
  session: Session,
  draftId: string,
  decision: DraftReviewDecision
): Promise<ReviewResponse> {
  return apiRequest<ReviewResponse>(session, `/v1/drafts/${draftId}/review`, {
    method: 'POST',
    body: JSON.stringify(decision),
  });
}

export async function uploadFile(
  signedUrl: string,
  fileUri: string,
  contentType: string,
  onProgress?: (progress: number | null) => void,
): Promise<void> {
  const result = await new File(fileUri).upload(signedUrl, {
    headers: { 'Content-Type': contentType },
    httpMethod: 'PUT',
    mimeType: contentType,
    onProgress: ({ bytesSent, totalBytes }) => {
      onProgress?.(totalBytes > 0 ? Math.round((bytesSent / totalBytes) * 100) : null);
    },
    uploadType: UploadType.BINARY_CONTENT,
  });
  if (result.status < 200 || result.status >= 300) {
    const detail = result.body.trim().replace(/\s+/g, ' ').slice(0, 180);
    throw new Error(`Upload failed (${result.status})${detail ? `: ${detail}` : ''}`);
  }
}

export async function listCheckins(session: Session, activityId: string): Promise<Checkin[]> {
  return apiRequest<Checkin[]>(session, `/v1/activities/${activityId}/checkins`);
}

export async function listActivities(session: Session, activityStatus: 'active' | 'completed'): Promise<Activity[]> {
  return apiRequest<Activity[]>(session, `/v1/activities?status=${activityStatus}`);
}

export async function listActivityEvents(session: Session, activityId: string): Promise<ActivityEvent[]> {
  return apiRequest<ActivityEvent[]>(session, `/v1/activities/${activityId}/events`);
}

export async function createCheckin(
  session: Session,
  activityId: string,
  payload: { milestone: string; note?: string; next_small_step?: string; local_date?: string }
): Promise<Checkin> {
  return apiRequest<Checkin>(session, `/v1/activities/${activityId}/checkins`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function completeActivity(session: Session, activityId: string): Promise<ActivityRecap> {
  return apiRequest<ActivityRecap>(session, `/v1/activities/${activityId}/complete`, { method: 'POST' });
}

export async function updateActivityStatus(session: Session, activityId: string, activityStatus: 'active' | 'paused'): Promise<Activity> {
  return apiRequest<Activity>(session, `/v1/activities/${activityId}/status`, {
    method: 'POST',
    body: JSON.stringify({ status: activityStatus }),
  });
}

export async function getActivityRecap(session: Session, activityId: string): Promise<ActivityRecap | null> {
  return apiRequest<ActivityRecap | null>(session, `/v1/activities/${activityId}/recap`);
}

export async function reviewActivityRecap(session: Session, recapId: string, action: 'approve' | 'discard'): Promise<ReviewResponse> {
  return apiRequest<ReviewResponse>(session, `/v1/activity-recaps/${recapId}/review`, {
    method: 'POST',
    body: JSON.stringify({ action }),
  });
}

export async function searchActivities(session: Session, filters: { query?: string; date_from?: string; date_to?: string; media_type?: 'audio' | 'image' }): Promise<ActivitySearchResult[]> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => value && params.set(key, value));
  return apiRequest<ActivitySearchResult[]>(session, `/v1/activities/search?${params.toString()}`);
}

export async function registerDeviceToken(
  session: Session,
  payload: { expo_push_token: string; platform: 'android' | 'ios' }
): Promise<{ status: string }> {
  return apiRequest(session, '/v1/device-tokens', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getNotificationPreferences(session: Session): Promise<NotificationPreferences> {
  return apiRequest<NotificationPreferences>(session, '/v1/notification-preferences');
}

export async function updateNotificationPreferences(
  session: Session,
  payload: Partial<NotificationPreferences>
): Promise<NotificationPreferences> {
  return apiRequest<NotificationPreferences>(session, '/v1/notification-preferences', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function generateDiaryRecap(
  session: Session,
  payload: DiaryRecapRequest,
): Promise<DiaryRecap> {
  return apiRequest<DiaryRecap>(session, '/v1/recaps', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
