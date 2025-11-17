-- CBT Chat Assistant - Initial Database Schema
-- Multi-tenant architecture: Therapists → Patients → Sessions

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- THERAPISTS TABLE
-- ============================================================================
CREATE TABLE therapists (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    license_number VARCHAR(100),
    organization VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_therapists_email ON therapists(email);
CREATE INDEX idx_therapists_active ON therapists(is_active);

-- ============================================================================
-- PATIENTS TABLE
-- ============================================================================
CREATE TABLE patients (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    access_code VARCHAR(50) UNIQUE NOT NULL, -- Simple access code for MVP (no password)
    preferred_name VARCHAR(100),
    age_range VARCHAR(20), -- "18-25", "26-35", etc. for demographics
    country_code VARCHAR(2) DEFAULT 'US', -- For crisis resources
    onboarding_completed BOOLEAN DEFAULT FALSE,
    communication_style VARCHAR(50), -- "casual", "formal", "direct"
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,

    -- Session preferences
    preferred_language VARCHAR(10) DEFAULT 'en'
);

CREATE INDEX idx_patients_access_code ON patients(access_code);
CREATE INDEX idx_patients_active ON patients(is_active);

-- ============================================================================
-- THERAPIST-PATIENT RELATIONSHIPS
-- ============================================================================
CREATE TABLE therapist_patients (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    therapist_id UUID NOT NULL REFERENCES therapists(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    notes TEXT, -- Private therapist notes about the patient

    UNIQUE(therapist_id, patient_id)
);

CREATE INDEX idx_therapist_patients_therapist ON therapist_patients(therapist_id);
CREATE INDEX idx_therapist_patients_patient ON therapist_patients(patient_id);
CREATE INDEX idx_therapist_patients_active ON therapist_patients(is_active);

-- ============================================================================
-- CONVERSATION SESSIONS
-- ============================================================================
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,

    -- Session metadata
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'active', -- active, completed, terminated, flagged

    -- State machine tracking
    current_state VARCHAR(100) DEFAULT 'menu', -- consent, intake, menu, thought_record, ba, exposure, coping
    current_skill VARCHAR(50), -- thought_record, behavioral_activation, exposure, coping
    current_step VARCHAR(100), -- specific step within skill

    -- Session goals
    session_goal TEXT,
    session_focus VARCHAR(255), -- What user wanted to work on

    -- Risk flags
    risk_level VARCHAR(20) DEFAULT 'none', -- none, low, medium, high
    risk_flagged BOOLEAN DEFAULT FALSE,
    risk_flagged_at TIMESTAMP WITH TIME ZONE,
    therapist_notified BOOLEAN DEFAULT FALSE,

    -- Session summary
    summary_generated BOOLEAN DEFAULT FALSE,
    summary TEXT,
    skills_practiced JSONB DEFAULT '[]'::JSONB, -- Array of skill names
    mood_start INTEGER, -- 0-10 scale
    mood_end INTEGER, -- 0-10 scale

    -- Metadata
    total_messages INTEGER DEFAULT 0,
    total_duration_seconds INTEGER,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_sessions_patient ON sessions(patient_id);
CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_sessions_risk_flagged ON sessions(risk_flagged);
CREATE INDEX idx_sessions_started_at ON sessions(started_at DESC);

-- ============================================================================
-- MESSAGES
-- ============================================================================
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,

    -- Message content
    role VARCHAR(20) NOT NULL, -- user, assistant, system
    content TEXT NOT NULL,

    -- Risk detection
    risk_scan_performed BOOLEAN DEFAULT FALSE,
    risk_level VARCHAR(20), -- none, low, medium, high
    risk_keywords TEXT[], -- Detected risk keywords

    -- Metadata
    tokens_used INTEGER,
    model_used VARCHAR(100), -- deepseek-chat, claude-3-5-haiku, etc.
    processing_time_ms INTEGER,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_messages_session ON messages(session_id);
CREATE INDEX idx_messages_created_at ON messages(created_at DESC);
CREATE INDEX idx_messages_role ON messages(role);
CREATE INDEX idx_messages_risk_level ON messages(risk_level);

-- ============================================================================
-- RISK EVENTS (Flagged high-risk interactions)
-- ============================================================================
CREATE TABLE risk_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    message_id UUID REFERENCES messages(id) ON DELETE SET NULL,

    -- Risk details
    risk_level VARCHAR(20) NOT NULL, -- medium, high
    risk_type VARCHAR(100), -- suicidal_ideation, self_harm, psychosis, etc.
    detected_keywords TEXT[],
    full_message_content TEXT NOT NULL,

    -- AI analysis
    ai_reasoning TEXT,
    confidence_score FLOAT, -- 0.0 - 1.0

    -- Actions taken
    escalation_flow_triggered BOOLEAN DEFAULT TRUE,
    session_terminated BOOLEAN DEFAULT FALSE,
    resources_provided BOOLEAN DEFAULT FALSE,

    -- Therapist review
    therapist_notified BOOLEAN DEFAULT FALSE,
    therapist_notified_at TIMESTAMP WITH TIME ZONE,
    therapist_reviewed BOOLEAN DEFAULT FALSE,
    therapist_reviewed_at TIMESTAMP WITH TIME ZONE,
    therapist_notes TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_risk_events_session ON risk_events(session_id);
CREATE INDEX idx_risk_events_patient ON risk_events(patient_id);
CREATE INDEX idx_risk_events_risk_level ON risk_events(risk_level);
CREATE INDEX idx_risk_events_therapist_reviewed ON risk_events(therapist_reviewed);
CREATE INDEX idx_risk_events_created_at ON risk_events(created_at DESC);

-- ============================================================================
-- SKILL COMPLETIONS (Completed CBT exercises)
-- ============================================================================
CREATE TABLE skill_completions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,

    -- Skill details
    skill_type VARCHAR(50) NOT NULL, -- thought_record, behavioral_activation, exposure, coping
    skill_name VARCHAR(255), -- Specific name/description

    -- Completion data (flexible JSON for different skill types)
    data JSONB NOT NULL, -- Stores all skill-specific data

    -- Outcomes
    mood_before INTEGER, -- 0-10
    mood_after INTEGER, -- 0-10
    completion_status VARCHAR(50) DEFAULT 'completed', -- completed, partial, abandoned

    -- Insights
    ai_summary TEXT, -- Brief AI-generated summary of the exercise
    key_insight TEXT, -- Main takeaway

    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    duration_seconds INTEGER
);

CREATE INDEX idx_skill_completions_session ON skill_completions(session_id);
CREATE INDEX idx_skill_completions_patient ON skill_completions(patient_id);
CREATE INDEX idx_skill_completions_skill_type ON skill_completions(skill_type);
CREATE INDEX idx_skill_completions_completed_at ON skill_completions(completed_at DESC);

-- ============================================================================
-- MOOD RATINGS (Quick mood check-ins)
-- ============================================================================
CREATE TABLE mood_ratings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,

    -- Mood data
    mood_score INTEGER NOT NULL CHECK (mood_score >= 0 AND mood_score <= 10),
    mood_label VARCHAR(50), -- anxious, depressed, calm, happy, etc.
    context VARCHAR(50), -- session_start, session_end, check_in, post_skill
    notes TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_mood_ratings_patient ON mood_ratings(patient_id);
CREATE INDEX idx_mood_ratings_created_at ON mood_ratings(created_at DESC);

-- ============================================================================
-- SESSION SUMMARIES (Weekly/periodic summaries)
-- ============================================================================
CREATE TABLE session_summaries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    therapist_id UUID REFERENCES therapists(id) ON DELETE SET NULL,

    -- Time range
    period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    period_end TIMESTAMP WITH TIME ZONE NOT NULL,
    period_type VARCHAR(20) DEFAULT 'weekly', -- daily, weekly, monthly

    -- Summary data
    total_sessions INTEGER DEFAULT 0,
    total_duration_minutes INTEGER DEFAULT 0,

    -- Skills usage
    skills_practiced JSONB DEFAULT '[]'::JSONB, -- [{ skill: "thought_record", count: 5 }]
    completion_rate FLOAT, -- Percentage of completed vs abandoned skills

    -- Mood trends
    avg_mood_start FLOAT,
    avg_mood_end FLOAT,
    mood_improvement_avg FLOAT,
    mood_trend VARCHAR(50), -- improving, stable, declining

    -- Top triggers/themes
    top_triggers TEXT[], -- Common themes from thought records
    common_emotions TEXT[], -- Most frequent emotions

    -- Risk indicators
    risk_events_count INTEGER DEFAULT 0,
    risk_events_severity VARCHAR(20), -- none, low, medium, high

    -- AI-generated narrative summary
    ai_summary TEXT,

    -- Therapist access
    viewed_by_therapist BOOLEAN DEFAULT FALSE,
    viewed_at TIMESTAMP WITH TIME ZONE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_session_summaries_patient ON session_summaries(patient_id);
CREATE INDEX idx_session_summaries_period_end ON session_summaries(period_end DESC);
CREATE INDEX idx_session_summaries_viewed ON session_summaries(viewed_by_therapist);

-- ============================================================================
-- AUDIT LOG (Track all important actions)
-- ============================================================================
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Actor
    actor_type VARCHAR(50) NOT NULL, -- therapist, patient, system
    actor_id UUID,

    -- Action
    action VARCHAR(100) NOT NULL, -- login, view_transcript, export_data, flag_reviewed, etc.
    resource_type VARCHAR(50), -- session, patient, risk_event
    resource_id UUID,

    -- Details
    details JSONB,
    ip_address INET,
    user_agent TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_actor ON audit_logs(actor_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);

-- ============================================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_therapists_updated_at BEFORE UPDATE ON therapists
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_patients_updated_at BEFORE UPDATE ON patients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sessions_updated_at BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Auto-increment message count on sessions
CREATE OR REPLACE FUNCTION increment_session_message_count()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE sessions
    SET total_messages = total_messages + 1,
        updated_at = NOW()
    WHERE id = NEW.session_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER increment_message_count AFTER INSERT ON messages
    FOR EACH ROW EXECUTE FUNCTION increment_session_message_count();

-- Auto-flag session when risk event is created
CREATE OR REPLACE FUNCTION flag_session_on_risk_event()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE sessions
    SET risk_flagged = TRUE,
        risk_flagged_at = NOW(),
        risk_level = NEW.risk_level,
        status = CASE
            WHEN NEW.risk_level = 'high' THEN 'flagged'
            ELSE status
        END
    WHERE id = NEW.session_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER flag_session_on_risk AFTER INSERT ON risk_events
    FOR EACH ROW EXECUTE FUNCTION flag_session_on_risk_event();

-- ============================================================================
-- SEED DATA (for MVP testing)
-- ============================================================================

-- Insert test therapist
INSERT INTO therapists (email, name, license_number, organization) VALUES
    ('dr.smith@example.com', 'Dr. Sarah Smith', 'PSY-12345', 'Example Clinic');

-- Insert test patients with simple access codes
INSERT INTO patients (access_code, preferred_name, country_code, communication_style) VALUES
    ('PATIENT001', 'Alex', 'US', 'casual'),
    ('PATIENT002', 'Jordan', 'UK', 'formal'),
    ('PATIENT003', 'Marco', 'IT', 'casual');

-- Link patients to therapist
INSERT INTO therapist_patients (therapist_id, patient_id, notes)
SELECT
    t.id,
    p.id,
    'Test patient for MVP'
FROM therapists t
CROSS JOIN patients p
WHERE t.email = 'dr.smith@example.com';

-- ============================================================================
-- VIEWS (for easier querying)
-- ============================================================================

-- View for therapist dashboard - all patients with recent activity
CREATE VIEW v_therapist_dashboard AS
SELECT
    tp.therapist_id,
    p.id AS patient_id,
    p.preferred_name,
    p.access_code,
    COUNT(DISTINCT s.id) AS total_sessions,
    COUNT(DISTINCT CASE WHEN s.risk_flagged THEN s.id END) AS flagged_sessions,
    MAX(s.started_at) AS last_session_date,
    MAX(CASE WHEN s.risk_flagged THEN s.started_at END) AS last_flag_date,
    COUNT(DISTINCT re.id) AS unreviewed_risk_events
FROM therapist_patients tp
JOIN patients p ON tp.patient_id = p.id
LEFT JOIN sessions s ON s.patient_id = p.id
LEFT JOIN risk_events re ON re.patient_id = p.id AND re.therapist_reviewed = FALSE
WHERE tp.is_active = TRUE
GROUP BY tp.therapist_id, p.id, p.preferred_name, p.access_code;

-- View for recent flagged sessions
CREATE VIEW v_recent_flags AS
SELECT
    re.id AS risk_event_id,
    re.patient_id,
    p.preferred_name AS patient_name,
    re.session_id,
    re.risk_level,
    re.risk_type,
    re.detected_keywords,
    re.created_at AS flagged_at,
    re.therapist_reviewed,
    s.started_at AS session_started_at,
    tp.therapist_id
FROM risk_events re
JOIN patients p ON re.patient_id = p.id
JOIN sessions s ON re.session_id = s.id
JOIN therapist_patients tp ON tp.patient_id = p.id
WHERE tp.is_active = TRUE
ORDER BY re.created_at DESC;

COMMENT ON TABLE therapists IS 'Licensed therapists who monitor patients';
COMMENT ON TABLE patients IS 'Adult patients using the CBT chat assistant';
COMMENT ON TABLE sessions IS 'Individual chat sessions with state tracking';
COMMENT ON TABLE messages IS 'All messages exchanged in sessions';
COMMENT ON TABLE risk_events IS 'Flagged high-risk interactions requiring review';
COMMENT ON TABLE skill_completions IS 'Completed CBT exercises with outcomes';
COMMENT ON TABLE session_summaries IS 'Periodic summaries of patient activity';
