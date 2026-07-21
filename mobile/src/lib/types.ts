export type Provenance = 'user_written' | 'transcribed' | 'ai_generated';
export type DayFeeling = 'loved' | 'low' | 'mixed' | 'quiet';

export interface Activity {
  id: string;
  title: string;
  purpose: string | null;
  start_date: string;
  end_date: string | null;
  cadence_type: string;
  cadence_config: Record<string, unknown>;
  reminder_time: string | null;
  status: string;
  streak: number;
  current_streak: number;
  longest_streak: number;
  completed_at: string | null;
  recap_status: string | null;
  completed_for_date: boolean;
  due_for_date: boolean;
}

export interface DiaryEntry {
  id: string;
  title: string;
  body: string;
  mood: string | null;
  day_feeling: DayFeeling | null;
  local_date: string;
  status: string;
  source_badge: 'user_written' | 'ai_generated';
  audio_count: number;
  image_count: number;
  addenda_count: number;
  preview_images: DiaryMediaPreview[];
  preview_audio: DiaryMediaPreview | null;
}

export interface DiaryMediaPreview {
  id: string;
  media_type: 'audio' | 'image';
  signed_url: string;
}

export interface DiaryMedia {
  id: string;
  media_type: 'audio' | 'image';
  signed_url: string;
  transcript: string | null;
  ai_description: Record<string, unknown> | null;
}

export interface DiaryAddendum {
  id: string;
  entry_id: string;
  body: string | null;
  created_at: string;
  media: DiaryMedia[];
}

export interface SavedRecap {
  id: string | null;
  recap_type: 'weekly' | 'monthly' | 'custom';
  period_start_date: string;
  period_end_date: string;
  title: string | null;
  summary: string | null;
  source_count: number;
  saved: boolean;
}

export interface ExploreDiscoveryResponse {
  on_this_day: DiaryEntry[];
  saved_recaps: SavedRecap[];
  saved_entries: DiaryEntry[];
  recent_photos: ExploreMediaItem[];
  recent_audio: ExploreMediaItem[];
}

export interface ExploreMediaItem {
  entry_id: string;
  media_item_id: string;
  title: string;
  local_date: string;
  signed_url: string;
}

/** @deprecated Discovery lives in Explore; retained only for old type imports. */
export type MemoriesResponse = ExploreDiscoveryResponse;

export interface DiaryExploreResponse {
  selected_date: string;
  is_today: boolean;
  entry: DiaryEntry | null;
  recap_available: boolean;
}

export interface DiaryAskResponse {
  answer: string;
  source_count: number;
  date_from: string;
  date_to: string;
  sources: { entry_id: string; local_date: string; title: string; excerpt: string | null }[];
  reflection_prompt: string | null;
}

export type DiaryRecapType = 'weekly' | 'monthly' | 'custom';

export interface DiaryRecapRequest {
  recap_type: DiaryRecapType;
  period_start_date: string;
  period_end_date: string;
  run_id?: string;
}

export interface DiaryRecap {
  id: string | null;
  recap_type: DiaryRecapType;
  period_start_date: string;
  period_end_date: string;
  title: string | null;
  summary: string | null;
  highlights: {
    entry_id: string;
    local_date: string;
    title: string;
    excerpt: string | null;
  }[];
  source_count: number;
  insufficient_material: boolean;
  saved: boolean;
  reflection_prompt: string | null;
}

export interface TodayResponse {
  local_date: string;
  entry: DiaryEntry | null;
  activities: Activity[];
}

export interface ExploreFocus {
  activity: Activity;
  reason: string;
  rule: 'smallest_next_step' | 'nearing_end_date' | 'recent_reset' | 'recent_activity';
}

export interface ExploreContinuity {
  activity_id: string;
  activity_title: string;
  checkin_id: string;
  local_date: string;
  next_small_step: string;
}

export interface AgentInsight {
  id: string;
  insight_type: 'pattern' | 'continuity' | 'comeback';
  body: string;
  source_count: number;
  date_from: string;
  date_to: string;
}

export interface WeeklyProof {
  recap_id: string;
  entry_count: number;
  checkin_count: number;
  return_count: number;
}

export interface ExploreBriefing {
  selected_date: string;
  is_today: boolean;
  entry: DiaryEntry | null;
  activities: Activity[];
  agent_focus: ExploreFocus | null;
  continuity: ExploreContinuity | null;
  insight: AgentInsight | null;
  weekly_proof: WeeklyProof | null;
}

export interface ExploreSourceCard {
  source_type: 'diary_entry' | 'activity_checkin';
  source_id: string;
  activity_id: string | null;
  local_date: string;
  title: string;
  excerpt: string | null;
}

export interface ExploreAskResponse {
  answer: string;
  source_count: number;
  date_from: string;
  date_to: string;
  sources: ExploreSourceCard[];
}

export interface Profile {
  onboarding_completed_at: string | null;
  created_at: string | null;
}

export interface Draft {
  id: string;
  entry_id: string;
  run_id: string;
  payload: {
    title: string;
    body: string;
    mood: string | null;
    tags: string[];
    source_labels: Provenance[];
    reflection_prompt: string | null;
    proposed_activity_update?: {
      activity_id: string | null;
      confidence: number;
      milestone: string;
      reason: string;
    };
  };
  status: string;
  version: number;
}

export interface DraftReviewDecision {
  action: 'approve' | 'edit' | 'discard';
  entry?: { title: string; body: string; mood?: string | null; day_feeling?: DayFeeling | null };
  activity_update?: {
    action: 'accept' | 'change' | 'decline';
    activity_id?: string;
    milestone?: string;
    note?: string;
  };
}

export interface ReviewResponse {
  status: string;
  entry_id: string;
}

export interface Capture {
  id: string;
  status: string;
  local_date: string;
  entry_id: string | null;
}

export interface CaptureProcessResponse {
  id: string;
  status: string;
  local_date: string;
  entry_id: string;
}

export interface Checkin {
  id: string;
  activity_id: string;
  entry_id: string | null;
  local_date: string;
  milestone: string;
  note: string | null;
  next_small_step: string | null;
  source_badge: 'user_written' | 'ai_generated';
  audio_count: number;
  image_count: number;
  status: string;
}

export interface ActivityEvent {
  id: string;
  activity_id: string;
  local_date: string;
  event_type: 'checkin' | 'streak_reset' | 'paused' | 'resumed' | 'completed';
  checkin_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ActivityRecap {
  id: string;
  activity_id: string;
  payload: { title: string; summary: string; highlights: string[]; source_checkin_count: number };
  status: 'ready_for_review' | 'approved' | 'discarded' | 'failed';
  created_at: string;
}

export interface ActivitySearchResult {
  activity: Activity;
  matching_checkins: Checkin[];
}

export interface NotificationPreferences {
  user_id: string;
  timezone: string;
  diary_enabled: boolean;
  diary_reminder_time: string | null;
  activity_enabled: boolean;
  activity_reminder_time: string | null;
  weekly_recap_enabled: boolean;
  weekly_recap_day: number | null;
  weekly_recap_time: string | null;
}
