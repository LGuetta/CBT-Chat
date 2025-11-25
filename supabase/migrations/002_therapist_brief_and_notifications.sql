-- CBT Chat Assistant - Opzione C: Therapist Brief & Enhanced Notifications
-- Migration 002: Adds adaptive conversation support and notification system

-- ============================================================================
-- EXTEND PATIENTS TABLE - Add Therapist Brief
-- ============================================================================

ALTER TABLE patients
ADD COLUMN IF NOT EXISTS case_formulation TEXT,
ADD COLUMN IF NOT EXISTS presenting_problems TEXT[],
ADD COLUMN IF NOT EXISTS treatment_goals TEXT[],
ADD COLUMN IF NOT EXISTS therapy_stage VARCHAR(20) DEFAULT 'early', -- early, middle, late
ADD COLUMN IF NOT EXISTS preferred_techniques JSONB DEFAULT '{
    "cognitive_restructuring": true,
    "behavioral_activation": true,
    "exposure": false,
    "distress_tolerance": true,
    "schema_work": false
}'::JSONB,
ADD COLUMN IF NOT EXISTS sensitivities JSONB DEFAULT '{}'::JSONB,
-- Example: {"trauma_history": "childhood abuse - avoid direct questions", "pacing": "slow", "topics_to_avoid": ["family", "relationships"]}
ADD COLUMN IF NOT EXISTS therapist_language JSONB DEFAULT '{
    "metaphors": [],
    "coping_statements": [],
    "preferred_terms": {}
}'::JSONB,
-- Example: {"metaphors": ["anxious mind radio", "worry bully"], "coping_statements": ["feelings aren't facts"], "preferred_terms": {"panic": "intense anxiety"}}
ADD COLUMN IF NOT EXISTS contraindications TEXT[] DEFAULT ARRAY[]::TEXT[];
-- Example: ["no trauma narrative work", "avoid prolonged exposure without therapist"]

COMMENT ON COLUMN patients.case_formulation IS 'Therapist case summary and formulation for this patient';
COMMENT ON COLUMN patients.presenting_problems IS 'Why patient is in therapy (e.g., GAD, panic, social anxiety)';
COMMENT ON COLUMN patients.treatment_goals IS 'Current therapy goals (e.g., reduce avoidance, build distress tolerance)';
COMMENT ON COLUMN patients.therapy_stage IS 'Stage of therapy: early (building rapport), middle (active work), late (consolidation)';
COMMENT ON COLUMN patients.preferred_techniques IS 'CBT techniques preferred by therapist for this patient';
COMMENT ON COLUMN patients.sensitivities IS 'Important clinical sensitivities (trauma, pacing, topics to avoid)';
COMMENT ON COLUMN patients.therapist_language IS 'Metaphors, coping statements, and terms therapist uses with this patient';
COMMENT ON COLUMN patients.contraindications IS 'Techniques or approaches to avoid with this patient';

-- ============================================================================
-- EXTEND THERAPISTS TABLE - Add Notification Preferences
-- ============================================================================

ALTER TABLE therapists
ADD COLUMN IF NOT EXISTS phone VARCHAR(20),
ADD COLUMN IF NOT EXISTS notification_preferences JSONB DEFAULT '{
    "email_enabled": true,
    "sms_enabled": false,
    "high_risk_immediate": true,
    "daily_summary": false,
    "weekly_summary": true
}'::JSONB,
ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) DEFAULT 'UTC';

COMMENT ON COLUMN therapists.phone IS 'Phone number for SMS alerts (optional)';
COMMENT ON COLUMN therapists.notification_preferences IS 'How therapist wants to be notified';
COMMENT ON COLUMN therapists.timezone IS 'Therapist timezone for scheduling reports';

-- ============================================================================
-- NEW TABLE: APPOINTMENTS (for pre-session report scheduling)
-- ============================================================================

