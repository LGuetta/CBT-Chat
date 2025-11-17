/**
 * TypeScript types for CBT Chat Assistant frontend
 */

export enum RiskLevel {
  NONE = "none",
  LOW = "low",
  MEDIUM = "medium",
  HIGH = "high",
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

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  created_at: string;
  risk_level?: RiskLevel;
}

export interface Session {
  id: string;
  patient_id: string;
  status: SessionStatus;
  current_state: ConversationState;
  current_skill?: string;
  session_goal?: string;
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
  should_end_session: boolean;
  resources?: Record<string, string>;
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
}

export interface TherapistDashboard {
  therapist_id: string;
  therapist_name: string;
  patients: PatientOverview[];
  total_unreviewed_flags: number;
  recent_flags: RiskEvent[];
}

export interface SessionTranscript {
  session: Session;
  messages: Message[];
  risk_events: RiskEvent[];
  skill_completions: SkillCompletion[];
}
