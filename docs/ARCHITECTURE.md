# CBT Chat Assistant - Architecture Documentation

## System Overview

The CBT Chat Assistant is a multi-tenant web application designed to help patients practice CBT skills between therapy sessions under therapist supervision.

---

## High-Level Architecture

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Patient   │────────▶│   Next.js    │────────▶│   FastAPI   │
│   Browser   │         │   Frontend   │         │   Backend   │
└─────────────┘         └──────────────┘         └─────────────┘
                                                         │
                                                         ▼
                                                  ┌─────────────┐
                                                  │  Supabase   │
                                                  │  Postgres   │
                                                  └─────────────┘
                                                         │
                                                         ▼
                                                  ┌─────────────┐
                                                  │ LLM APIs    │
                                                  │ DeepSeek +  │
                                                  │ Claude      │
                                                  └─────────────┘
```

---

## Component Architecture

### 1. Frontend (Next.js)

**Responsibilities:**
- Patient chat interface
- Therapist dashboard
- Session management UI
- Export/download functionality

**Key Components:**
- `app/patient/chat` - Real-time chat interface
- `app/therapist/dashboard` - Patient monitoring
- `lib/api.ts` - API client abstraction

**State Management:**
- Local React state (no Redux needed for MVP)
- SessionStorage for access codes/auth tokens

---

### 2. Backend (FastAPI)

**Responsibilities:**
- Request routing
- Business logic
- LLM orchestration
- Risk detection
- Database operations

**Module Breakdown:**

#### `api/routes/`
- **`chat.py`**: Patient-facing endpoints
  - POST `/api/chat/session/create` - Start session
  - POST `/api/chat/message` - Send message
  - POST `/api/chat/session/end` - End session

- **`therapist.py`**: Therapist dashboard endpoints
  - GET `/api/therapist/dashboard/{email}` - Dashboard data
  - GET `/api/therapist/session/{id}/transcript` - Session details
  - GET `/api/therapist/patient/{id}/export/json` - Data export

- **`admin.py`**: Admin/testing endpoints
  - POST `/api/admin/test-patient/create` - Create test patient

#### `services/`
- **`llm_service.py`**: LLM provider abstraction
  - `DeepSeekProvider` - Primary conversational AI
  - `ClaudeProvider` - Risk detection AI
  - Unified interface for both

- **`risk_detector.py`**: Safety system
  - Keyword-based fast scan
  - LLM-based nuanced analysis
  - Three-level risk classification (LOW/MEDIUM/HIGH)

- **`state_machine.py`**: Conversation flow controller
  - State transitions (CONSENT → INTAKE → MENU → SKILLS)
  - Skill-specific handlers (Thought Record, BA, Exposure, Coping)
  - Step-by-step guidance

#### `utils/`
- **`database.py`**: Supabase wrapper
  - CRUD operations for all entities
  - Complex queries (dashboard views)
  - Transaction management

- **`prompts.py`**: Prompt management
  - YAML loading
  - Template formatting
  - Hot-reloading support

---

### 3. Database (Supabase/PostgreSQL)

**Entity Relationship:**

```
therapists (1) ──┐
                 ├─→ therapist_patients (N) ──┐
patients (1) ────┘                             │
                                               ▼
                                          (M:N relationship)
                                               │
patients (1) ──→ sessions (N) ──┬─→ messages (N)
                                 ├─→ risk_events (N)
                                 └─→ skill_completions (N)
```

**Key Tables:**

1. **`therapists`**: Licensed therapists
2. **`patients`**: Adults using the tool (access code auth)
3. **`therapist_patients`**: M:N relationship
4. **`sessions`**: Chat sessions with state tracking
5. **`messages`**: Individual messages with risk scan results
6. **`risk_events`**: Flagged high-risk interactions
7. **`skill_completions`**: Completed CBT exercises
8. **`mood_ratings`**: Mood check-ins (0-10 scale)
9. **`session_summaries`**: Periodic aggregated summaries

**Views:**
- `v_therapist_dashboard`: Aggregated patient metrics
- `v_recent_flags`: Unreviewed risk events

---

### 4. LLM Integration

**Hybrid Approach:**

```
User Message
     │
     ▼
┌─────────────────┐
│ Risk Detection  │ ──── Claude 3.5 Haiku (safety-critical)
└─────────────────┘
     │
     ▼
   HIGH? ──Yes──▶ ESCALATE + END SESSION
     │
     No
     ▼
┌─────────────────┐
│ State Machine   │
│ Process         │
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ LLM Response    │ ──── DeepSeek-V3 (cost-effective)
└─────────────────┘
```

**Why Two Models?**
- **DeepSeek-V3**: 5x cheaper, excellent for conversational flow
- **Claude 3.5 Haiku**: More reliable for safety-critical risk detection

---

## Data Flow

### Patient Chat Message Flow

```
1. User sends message
        │
        ▼
2. Frontend → POST /api/chat/message
        │
        ▼
3. Backend saves user message to DB
        │
        ▼
4. Risk Detector scans message
        │
        ├──▶ HIGH risk? → Create risk_event
        │                  Flag session
        │                  Return crisis resources
        │                  END SESSION
        │
        ▼