CREATE TABLE appointments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    therapist_id UUID NOT NULL REFERENCES therapists(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,

    -- Appointment details
    scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
    duration_minutes INTEGER DEFAULT 50,
    appointment_type VARCHAR(50) DEFAULT 'regular', -- regular, intake, follow_up, check_in

    -- Pre-appointment report
    report_generated BOOLEAN DEFAULT FALSE,
    report_generated_at TIMESTAMP WITH TIME ZONE,
    report_sent BOOLEAN DEFAULT FALSE,
    report_sent_at TIMESTAMP WITH TIME ZONE,
    report_data JSONB, -- Stores the generated report

    -- Status
    status VARCHAR(50) DEFAULT 'scheduled', -- scheduled, completed, cancelled, no_show
    notes TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_appointments_therapist ON appointments(therapist_id);
CREATE INDEX idx_appointments_patient ON appointments(patient_id);
CREATE INDEX idx_appointments_scheduled_at ON appointments(scheduled_at);
CREATE INDEX idx_appointments_report_sent ON appointments(report_sent);

COMMENT ON TABLE appointments IS 'Scheduled therapy appointments for pre-session report generation';

-- ============================================================================
-- NEW TABLE: NOTIFICATIONS (log all notifications sent)
-- ============================================================================

CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Recipient
    therapist_id UUID NOT NULL REFERENCES therapists(id) ON DELETE CASCADE,

    -- Notification details
    notification_type VARCHAR(50) NOT NULL, -- risk_alert, daily_summary, weekly_summary, pre_session_report
    priority VARCHAR(20) DEFAULT 'normal', -- low, normal, high, critical

    -- Related entities
    patient_id UUID REFERENCES patients(id) ON DELETE SET NULL,
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    risk_event_id UUID REFERENCES risk_events(id) ON DELETE SET NULL,
    appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,

    -- Message content
    subject TEXT NOT NULL,
    message_body TEXT NOT NULL,

    -- Delivery channels
    email_sent BOOLEAN DEFAULT FALSE,
    email_sent_at TIMESTAMP WITH TIME ZONE,
    email_error TEXT,

    sms_sent BOOLEAN DEFAULT FALSE,
    sms_sent_at TIMESTAMP WITH TIME ZONE,
    sms_error TEXT,

    -- Read status
    read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMP WITH TIME ZONE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_notifications_therapist ON notifications(therapist_id);
CREATE INDEX idx_notifications_type ON notifications(notification_type);
CREATE INDEX idx_notifications_priority ON notifications(priority);
CREATE INDEX idx_notifications_read ON notifications(read);
CREATE INDEX idx_notifications_created_at ON notifications(created_at DESC);

COMMENT ON TABLE notifications IS 'All notifications sent to therapists (email, SMS, in-app)';

-- ============================================================================
-- NEW TABLE: DISCLAIMER_LOGS (track boundary reminders)
-- ============================================================================

CREATE TABLE disclaimer_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,

    -- Disclaimer details
    disclaimer_type VARCHAR(50) NOT NULL, -- initial_consent, periodic_reminder, crisis_boundary, therapy_referral
    content TEXT NOT NULL,

    -- Context
    triggered_by VARCHAR(100), -- session_start, message_count_threshold, high_dependency_detected, crisis_language
    message_count_at_trigger INTEGER,

    -- Patient response
    patient_acknowledged BOOLEAN DEFAULT FALSE,
    patient_response TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_disclaimer_logs_session ON disclaimer_logs(session_id);
CREATE INDEX idx_disclaimer_logs_patient ON disclaimer_logs(patient_id);
CREATE INDEX idx_disclaimer_logs_type ON disclaimer_logs(disclaimer_type);
CREATE INDEX idx_disclaimer_logs_created_at ON disclaimer_logs(created_at DESC);

COMMENT ON TABLE disclaimer_logs IS 'Tracks when boundary/disclaimer reminders are shown to patients';

-- ============================================================================
-- EXTEND SESSIONS TABLE - Add conversational state
-- ============================================================================

ALTER TABLE sessions
ADD COLUMN IF NOT EXISTS distress_level VARCHAR(20) DEFAULT 'none', -- none, mild, moderate, severe, crisis
ADD COLUMN IF NOT EXISTS grounding_performed BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS grounding_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS conversation_mode VARCHAR(50) DEFAULT 'adaptive', -- adaptive, structured (old state machine)
ADD COLUMN IF NOT EXISTS disclaimer_shown_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_disclaimer_at TIMESTAMP WITH TIME ZONE;

COMMENT ON COLUMN sessions.distress_level IS 'Current assessed distress level of patient in this session';
COMMENT ON COLUMN sessions.grounding_performed IS 'Whether grounding exercises were used in this session';
COMMENT ON COLUMN sessions.grounding_count IS 'Number of times grounding was triggered';
COMMENT ON COLUMN sessions.conversation_mode IS 'Adaptive (Opzione C) vs Structured (old state machine)';

-- ============================================================================
-- EXTEND RISK_EVENTS TABLE - Add critical level and enhanced tracking
-- ============================================================================

ALTER TABLE risk_events
ADD COLUMN IF NOT EXISTS alert_level VARCHAR(20) DEFAULT 'medium', -- low, medium, high, critical
ADD COLUMN IF NOT EXISTS notification_sent BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS notification_sent_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS notification_id UUID REFERENCES notifications(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS patient_state_at_event JSONB; -- Snapshot of patient state (distress_level, recent_history, etc.)

-- Update existing risk_events to have alert_level based on risk_level
UPDATE risk_events SET alert_level =
    CASE
        WHEN risk_level = 'high' THEN 'critical'
        WHEN risk_level = 'medium' THEN 'high'
        ELSE 'medium'
    END
WHERE alert_level = 'medium'; -- Only update defaults

CREATE INDEX idx_risk_events_alert_level ON risk_events(alert_level);
CREATE INDEX idx_risk_events_notification_sent ON risk_events(notification_sent);

COMMENT ON COLUMN risk_events.alert_level IS 'Urgency level for therapist notification: low (keyword only), medium (LLM concern), high (clear risk), critical (active crisis)';

-- ============================================================================
-- ENHANCED TRIGGERS
-- ============================================================================

-- Trigger: Auto-create notification when high/critical risk event occurs
CREATE OR REPLACE FUNCTION create_risk_notification()
RETURNS TRIGGER AS $$
DECLARE
    v_therapist_id UUID;
    v_patient_name VARCHAR(100);
    v_notification_id UUID;
    v_priority VARCHAR(20);
BEGIN
    -- Only create notification for high and critical alerts
    IF NEW.alert_level IN ('high', 'critical') THEN
        -- Get therapist ID and patient name
        SELECT tp.therapist_id, p.preferred_name
        INTO v_therapist_id, v_patient_name
        FROM therapist_patients tp
        JOIN patients p ON p.id = tp.patient_id
        WHERE tp.patient_id = NEW.patient_id
          AND tp.is_active = TRUE
        LIMIT 1;

        IF v_therapist_id IS NOT NULL THEN
            -- Set priority
            v_priority := CASE
                WHEN NEW.alert_level = 'critical' THEN 'critical'
                ELSE 'high'
            END;

            -- Insert notification
            INSERT INTO notifications (
                therapist_id,
                notification_type,
                priority,
                patient_id,
                session_id,
                risk_event_id,
                subject,
                message_body
            ) VALUES (
                v_therapist_id,
                'risk_alert',
                v_priority,
                NEW.patient_id,
                NEW.session_id,
                NEW.id,
                '🚨 ' || UPPER(NEW.alert_level) || ' Risk Alert - ' || v_patient_name,
                'A ' || NEW.alert_level || ' risk event was detected for ' || v_patient_name || E'.\n\n' ||
                'Risk Type: ' || COALESCE(NEW.risk_type, 'Unknown') || E'\n' ||
                'Message: ' || LEFT(NEW.full_message_content, 200) || E'\n\n' ||
                'Please review this event in your dashboard immediately.'
            )
            RETURNING id INTO v_notification_id;

            -- Update risk event with notification ID
            UPDATE risk_events
            SET notification_id = v_notification_id,
                therapist_notified = TRUE,
                therapist_notified_at = NOW()
            WHERE id = NEW.id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER create_risk_notification_trigger
AFTER INSERT ON risk_events
FOR EACH ROW
EXECUTE FUNCTION create_risk_notification();

-- Trigger: Auto-generate pre-session report 24h before appointment
CREATE OR REPLACE FUNCTION schedule_pre_session_report()
RETURNS TRIGGER AS $$
BEGIN
    -- This will be handled by a background job, but we mark it for generation
    IF NEW.scheduled_at IS NOT NULL AND NEW.status = 'scheduled' THEN
        -- Background job will check for appointments 24h ahead and generate reports
        -- This trigger just validates the data
        IF NEW.therapist_id IS NULL OR NEW.patient_id IS NULL THEN
            RAISE EXCEPTION 'Appointment must have therapist_id and patient_id';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER validate_appointment_trigger
BEFORE INSERT OR UPDATE ON appointments
FOR EACH ROW
EXECUTE FUNCTION schedule_pre_session_report();

-- Update trigger for appointments updated_at
CREATE TRIGGER update_appointments_updated_at
BEFORE UPDATE ON appointments
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- ENHANCED VIEWS
-- ============================================================================

-- Drop old view and recreate with new fields
DROP VIEW IF EXISTS v_therapist_dashboard;

CREATE VIEW v_therapist_dashboard AS
SELECT
    tp.therapist_id,
    p.id AS patient_id,
    p.preferred_name,
    p.access_code,
    p.therapy_stage,
    p.case_formulation,

    -- Session stats
    COUNT(DISTINCT s.id) AS total_sessions,
    COUNT(DISTINCT CASE WHEN s.risk_flagged THEN s.id END) AS flagged_sessions,
    MAX(s.started_at) AS last_session_date,
    MAX(CASE WHEN s.risk_flagged THEN s.started_at END) AS last_flag_date,

    -- Risk stats
    COUNT(DISTINCT re.id) FILTER (WHERE re.therapist_reviewed = FALSE) AS unreviewed_risk_events,
    COUNT(DISTINCT re.id) FILTER (WHERE re.alert_level = 'critical' AND re.therapist_reviewed = FALSE) AS critical_alerts,
    MAX(CASE WHEN re.alert_level IN ('high', 'critical') THEN re.created_at END) AS last_high_risk_date,

    -- Notifications
    COUNT(DISTINCT n.id) FILTER (WHERE n.read = FALSE) AS unread_notifications,

    -- Upcoming appointments
    (SELECT MIN(scheduled_at)
     FROM appointments
     WHERE patient_id = p.id
       AND therapist_id = tp.therapist_id
       AND scheduled_at > NOW()
       AND status = 'scheduled'
    ) AS next_appointment_at

FROM therapist_patients tp
JOIN patients p ON tp.patient_id = p.id
LEFT JOIN sessions s ON s.patient_id = p.id
LEFT JOIN risk_events re ON re.patient_id = p.id
LEFT JOIN notifications n ON n.therapist_id = tp.therapist_id AND n.patient_id = p.id
WHERE tp.is_active = TRUE
GROUP BY tp.therapist_id, p.id, p.preferred_name, p.access_code, p.therapy_stage, p.case_formulation;

COMMENT ON VIEW v_therapist_dashboard IS 'Enhanced therapist dashboard with notifications and appointments';

-- ============================================================================
-- SEED DATA UPDATES
-- ============================================================================

-- Update existing test therapist with notification preferences
UPDATE therapists
SET
    phone = '+1-555-0123',
    notification_preferences = '{
        "email_enabled": true,
        "sms_enabled": true,
        "high_risk_immediate": true,
        "daily_summary": false,
        "weekly_summary": true
    }'::JSONB,
    timezone = 'America/New_York'
WHERE email = 'dr.smith@example.com';

-- Add sample therapist brief to test patient
UPDATE patients
SET
    case_formulation = 'Patient with Generalized Anxiety Disorder and social anxiety. Frequent worry about work performance and social interactions. History of panic attacks in crowded settings.',
    presenting_problems = ARRAY['generalized_anxiety', 'social_anxiety', 'panic_attacks'],
    treatment_goals = ARRAY['reduce safety behaviors', 'practice exposure to social situations', 'challenge catastrophic thinking'],
    therapy_stage = 'middle',
    preferred_techniques = '{
        "cognitive_restructuring": true,
        "behavioral_activation": true,
        "exposure": true,
        "distress_tolerance": true,
        "schema_work": false
    }'::JSONB,
    sensitivities = '{
        "trauma_history": "None reported",
        "pacing": "moderate",
        "topics_to_avoid": []
    }'::JSONB,
    therapist_language = '{
        "metaphors": ["worry radio", "anxiety alarm system"],
        "coping_statements": ["This is uncomfortable, not dangerous", "Feelings aren''t facts"],
        "preferred_terms": {}
    }'::JSONB,
    contraindications = ARRAY['avoid trauma-focused work without therapist present']
