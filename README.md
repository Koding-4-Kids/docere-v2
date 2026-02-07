# Docere v2

**A memory-augmented, self-improving learning agent for LMS integration.**

Docere v2 is an intelligent tutoring system that goes beyond standard LLM chatbots. It maintains persistent semantic memory of each student's learning journey, adaptively selects teaching strategies using multi-armed bandit algorithms, and scores every interaction for educational effectiveness — then uses those scores to evolve its own strategies over time.

Built for integration with Canvas and Moodle via LTI 1.3, Docere requires zero manual setup from teachers. Course materials, assignments, grades, and rosters are auto-pulled from the LMS and embedded into a vector database for semantic retrieval during tutoring sessions.

> **Authors:** Youdahe Asfaw, Kofi Osei, Guarionex Salivia
> **Institution:** Gustavus Adolphus College
> **Paper:** *"Learning Agents That Learn"*

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Core Systems](#core-systems)
  - [Tutoring Agent](#1-tutoring-agent)
  - [Memory Layer](#2-memory-layer)
  - [Process Verification](#3-process-verification)
  - [Self-Improvement Loop](#4-self-improvement-loop)
  - [LMS Integration](#5-lms-integration)
  - [Research Infrastructure](#6-research-infrastructure)
- [Data Model](#data-model)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration Reference](#configuration-reference)
- [Research Design](#research-design)
- [Roadmap](#roadmap)

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                         FastAPI Server                           │
│  /api/v1/chat  /api/v1/lms  /api/v1/analytics  /api/v1/...     │
└───────────────────────┬──────────────────────────────────────────┘
                        │
          ┌─────────────▼─────────────┐
          │      TutoringAgent        │
          │   (core/agent.py)         │
          │                           │
          │  1. Retrieve memory ctx   │
          │  2. Select strategy       │
          │  3. Build system prompt   │
          │  4. Call LLM              │
          │  5. Post-process          │
          └──┬────────┬──────────┬────┘
             │        │          │
    ┌────────▼──┐ ┌───▼────┐ ┌──▼──────────────┐
    │  Memory   │ │Strategy│ │  Process         │
    │  Layer    │ │Archive │ │  Verifier        │
    │           │ │ (UCB1) │ │  (LLM-as-judge)  │
    └──┬──┬──┬──┘ └───┬────┘ └──┬──────────────┘
       │  │  │        │         │
       │  │  │   ┌────▼────┐    │
       │  │  │   │Strategy │    │
       │  │  │   │Evolver  │    │
       │  │  │   │(weekly) │    │
       │  │  │   └─────────┘    │
       │  │  │                  │
  ┌────▼┐ │ ┌▼────────┐  ┌─────▼──────┐
  │Qdrant│ │ │PostgreSQL│  │Outcome     │
  │(vec) │ │ │(relat.)  │  │Tracker     │
  └──────┘ │ └──────────┘  └────────────┘
           │
    ┌──────▼──────┐
    │ LMS Adapter │
    │ Canvas/     │
    │ Moodle      │
    └─────────────┘
```

**Data flow for a single student message:**

1. Student sends a message via the chat API
2. **Memory Layer** assembles context by parallel-fetching from three sources: teacher materials (Qdrant), student profile (PostgreSQL), and interaction history (Qdrant)
3. **Strategy Archive** selects a teaching strategy using UCB1 bandit (exploration vs. exploitation), gated by study group
4. System prompt is built from memory context + strategy instructions
5. LLM generates a tutoring response
6. Message pair is persisted and async post-processing fires: memory capture, embedding generation, and process verification scoring

---

## Core Systems

### 1. Tutoring Agent

**`src/docere/core/agent.py`**

The central orchestrator. For each student message, it coordinates memory retrieval, strategy selection, prompt construction, and LLM invocation.

```
Student message → Memory retrieval → Strategy selection → Prompt building → LLM call → Persist → Post-process
```

**Key behaviors:**
- Feature-gated by `study_group` — the control group receives no memory or strategy augmentation, enabling rigorous ablation studies
- Conversation history is fetched from PostgreSQL (last 20 messages) and prepended to the LLM call
- Every response records metadata: strategy used, memory tokens consumed, model version
- Post-processing runs asynchronously: memory capture generates an embedding for the Q&A pair and stores it in both Qdrant (for future semantic retrieval) and PostgreSQL (for relational queries)

**System prompt composition:**
```
Base tutoring guidelines
  + Strategy instructions (if treatment_full group)
  + Student profile summary
  + Concept mastery levels
  + Recent grades
  + Relevant course materials (from Qdrant)
  + Relevant past interactions (from Qdrant)
```

---

### 2. Memory Layer

**`src/docere/core/memory/`**

A three-source semantic memory system with token budgeting.

#### 2.1 Memory Context Assembly (`memory_layer.py`)

Parallel-fetches from all three sources using `asyncio.gather()`:

| Source | Storage | Retrieval Method | Purpose |
|--------|---------|-----------------|---------|
| Teacher context | Qdrant | Cosine similarity against student query | Relevant syllabus, lectures, assignments |
| Student profile | PostgreSQL | Direct lookup | Learning patterns, engagement, grades |
| Interaction history | Qdrant | Cosine similarity + diversity filter | Relevant past conversations |

**Token budget allocation** (default 4,000 tokens max):
1. Student profile (highest priority, ~200 tokens)
2. Concept mastery levels (~100 tokens)
3. Recent grades (~150 tokens)
4. Course materials (variable, truncated to fit)
5. Interaction history (fills remaining budget)

#### 2.2 Student Profile Builder (`student_profile.py`)

Maintains per-student, per-course aggregate profiles:
- **Engagement level:** Classified as `unknown` → `low` → `medium` → `high` based on interaction count thresholds (3, 10, 20)
- **Confusion tracking:** Running average of confusion scores across all interactions
- **Concept mastery:** Per-concept skill levels (0.0–1.0) adjusted incrementally — low confusion raises mastery by +0.05, high confusion lowers it by -0.03
- **Narrative summaries:** Auto-generated via LLM, producing human-readable profiles like *"Alex has been struggling with recursion for 2 weeks. She responds well to visual analogies and step-by-step examples."*

#### 2.3 Interaction Store (`interaction_store.py`)

Stores and retrieves tutoring exchanges in Qdrant with a **diversity filter**:
- Fetches 3x the requested number of results
- Iteratively selects results using a greedy diversity algorithm: each candidate must have cosine similarity below the `diversity_threshold` (default 0.65) against all already-selected results
- Prevents the context window from being filled with near-duplicate memories

#### 2.4 Teacher Context Manager (`teacher_context.py`)

Auto-ingests course materials from the LMS on first LTI launch:
- **Chunking:** Splits materials at paragraph boundaries (max 2,000 chars per chunk)
- **Compression:** Materials over 3,000 characters are compressed via CARTRIDGES-inspired synthetic Q&A distillation — the LLM generates 5–10 Q&A pairs capturing key concepts, requirements, and common confusion points
- **Retrieval:** Cosine similarity search against the student's current query

#### 2.5 Memory Compressor (`compressor.py`)

Periodic compression of raw memories to prevent unbounded growth:
- Triggered when a student exceeds a configurable threshold (default: 50 uncompressed memories)
- Groups memories by type, processes in batches of 20
- LLM generates 3–5 sentence summaries preserving: key struggles, learning patterns, breakthroughs, trajectory
- Originals are marked `is_compressed = True` and linked to the summary via `compressed_into` UUID
- Baseline seed strategies are never compressed

---

### 3. Process Verification

**`src/docere/core/verification/`**

Adapts MATH-SHEPHERD's process reward model approach to open-ended educational dialogues. Instead of verifying math steps, Docere scores whether tutoring interactions actually helped students learn.

#### 3.1 Scoring Dimensions

| Dimension | Range | Weight | Description |
|-----------|-------|--------|-------------|
| Helpfulness | 0.0–1.0 | 0.35 | Did the response address the student's actual need? |
| Clarity | 0.0–1.0 | 0.25 | Was the explanation appropriate for this student's level? |
| Understanding delta | -1.0–1.0 | 0.25 | How much did understanding likely change? |
| Engagement | 0.0–1.0 | 0.15 | Did the response encourage continued productive learning? |

**Composite score** = 0.35 * helpfulness + 0.25 * clarity + 0.25 * max(0, understanding_delta) + 0.15 * engagement

#### 3.2 Hybrid Scoring (`process_verifier.py`)

Two-phase scoring approach:

**Phase 1 — Heuristic scoring** (immediate, no LLM call):
- **Clarity:** Sentence length analysis (ideal 10–20 words for tutoring), presence of examples/code blocks, response-to-question length ratio
- **Engagement:** Time-to-followup mapping — <30s = 0.9 (very engaged), 30s–2min = 0.7, 2–10min = 0.5, 10min–1hr = 0.3, >1hr = 0.1
- **Quality:** Presence of questions (Socratic engagement bonus), structured formatting (bullet points, numbered lists), length penalties for extremes

**Phase 2 — LLM-as-judge** (deferred until student responds or 300s timeout):
- Claude evaluates the interaction with the student's followup as evidence
- Student followup is classified into: `understood`, `still_confused`, `new_question`, `off_topic`
- Final scores are a weighted blend: 70% LLM + 30% heuristic for clarity, 60/40 for engagement

#### 3.3 Outcome Tracker (`outcome_tracker.py`)

Links interaction scores to downstream LMS grade outcomes:
- When a grade arrives from the LMS sync, searches for tutoring interactions from the past 14 days about related concepts
- Updates the `subsequent_performance` field on matching interaction scores
- Enables analysis of whether specific tutoring interactions correlated with better/worse outcomes

---

### 4. Self-Improvement Loop

**`src/docere/core/improvement/`**

The key differentiator: Docere doesn't just remember — it learns which teaching approaches work and evolves new ones.

#### 4.1 Strategy Archive (`strategy_archive.py`)

Maintains a library of teaching strategies, initialized with 5 seed strategies:

| Strategy | Type | Core Approach |
|----------|------|---------------|
| Socratic Questioning | `socratic` | Guide through discovery via questions, never give answers directly |
| Analogy-First | `analogy` | Real-world analogies before formal concepts |
| Scaffolded Hints | `scaffolded` | 3-level progressive hints: concept → example → walkthrough |
| Error-Focused | `error_focused` | Explain WHY errors happen, address common misconceptions |
| Minimal Intervention | `minimal` | Shortest possible hint, encourage productive struggle |

**UCB1 multi-armed bandit selection:**

```
UCB1(strategy) = avg_score + sqrt(2 * ln(total_uses) / strategy_uses)
```

- Balances exploitation (pick what works) vs. exploration (try underused strategies)
- Strategies with 0 uses get `+inf` score (forced exploration)
- Only active for the `treatment_full` study group — control and `treatment_memory` groups receive no strategy augmentation

**Outcome recording:**
- Running average score maintained per strategy
- Success rate tracked (interactions with composite score >= 0.6)
- Used by the evolver to identify top/bottom performers

#### 4.2 Strategy Evolver (`strategy_evolver.py`)

Runs on a weekly cycle. Inspired by the Darwin Godel Machine's archive-based exploration:

**Step 1 — Mutate top K performers:**
- Selects top K strategies by average score (default K=3)
- For each, retrieves best/worst performing interaction contexts
- Claude generates a variant: same core approach but refined based on what worked and what didn't
- New strategy is linked to its parent via `parent_strategy_id` with `generation` incremented
- Requires minimum 5 uses before a strategy is eligible for mutation

**Step 2 — Prune weak strategies:**
- Strategies with >20 uses and avg_score < 0.3 are deactivated (`is_active = False`)
- Seed (baseline) strategies are never pruned — they serve as the evolutionary foundation

**Evolution lineage** is fully tracked: parent → child → grandchild, with generation numbers, enabling analysis of whether evolved strategies actually outperform their ancestors.

#### 4.3 Experiment Runner (`experiment_runner.py`)

Manages the ablation study's feature gating:

**Deterministic group assignment:**
- Uses SHA-256 hash of `(randomization_seed + student_id)` for reproducible but random-looking assignment
- Supports arbitrary study arms (default: `control`, `treatment_memory`, `treatment_full`)

**Feature flags by group:**

| Group | Memory | Verification | Self-Improvement |
|-------|--------|-------------|-----------------|
| `control` | Off | Off | Off |
| `treatment_memory` | On | Off | Off |
| `treatment_full` | On | On | On |

All assignment events are logged to `research_events` for audit trail.

---

### 5. LMS Integration

**`src/docere/integrations/lms/`**

Zero-configuration LMS integration. Teachers do nothing — everything is auto-pulled.

#### 5.1 Abstract Adapter Interface (`base.py`)

Defines normalized data structures and abstract methods:
- `LMSCourse`, `LMSAssignment`, `LMSSubmission`, `LMSEnrollment`, `LMSCourseMaterial`
- `full_sync(course_id)` — pulls everything in one call (first LTI launch)
- Individual methods: `get_course()`, `get_assignments()`, `get_submissions()`, `get_enrollments()`, `get_course_materials()`

Implementations: `CanvasAdapter`, `MoodleAdapter`

#### 5.2 LMS Sync Service (`services/lms_sync_service.py`)

**Full sync** (on first LTI launch):
1. Upsert course (create or update from LMS data)
2. Sync student roster → create/update `User` records
3. Sync assignments with descriptions, due dates, points
4. Sync submissions/grades
5. Sync course materials (files, modules, pages)

**Incremental sync** (every 2 hours via background task):
- Pulls latest assignments and submissions only
- Updates existing records or creates new ones
- Builds lookup maps for efficient batch processing

#### 5.3 Background Task (`tasks/lms_sync.py`)

Iterates all LMS-enabled courses, instantiates the appropriate adapter, runs incremental sync. Scheduled via ARQ (Redis-backed async task queue).

---

### 6. Research Infrastructure

#### Data Collection Models

- **`LearningAnalyticsEvent`** — Generic event log (interactions, grade changes, logins) indexed by student, course, and event type
- **`Alert`** — Instructor notifications with severity levels, evidence, and recommended actions (struggling student, breakthrough, class-wide pattern)
- **`StudyConfig`** — Per-course ablation study configuration with randomization seed and group definitions
- **`ResearchEvent`** — Audit log of all research-relevant events (group assignments, feature flag changes)

---

## Data Model

### Entity Relationship Overview

```
Users ──< Enrollments >── Courses
  │                          │
  │                          ├──< Assignments ──< Submissions
  │                          ├──< CourseMaterials
  │                          └──< StudyConfig ──< ResearchEvents
  │
  ├──< Conversations ──< Messages ──< InteractionScores
  │         │
  │         └── strategy_id ──> Strategies ──< StrategyScores
  │
  ├──< StudentProfiles
  ├──< ConceptMastery
  ├──< MemoryRecords
  └──< LearningAnalyticsEvents
```

### Key Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `users` | Students, instructors, admins (auto-created from LMS) | `external_lms_id`, `lms_platform`, `role` |
| `courses` | Synced from Canvas/Moodle | `syllabus_text`, `lms_sync_enabled`, `last_synced_at` |
| `enrollments` | Student ↔ course with study group | `study_group` (control/treatment_memory/treatment_full) |
| `conversations` | Tutoring sessions | `student_id`, `course_id`, `strategy_id`, `study_group` |
| `messages` | Individual messages with embedding IDs | `role`, `content`, `metadata` (strategy info, memory tokens) |
| `memory_records` | Captured interactions, grades, insights | `memory_type`, `concepts[]`, `confusion_score`, `is_compressed` |
| `student_profiles` | Aggregate per-student-per-course profile | `engagement_level`, `current_grade`, `profile_summary` |
| `concept_mastery` | Per-concept skill tracking | `mastery_level`, `times_practiced`, `times_struggled` |
| `interaction_scores` | Process verification scores | `helpfulness`, `clarity`, `engagement`, `understanding_delta`, `composite_score` |
| `strategies` | Teaching strategy archive with evolution lineage | `prompt_template`, `avg_score`, `parent_strategy_id`, `generation` |
| `strategy_scores` | Per-interaction strategy outcomes | `score`, `context_metadata` |
| `study_config` | Ablation study parameters | `groups`, `randomization_seed`, `is_active` |
| `research_events` | Audit log for research | `event_type`, `event_data` |
| `alerts` | Instructor notifications | `alert_type`, `severity`, `recommended_action` |
| `learning_analytics_events` | Generic analytics events | `event_type`, `event_data` |

All tables use UUID primary keys and timezone-aware timestamps.

---

## API Reference

Base URL: `/api/v1/`

### Chat (Implemented)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/chat/conversations` | Start a new tutoring session |
| `GET` | `/chat/conversations` | List student's conversations (filterable by course) |
| `GET` | `/chat/conversations/{id}` | Get conversation with full message history |
| `POST` | `/chat/conversations/{id}/messages` | Send message, receive AI tutoring response |

**`POST /chat/conversations/{id}/messages`** — The main tutoring endpoint:

Request:
```json
{
  "content": "I don't understand how recursion works"
}
```

Response:
```json
{
  "message": {
    "id": "uuid",
    "role": "assistant",
    "content": "Let's start with something you already know...",
    "model_used": "claude-sonnet-4-20250514",
    "token_count": 256,
    "created_at": "2025-01-15T10:30:00Z"
  },
  "strategy_used": "Analogy-First",
  "memory_context_tokens": 1847
}
```

### Planned Endpoints

| Route Group | Endpoints | Status |
|-------------|-----------|--------|
| `/auth` | JWT-based authentication | Placeholder |
| `/courses` | Course list, detail, sync triggers | Placeholder |
| `/students` | Student profiles, concept mastery | Placeholder |
| `/instructor` | Dashboard, at-risk alerts, class patterns | Placeholder |
| `/memory` | Memory retrieval, management | Placeholder |
| `/analytics` | Course metrics, strategy performance, research export | Placeholder |
| `/lms` | Sync hooks, webhook receivers | Placeholder |

### Health Check

```
GET /health → {"status": "ok", "version": "0.1.0"}
```

---

## Project Structure

```
docere-v2/
├── src/docere/
│   ├── main.py                          # FastAPI app entry point, router registration
│   ├── config.py                        # Pydantic settings (env vars)
│   ├── dependencies.py                  # Dependency injection (DB sessions)
│   │
│   ├── api/                             # Route handlers
│   │   ├── chat.py                      # Tutoring conversation endpoints (implemented)
│   │   ├── auth.py                      # Authentication (placeholder)
│   │   ├── courses.py                   # Course management (placeholder)
│   │   ├── students.py                  # Student profiles (placeholder)
│   │   ├── instructor.py               # Instructor dashboard (placeholder)
│   │   ├── memory.py                    # Memory management (placeholder)
│   │   ├── analytics.py                # Analytics & research export (placeholder)
│   │   └── lms.py                       # LMS sync hooks (placeholder)
│   │
│   ├── core/                            # Core agent logic
│   │   ├── agent.py                     # TutoringAgent orchestrator
│   │   ├── memory/
│   │   │   ├── memory_layer.py          # Three-source context assembly
│   │   │   ├── student_profile.py       # Profile builder & narrative generation
│   │   │   ├── interaction_store.py     # Qdrant interaction storage & diversity retrieval
│   │   │   ├── teacher_context.py       # Course material ingestion & compression
│   │   │   └── compressor.py            # Memory compression (CARTRIDGES-inspired)
│   │   ├── verification/
│   │   │   ├── process_verifier.py      # Hybrid LLM + heuristic interaction scoring
│   │   │   ├── interaction_scorer.py    # Heuristic scoring (clarity, engagement, quality)
│   │   │   └── outcome_tracker.py       # Links interaction scores to LMS grade outcomes
│   │   └── improvement/
│   │       ├── strategy_archive.py      # UCB1 bandit strategy selection
│   │       ├── strategy_evolver.py      # Weekly mutation + pruning cycle
│   │       └── experiment_runner.py     # Ablation study management & feature gating
│   │
│   ├── integrations/                    # External service adapters
│   │   ├── llm/
│   │   │   ├── client.py               # Anthropic Claude API wrapper
│   │   │   └── embeddings.py           # Voyage AI / OpenAI embeddings with LRU cache
│   │   ├── lms/
│   │   │   ├── base.py                 # Abstract LMS adapter interface
│   │   │   ├── canvas.py               # Canvas REST API adapter
│   │   │   └── moodle.py               # Moodle API adapter
│   │   └── vector_db/
│   │       └── qdrant.py               # Qdrant vector DB client
│   │
│   ├── models/                          # SQLAlchemy ORM models
│   │   ├── base.py                      # Base class, UUID + timestamp mixins
│   │   ├── user.py                      # User (auto-created from LMS)
│   │   ├── course.py                    # Course, Enrollment, Assignment, Submission, CourseMaterial
│   │   ├── conversation.py             # Conversation, Message
│   │   ├── memory.py                    # MemoryRecord, StudentProfile, ConceptMastery
│   │   ├── verification.py             # InteractionScore
│   │   ├── strategy.py                 # Strategy, StrategyScore
│   │   ├── research.py                 # StudyConfig, ResearchEvent
│   │   ├── alert.py                    # Instructor alerts
│   │   └── analytics.py               # LearningAnalyticsEvent
│   │
│   ├── schemas/                         # Pydantic request/response schemas
│   │   └── chat.py                      # Chat endpoint schemas
│   │
│   ├── services/                        # Business logic
│   │   └── lms_sync_service.py          # Full + incremental LMS sync
│   │
│   ├── tasks/                           # Background jobs (ARQ)
│   │   └── lms_sync.py                  # Periodic course sync (every 2 hours)
│   │
│   └── utils/                           # Helpers
│
├── frontend/                            # React + TypeScript SPA
│   └── src/
│       ├── App.tsx
│       ├── pages/ChatPage.tsx
│       ├── components/
│       │   ├── ClaudeChatInput.tsx
│       │   ├── MessageBubble.tsx
│       │   ├── CourseSelector.tsx
│       │   ├── Sidebar.tsx
│       │   └── ThemeToggle.tsx
│       └── hooks/useTheme.ts
│
├── alembic/                             # Database migrations
│   ├── env.py
│   └── versions/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── docker-compose.yml                   # Local dev (PostgreSQL, Redis, Qdrant)
├── pyproject.toml                       # Python dependencies & tool config
├── alembic.ini                          # Migration config
└── .env.example                         # Environment template
```

---

## Getting Started

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- An Anthropic API key
- A Voyage AI or OpenAI API key (for embeddings)

### 1. Clone and install

```bash
git clone https://github.com/Koding-4-Kids/docere-v2.git
cd docere-v2
```

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Start infrastructure

```bash
docker compose up -d
```

This starts:
- **PostgreSQL 16** on port 5432
- **Redis 7** on port 6379
- **Qdrant** on port 6333 (HTTP) and 6334 (gRPC)

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set:
- `ANTHROPIC_API_KEY` — your Anthropic key
- `VOYAGE_API_KEY` — your Voyage AI key (or `OPENAI_API_KEY` for OpenAI embeddings)
- For LMS integration: `CANVAS_BASE_URL`, `CANVAS_API_TOKEN` (or Moodle equivalents)

### 4. Run database migrations

```bash
alembic upgrade head
```

### 5. Start the server

```bash
uvicorn docere.main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at `http://localhost:8000/docs`

### 6. Start the frontend (optional)

```bash
cd frontend
npm install
npm run dev
```

---

## Configuration Reference

All configuration is via environment variables (loaded from `.env`):

### Core Services

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://docere:docere_dev@localhost:5432/docere` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant vector DB |

### LLM & Embeddings

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Anthropic API key (required) |
| `DEFAULT_MODEL` | `claude-sonnet-4-20250514` | Claude model for tutoring |
| `VOYAGE_API_KEY` | — | Voyage AI embeddings (preferred) |
| `OPENAI_API_KEY` | — | OpenAI embeddings (fallback) |
| `EMBEDDING_MODEL` | `voyage-3` | Embedding model name |
| `EMBEDDING_DIMENSIONS` | `1024` | Vector dimensions |

### Memory Layer Tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `MEMORY_SIMILARITY_THRESHOLD` | `0.60` | Min cosine similarity for memory retrieval |
| `MEMORY_DIVERSITY_THRESHOLD` | `0.65` | Max similarity between selected memories |
| `MEMORY_MAX_CONTEXT_TOKENS` | `4000` | Token budget for memory context |
| `MEMORY_COMPRESSION_THRESHOLD` | `50` | Compress after N uncompressed memories |

### Process Verification Weights

| Variable | Default | Description |
|----------|---------|-------------|
| `VERIFICATION_HELPFULNESS_WEIGHT` | `0.35` | Helpfulness weight in composite score |
| `VERIFICATION_CLARITY_WEIGHT` | `0.25` | Clarity weight |
| `VERIFICATION_UNDERSTANDING_WEIGHT` | `0.25` | Understanding delta weight |
| `VERIFICATION_ENGAGEMENT_WEIGHT` | `0.15` | Engagement weight |
| `VERIFICATION_FOLLOWUP_TIMEOUT_SECONDS` | `300` | Seconds to wait for student followup |

### Self-Improvement

| Variable | Default | Description |
|----------|---------|-------------|
| `STRATEGY_MIN_USES_FOR_PRUNE` | `20` | Min uses before a strategy can be pruned |
| `STRATEGY_PRUNE_SCORE_THRESHOLD` | `0.3` | Prune strategies scoring below this |
| `STRATEGY_EVOLUTION_TOP_K` | `3` | Number of top strategies to mutate |

### LMS & Auth

| Variable | Default | Description |
|----------|---------|-------------|
| `CANVAS_BASE_URL` | — | Canvas instance URL |
| `CANVAS_API_TOKEN` | — | Canvas API token |
| `MOODLE_BASE_URL` | — | Moodle instance URL |
| `MOODLE_API_TOKEN` | — | Moodle API token |
| `JWT_SECRET` | `change-this-in-production` | JWT signing secret |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `JWT_EXPIRATION_MINUTES` | `1440` | Token expiration (24 hours) |
| `LTI_ISSUER` | — | LTI 1.3 issuer URL |
| `LTI_CLIENT_ID` | — | LTI 1.3 client ID |

---

## Research Design

### Ablation Study

Docere v2 is designed for rigorous empirical evaluation via a three-arm ablation study:

```
┌─────────────────┐    ┌─────────────────────┐    ┌─────────────────────────┐
│     Control      │    │  Treatment: Memory   │    │  Treatment: Full        │
│                  │    │                      │    │                         │
│  Base LLM only   │    │  + Semantic memory    │    │  + Semantic memory      │
│  No memory       │    │  + Student profiles   │    │  + Student profiles     │
│  No strategies   │    │  + Context retrieval  │    │  + Context retrieval    │
│  No scoring      │    │  No strategies        │    │  + UCB1 strategies      │
│                  │    │  No scoring           │    │  + Process verification │
│                  │    │                       │    │  + Strategy evolution   │
└─────────────────┘    └─────────────────────┘    └─────────────────────────┘
```

### Metrics Collected

**Per interaction:**
- Helpfulness, clarity, engagement, understanding delta (scored)
- Strategy used, memory context size
- Time to student followup
- Student followup classification (understood / still_confused / new_question / off_topic)

**Per student:**
- Engagement level trajectory
- Concept mastery over time
- Grade correlation with tutoring usage

**Per strategy:**
- Total uses, average score, success rate
- Evolution lineage and generation performance
- Best/worst performing interaction contexts

### Novel Research Claims

1. **Process verification for tutoring:** Adapting process reward models (MATH-SHEPHERD) from math verification to open-ended educational dialogues
2. **Self-improvement from outcomes:** Teaching strategies that evolve based on measured educational effectiveness, not just user satisfaction

---

## Roadmap

- [x] Core tutoring pipeline (memory → strategy → LLM → response)
- [x] Three-source semantic memory with token budgeting
- [x] Process verification (LLM-as-judge + heuristic hybrid)
- [x] UCB1 strategy selection with 5 seed strategies
- [x] Strategy evolution (mutation + pruning)
- [x] Student profile builder with narrative summaries
- [x] Concept mastery tracking
- [x] Memory compression (CARTRIDGES-inspired)
- [x] LMS adapter interface (Canvas/Moodle)
- [x] LMS sync service (full + incremental)
- [x] Outcome tracker (grade → interaction linking)
- [x] Ablation study infrastructure (feature gating, deterministic assignment)
- [x] Database models and schema
- [x] Chat API endpoints
- [x] Frontend skeleton (React + TypeScript)
- [ ] JWT authentication
- [ ] Instructor dashboard & analytics API
- [ ] At-risk student alerts
- [ ] Canvas/Moodle adapter implementation
- [ ] Database migrations (Alembic)
- [ ] Background task scheduling (ARQ)
- [ ] Frontend ↔ API integration
- [ ] LTI 1.3 launch flow
- [ ] Rate limiting & production security
- [ ] Anonymized data export for research

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend framework | FastAPI (async) |
| Database | PostgreSQL 16 (SQLAlchemy 2.0 async) |
| Vector database | Qdrant |
| Cache / task queue | Redis 7 + ARQ |
| LLM | Anthropic Claude |
| Embeddings | Voyage AI (primary), OpenAI (fallback) |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS |
| Migrations | Alembic |
| Type checking | mypy (strict mode) |
| Linting | Ruff |
| Testing | pytest + pytest-asyncio |
| Containerization | Docker Compose |

---

## License

MIT
