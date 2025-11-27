/**
 * TypeScript types for CBT Chat Assistant frontend
 * Updated for Opzione C - Adaptive Conversation System
 */

export enum RiskLevel {
  NONE = "none",
  LOW = "low",
  MEDIUM = "medium",
  HIGH = "high",
}

export enum AlertLevel {
  LOW = "low",
  MEDIUM = "medium",
  HIGH = "high",
  CRITICAL = "critical",
}

export enum DistressLevel {
  NONE = "none",
  MILD = "mild",
  MODERATE = "moderate",
  SEVERE = "severe",
  CRISIS = "crisis",
}

export enum SessionStatus {
  ACTIVE = "active",
  COMPLETED = "completed",
  TERMINATED = "terminated",
  FLAGGED = "flagged",
}

export enum MessageRole {
  USER = "user",
  ASSISTANT = "assistant",
  SYSTEM = "system",
}

export enum ConversationState {
  CONSENT = "consent",
  INTAKE = "intake",
  MENU = "menu",
  THOUGHT_RECORD = "thought_record",
  BEHAVIORAL_ACTIVATION = "behavioral_activation",
  EXPOSURE = "exposure",
  COPING = "coping",
  LEARN = "learn",
  RISK_ESCALATION = "risk_escalation",
  ENDED = "ended",
}

export enum NotificationType {
  RISK_ALERT = "risk_alert",
  DAILY_SUMMARY = "daily_summary",
  WEEKLY_SUMMARY = "weekly_summary",
  PRE_SESSION_REPORT = "pre_session_report",
  PATIENT_MESSAGE = "patient_message",
}

export enum NotificationPriority {
  LOW = "low",
  NORMAL = "normal",
  HIGH = "high",
  CRITICAL = "critical",
}

export interface PreferredTechniques {
  cognitive_restructuring?: boolean;
  behavioral_activation?: boolean;
  exposure?: boolean;
  distress_tolerance?: boolean;
  schema_work?: boolean;
}

export interface ClinicalSensitivities {
  trauma_history?: string | null;
  pacing?: string | null;
  topics_to_avoid?: string[];
}

export interface TherapistLanguage {
  metaphors?: string[];
  coping_statements?: string[];
  preferred_terms?: Record<string, string>;
}

export interface TherapistBrief {
  case_formulation?: string | null;
  presenting_problems?: string[];
  treatment_goals?: string[];
  therapy_stage?: string;
  preferred_techniques?: PreferredTechniques;
  sensitivities?: ClinicalSensitivities;
  therapist_language?: TherapistLanguage;
  contraindications?: string[];
}

export interface PatientWithBrief {
  id: string;
  access_code: string;
  preferred_name?: string | null;
  country_code: string;
  therapist_brief?: TherapistBrief | null;
  created_at: string;
}

export interface PatientDetails {
  patient: PatientWithBrief;
  recent_sessions: Session[];
  recent_risk_events: RiskEvent[];
}

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  created_at: string;
  risk_level?: RiskLevel;
  risk_reasoning?: string;
  risk_triggers?: string[];
  // Opzione C metadata
  distress_level?: DistressLevel;
  is_grounding_exercise?: boolean;
  is_disclaimer?: boolean;
}

export interface Session {
  id: string;
  patient_id: string;
  status: SessionStatus;
  current_state: ConversationState;
  current_skill?: string;
  session_goal?: string;
  ai_summary?: string;
  risk_flagged: boolean;
  risk_level: RiskLevel;
  started_at: string;
  ended_at?: string;
  total_messages: number;
  mood_start?: number;
  mood_end?: number;
}

export interface ChatResponse {
  session_id: string;
  message: Message;
  session_status: SessionStatus;
  current_state: ConversationState;
  risk_detected: boolean;
  risk_level: RiskLevel;
  risk_reasoning?: string;
  risk_triggers?: string[];
  should_end_session: boolean;
  resources?: Record<string, string>;
  // Opzione C additions
  distress_level?: DistressLevel;
  distress_reasoning?: string;
  distress_signals?: string[];
  grounding_offered?: boolean;
  grounding_technique?: string;
  disclaimer_shown?: boolean;
  conversation_mode?: string; // "grounding", "cbt_skill", "clarification", etc.
}

export interface RiskEvent {
  id: string;
  session_id: string;
  patient_id: string;
  risk_level: RiskLevel;
  risk_type?: string;
  detected_keywords: string[];
  created_at: string;
  therapist_reviewed: boolean;
  // Opzione C additions
  alert_level?: AlertLevel;
  notification_sent?: boolean;
  patient_state_at_event?: {
    distress_level: DistressLevel;
    signals_detected: string[];
  };
}

export interface Notification {
  id: string;
  therapist_id: string;
  notification_type: NotificationType;
  priority: NotificationPriority;
  patient_id?: string;
  session_id?: string;
  subject: string;
  message_body: string;
  email_sent: boolean;
  sms_sent: boolean;
  read: boolean;
  created_at: string;
}

export interface Appointment {
  id: string;
  therapist_id: string;
  patient_id: string;
  scheduled_at: string;
  duration_minutes: number;
  appointment_type: string;
  report_generated: boolean;
  report_sent: boolean;
  status: string;
  created_at: string;
}

export interface SkillCompletion {
  id: string;
  skill_type: string;
  skill_name?: string;
  data: Record<string, any>;
  mood_before?: number;
  mood_after?: number;
  completion_status: string;
  completed_at: string;
}

export interface PatientOverview {
  patient_id: string;
  preferred_name?: string;
  access_code: string;
  total_sessions: number;
  flagged_sessions: number;
  last_session_date?: string;
  last_flag_date?: string;
  unreviewed_risk_events: number;
  // Opzione C additions
  therapy_stage?: string; // "early", "middle", "late"
  case_formulation?: string;
  critical_alerts?: number;
  unread_notifications?: number;
  next_appointment_at?: string;
  last_high_risk_date?: string;
}

export interface TherapistDashboard {
  therapist_id: string;
  therapist_name: string;
  patients: PatientOverview[];
  total_unreviewed_flags: number;
  recent_flags: RiskEvent[];
  // Opzione C additions
  total_critical_alerts?: number;
  unread_notifications?: number;
  upcoming_appointments?: Appointment[];
  notifications?: Notification[];
}

export interface SessionTranscript {
  session: Session;
  messages: Message[];
  risk_events: RiskEvent[];
  skill_completions: SkillCompletion[];
}