WHERE access_code = 'PATIENT001';

-- Add sample appointment for testing pre-session reports
INSERT INTO appointments (therapist_id, patient_id, scheduled_at, appointment_type)
SELECT
    t.id,
    p.id,
    NOW() + INTERVAL '3 days',
    'regular'
FROM therapists t
CROSS JOIN patients p
WHERE t.email = 'dr.smith@example.com'
  AND p.access_code = 'PATIENT001';

-- ============================================================================
-- UTILITY FUNCTIONS
-- ============================================================================

-- Function to check if pre-session report should be generated
CREATE OR REPLACE FUNCTION get_appointments_needing_reports()
RETURNS TABLE (
    appointment_id UUID,
    therapist_id UUID,
    patient_id UUID,
    scheduled_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.id,
        a.therapist_id,
        a.patient_id,
        a.scheduled_at
    FROM appointments a
    WHERE a.status = 'scheduled'
      AND a.report_generated = FALSE
      AND a.scheduled_at > NOW()
      AND a.scheduled_at <= NOW() + INTERVAL '24 hours';
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_appointments_needing_reports IS 'Returns appointments within 24h that need pre-session reports generated';

-- Function to mark appointment report as sent
CREATE OR REPLACE FUNCTION mark_appointment_report_sent(
    p_appointment_id UUID,
    p_report_data JSONB
)
RETURNS VOID AS $$
BEGIN
    UPDATE appointments
    SET
        report_generated = TRUE,
        report_generated_at = NOW(),
        report_sent = TRUE,
        report_sent_at = NOW(),
        report_data = p_report_data
    WHERE id = p_appointment_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION mark_appointment_report_sent IS 'Marks appointment report as generated and sent';