5. State Machine processes message
        │
        ▼
6. LLM generates response (via DeepSeek)
        │
        ▼
7. Save assistant message to DB
        │
        ▼
8. Return response to frontend
        │
        ▼
9. Update UI with new message
```

### Therapist Dashboard Flow

```
1. Therapist logs in with email
        │
        ▼
2. GET /api/therapist/dashboard/{email}
        │
        ▼
3. Backend queries:
   - All patients (via therapist_patients)
   - Unreviewed risk events
   - Recent session stats
        │
        ▼
4. Aggregate data from multiple tables
        │
        ▼
5. Return dashboard view
        │
        ▼
6. Frontend renders:
   - Patient cards
   - Unreviewed flags (red alerts)
   - Session counts
```

---

## State Machine Details

### Conversation States

```
CONSENT ──────▶ INTAKE ──────▶ MENU ──────┐
                                           │
                                           ▼
         ┌─────────────────────────────────┴─────┐
         │                                       │
    THOUGHT_RECORD ────▶ TR_STEPS ─┐            │
    BEHAVIORAL_ACT ────▶ BA_STEPS ─┤            │
    EXPOSURE ──────────▶ EXP_STEPS ┤────▶ MENU ◀┘
    COPING ────────────▶ COP_STEPS ┤
    LEARN ─────────────────────────┘
```

### State Persistence

Each session stores:
- `current_state`: Current conversation state
- `current_skill`: Active skill (if any)
- `current_step`: Current step within skill
- `state_data`: JSON blob for skill-specific data

---

## Security Architecture

### Authentication (MVP)

**Simple Access Code System:**
- Patient enters access code → stored in sessionStorage
- Therapist enters email → stored in sessionStorage
- No passwords (MVP limitation)

**Production TODO:**
- OAuth 2.0 (Google/Auth0)
- JWT tokens
- Refresh tokens
- Rate limiting

### Risk Mitigation

**Multi-Layer Risk Detection:**

1. **Keyword Scan (Fast):**
   - Pattern matching on known risk phrases
   - Immediate flagging of obvious risks

2. **LLM Analysis (Nuanced):**
   - Context-aware risk assessment
   - False positive reduction
   - Intent detection

3. **Escalation Flow:**
   - HIGH: Immediate resources + end session + therapist flag
   - MEDIUM: Resources + continue with caution
   - LOW: Continue normally

### Data Privacy

**P0 (MVP):**
- Supabase row-level security (basic)
- Therapist can only access their patients
- No public endpoints

**Production TODO:**
- Encryption at rest
- Audit logs
- HIPAA compliance measures
- Data retention policies

---

## Scalability Considerations

### Current Limits (MVP)

- **Concurrent Users**: ~100 (Supabase free tier)
- **Database Storage**: 500MB (free tier)
- **API Calls**: No hard limit (LLM API rate limits apply)

### Scaling Strategy (Future)

1. **Database:**
   - Upgrade Supabase tier
   - Add read replicas
   - Implement caching (Redis)

2. **Backend:**
   - Horizontal scaling (multiple FastAPI instances)
   - Load balancer (NGINX)
   - Background jobs (Celery) for summaries

3. **LLM:**
   - Request batching
   - Response caching for common flows
   - Rate limiting per user

---

## Monitoring & Observability

### MVP Logging

- FastAPI access logs
- Supabase query logs
- LLM API response times

### Production TODO

- **APM**: DataDog, New Relic
- **Error Tracking**: Sentry
- **Metrics**: Prometheus + Grafana
- **Alerts**: PagerDuty for HIGH risk events

---

## Deployment Architecture

```
GitHub Repo
    │
    ├──▶ Vercel (Frontend)
    │    - Auto-deploy on push to main
    │    - CDN + serverless functions
    │
    └──▶ Railway (Backend)
         - Docker container
         - Auto-deploy on push to main
         - Environment variables
              │
              ▼
         Supabase (Database)
         - Managed PostgreSQL
         - Auto-backups
```

---

## Cost Optimization

### Current Strategy

1. **Use DeepSeek for 90% of LLM calls** (~10x cheaper than GPT-4)
2. **Use Claude only for risk detection** (safety-critical)
3. **Free tiers for infrastructure** (Supabase, Vercel)
4. **Minimal backend hosting** ($5-10/month Railway)

### Estimated Costs (1000 users/month)

- LLM: ~$60
- Backend: ~$10
- Database: $0 (free tier)
- Frontend: $0 (free tier)

**Total: ~$70/month**

---

## Testing Strategy (Future)

### Unit Tests
- `pytest` for backend services
- `Jest` for frontend components

### Integration Tests
- API endpoint tests
- Database transaction tests

### E2E Tests
- Playwright for full user flows

### Safety Tests
- Risk detection accuracy
- False positive/negative rates

---

## Conclusion

This architecture prioritizes:
1. **Safety**: Multi-layer risk detection
2. **Cost**: DeepSeek primary, Claude for safety
3. **Simplicity**: Monolithic MVP, scale later
4. **Flexibility**: YAML prompts, hot-reloadable

For production, add: auth, encryption, monitoring, testing.
