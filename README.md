# CBT Chat Assistant - MVP

A **CBT-aligned chat assistant** that helps adults practice CBT skills **between therapy sessions** with strict scope limits and automatic risk escalation. This is a tool for psychologists to monitor their patients' CBT practice sessions.

## 🎯 Product Goal

Help adults practice CBT skills (psychoeducation, thought records, behavioral activation, exposure planning, coping skills) between therapy sessions, with **automatic risk detection** and **therapist monitoring**.

**NOT a crisis line or therapy replacement.**

---

## 📋 Table of Contents

- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Architecture](#-architecture)
- [Setup Guide](#-setup-guide)
- [Development](#-development)
- [API Documentation](#-api-documentation)
- [Cost Estimates](#-cost-estimates)
- [Deployment](#-deployment)
- [Security & Privacy](#-security--privacy)

---

## ✨ Features

### P0 - Safety & Boundaries (MVP)

- ✅ **Opening gate:** Clear disclaimer + consent + scope
- ✅ **Risk detector v1:** Keyword + LLM hybrid (SI/self-harm, harm to others, psychosis)
- ✅ **Escalation ladder:** Clarify → ground → resources → **stop** chat if acute risk
- ✅ **Hard refusals:** Medical/diagnostic/medication questions → decline + redirect
- ✅ **Privacy controls:** Supabase storage, session export (JSON/CSV)

### P0 - CBT Skill Loops

- ✅ **Thought Record (ABC):** Situation → Thought → Emotion → Evidence → Alternative → Re-rate
- ✅ **Behavioral Activation:** Pick activity → Break into steps → Schedule → If-then plan → Debrief
- ✅ **Exposure Planner:** Build hierarchy → Choose target → Predict → Run → Debrief
- ✅ **Coping Toolbox:** Breathing, grounding, muscle relaxation, urge surfing
- ✅ **Psychoeducation:** CBT concepts, cognitive distortions, BA/exposure science

### P0 - Logging & Therapist Dashboard

- ✅ **Session memory:** Last sessions, top triggers, mood tracking
- ✅ **Therapist dashboard:** Patient overview, unreviewed flags, session transcripts
- ✅ **Risk event flags:** Immediate flagging + async therapist review
- ✅ **Export:** JSON/CSV download of patient data

---

## 🛠 Tech Stack

### Backend
- **Framework:** FastAPI (Python 3.11+)
- **Database:** Supabase (PostgreSQL)
- **LLMs:**
  - **Primary:** DeepSeek-V3 (~$0.27-1.10 per 1M tokens) - cost-effective
  - **Risk Detection:** Claude 3.5 Haiku (~$0.80-4 per 1M tokens) - safety-critical
- **Prompt Management:** YAML-based editable templates

### Frontend
- **Framework:** Next.js 14 (TypeScript)
- **Styling:** Tailwind CSS + shadcn/ui components
- **API Client:** Axios

### Infrastructure
- **Deployment:** Vercel (frontend) + Railway/Fly.io (backend)
- **Database:** Supabase (free tier works for MVP)

---

## 🏗 Architecture

### Multi-Tenant Design

```
Therapist (1) → Many Patients (N)
    ↓
Patient (1) → Many Sessions (N)
    ↓
Session (1) → Many Messages (N)
              Many Risk Events (N)
              Many Skill Completions (N)
```

### Backend Structure

```
backend/
├── api/routes/          # FastAPI endpoints
│   ├── chat.py         # Patient chat endpoints
│   ├── therapist.py    # Therapist dashboard endpoints
│   └── admin.py        # Admin/test endpoints
├── services/
│   ├── llm_service.py      # LLM abstraction (DeepSeek + Claude)
│   ├── risk_detector.py    # Hybrid keyword + LLM risk detection
│   └── state_machine.py    # CBT conversation flows
├── models/
│   └── schemas.py          # Pydantic models
├── config/
│   ├── prompts.yaml        # Editable prompt templates
│   └── settings.py         # Environment configuration
└── utils/
    ├── database.py         # Supabase client wrapper
    └── prompts.py          # Prompt loader/formatter
```

### State Machine Flow

```
SESSION_START
  → CONSENT (agree? else END)
  → INTAKE (goals, preferred tone, country)
  → MENU
      ├─→ THOUGHT_RECORD → steps → complete → MENU
      ├─→ BEHAVIORAL_ACTIVATION → steps → complete → MENU
      ├─→ EXPOSURE → steps → complete → MENU
      ├─→ COPING → technique → complete → MENU
      └─→ LEARN → card → MENU
  (Risk scan at every turn)
END
```

---

## 🚀 Setup Guide

### Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **Supabase account** (free tier works)
- **API Keys:**
  - DeepSeek API key ([get one here](https://platform.deepseek.com/))
  - Anthropic API key ([get one here](https://console.anthropic.com/))

### 1. Database Setup (Supabase)

1. Create a Supabase project at [supabase.com](https://supabase.com)
2. Run the migration script:

```bash
# Copy the SQL from supabase/migrations/001_initial_schema.sql
# Paste it into Supabase SQL Editor and run it
```

3. Note your Supabase credentials:
   - Project URL
   - Anon Key
   - Service Key

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Edit .env with your credentials:
# - SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_KEY
# - DEEPSEEK_API_KEY
# - ANTHROPIC_API_KEY
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create .env.local
cp .env.local.example .env.local

# Edit .env.local:
# NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 4. Run the Application

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

Visit:
- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

### 5. Test Login Credentials

**Patient Access Code:** `PATIENT001` (created by seed data)

**Therapist Email:** `dr.smith@example.com` (created by seed data)

---

## 💻 Development

### Editing Prompts (No Code Changes!)

All prompts are in `backend/config/prompts.yaml`. Edit them directly and reload:

```bash
# Hot-reload prompts without restarting:
curl -X POST http://localhost:8000/api/chat/prompts/reload
```

### Adding New Patients

Use the admin API or create directly in Supabase:

```bash
curl -X POST "http://localhost:8000/api/admin/test-patient/create" \
  -H "Content-Type: application/json" \
  -d '{"preferred_name": "Jane", "country_code": "US"}'
```

### Database Access

Use Supabase dashboard or connect via psql:
```bash
psql "postgresql://postgres:[YOUR-PASSWORD]@[PROJECT-REF].supabase.co:5432/postgres"
```

---

## 📚 API Documentation

### Patient Endpoints

#### POST `/api/chat/session/create`
Create a new session.

**Request:**
```json
{
  "patient_access_code": "PATIENT001",
  "session_goal": "Work on anxious thoughts"
}
```

#### POST `/api/chat/message`
Send a message in a session.

**Request:**
```json
{
  "patient_access_code": "PATIENT001",
  "session_id": "uuid",
  "message": "I want to do a thought record"
}
```

**Response:**
```json
{
  "session_id": "uuid",
  "message": {
    "id": "uuid",
    "role": "assistant",
    "content": "Great! Let's start...",
    "created_at": "2025-01-15T10:00:00Z"
  },
  "risk_detected": false,
  "risk_level": "none",
  "should_end_session": false
}
```

### Therapist Endpoints

#### GET `/api/therapist/dashboard/{therapist_email}`
Get dashboard data with patient overview and flags.

#### GET `/api/therapist/session/{session_id}/transcript`
Get full session transcript.

**Query params:** `therapist_email`

#### GET `/api/therapist/patient/{patient_id}/export/json`
Export patient data as JSON.

#### GET `/api/therapist/patient/{patient_id}/export/csv`
Export patient skills as CSV.

---

## 💰 Cost Estimates

### LLM Costs (1000 users/month, 4 conversations each)

**Assumptions:**
- 10 back-and-forth exchanges per conversation = 20 LLM calls
- ~500 tokens input, ~300 tokens output per call
- Total: 64M tokens/month (32M input, 32M output)

**DeepSeek-V3 (Primary):**
- Input: 32M × $0.27/1M = $8.64
- Output: 32M × $1.10/1M = $35.20
- **Subtotal: ~$44/month**

**Claude 3.5 Haiku (Risk Detection Only - ~10% of calls):**
- Input: 3.2M × $0.80/1M = $2.56
- Output: 3.2M × $4.00/1M = $12.80
- **Subtotal: ~$15/month**

**Total LLM Costs: ~$60/month** for 1000 users

### Infrastructure Costs

- **Supabase:** Free tier (500MB database, 2GB bandwidth)
- **Vercel:** Free tier (100GB bandwidth, unlimited deployments)
- **Backend Hosting (Railway/Fly.io):** ~$5-10/month

**Grand Total: ~$65-70/month** for 1000 users

---

## 🚢 Deployment

### Backend Deployment (Railway)

1. Create Railway account at [railway.app](https://railway.app)
2. Create new project from GitHub repo
3. Set environment variables in Railway dashboard
4. Deploy automatically on push to `main`

### Frontend Deployment (Vercel)

1. Create Vercel account at [vercel.com](https://vercel.com)
2. Import GitHub repo
3. Set `NEXT_PUBLIC_API_URL` to your Railway backend URL
4. Deploy automatically on push to `main`

### Environment Variables Checklist

**Backend:**
- ✅ `SUPABASE_URL`
- ✅ `SUPABASE_KEY`
- ✅ `SUPABASE_SERVICE_KEY`
- ✅ `DEEPSEEK_API_KEY`
- ✅ `ANTHROPIC_API_KEY`
- ✅ `CORS_ORIGINS` (set to Vercel URL)

**Frontend:**
- ✅ `NEXT_PUBLIC_API_URL` (Railway backend URL)

---

## 🔒 Security & Privacy

### P0 Security Features

1. **Risk Detection:** Hybrid keyword + LLM (Claude) for safety
2. **Automatic Escalation:** High-risk messages → immediate flag + resources + session end
3. **Therapist Notifications:** All risk events logged and flagged for review
4. **Data Privacy:**
   - No PHI in logs
   - Session data accessible only by assigned therapist
   - Export controls (therapist-only)

### Limitations (MVP)

- ⚠️ **No authentication:** Simple access codes (add OAuth in production)
- ⚠️ **No encryption at rest:** Rely on Supabase defaults (add encryption in production)
- ⚠️ **No audit logs:** Basic logging only (add comprehensive audit trail in production)

---

## 📝 Future Enhancements (Post-MVP)

- [ ] **P1 Features:**
  - Habits/reminders (local notifications)
  - Therapist handoff mode (PDF summary)
  - Multi-language support
- [ ] **Authentication:** OAuth + role-based access control
- [ ] **Real-time:** WebSocket for live therapist monitoring
- [ ] **Analytics:** Usage dashboards, outcome tracking
- [ ] **Mobile App:** React Native version

---

## 🤝 Contributing

This is an MVP. For production use:
1. Add comprehensive testing (pytest + Jest)
2. Implement proper authentication
3. Add rate limiting and DDoS protection
4. Set up monitoring (Sentry, DataDog)
5. Add HIPAA compliance measures if handling PHI

---

## 📄 License

MIT License - see LICENSE file for details

---

## 🆘 Support

For issues or questions:
- **Technical Issues:** Open a GitHub issue
- **Clinical Questions:** Consult with licensed mental health professionals

**Remember:** This tool is NOT a replacement for therapy or crisis services.

**Crisis Resources:**
- US: 988 (Suicide & Crisis Lifeline)
- UK: 116 123 (Samaritans)
- EU: 112 (Emergency Services)

---

Built with ❤️ for CBT practitioners and their clients.