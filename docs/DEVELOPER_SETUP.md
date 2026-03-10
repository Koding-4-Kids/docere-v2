# Developer Setup Guide

Step-by-step guide to get Docere v2 running locally. If you run into issues, check [Troubleshooting](#troubleshooting) at the bottom.

---

## Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Python | 3.12+ | `python3 --version` |
| Node.js | 20+ | `node --version` |
| Docker | 24+ | `docker --version` |
| Docker Compose | v2+ | `docker compose version` |
| Git | any | `git --version` |

**API Keys needed:**

| Key | Required | Where to get it |
|-----|----------|-----------------|
| `ANTHROPIC_API_KEY` | Yes | https://console.anthropic.com/settings/keys |
| `VOYAGE_API_KEY` | Yes (recommended) | https://dash.voyageai.com/api-keys |
| `OPENAI_API_KEY` | Alternative to Voyage | https://platform.openai.com/api-keys |

> **Important:** OpenAI free-tier keys have very low rate limits and will cause 429 errors on the embeddings endpoint. Use Voyage AI instead (free tier is more generous), or use a paid OpenAI key.

---

## Quick Start (one command)

If you just want everything running:

```bash
git clone https://github.com/Koding-4-Kids/docere-v2.git
cd docere-v2
cp .env.example .env
# Edit .env with your API keys (see step 3 below)
./start.sh
```

This starts Docker containers, runs migrations, and launches backend + frontend.

---

## Step-by-Step Setup

### 1. Clone the repo

```bash
git clone https://github.com/Koding-4-Kids/docere-v2.git
cd docere-v2
```

### 2. Create Python virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate    # macOS / Linux
# .venv\Scripts\activate     # Windows (PowerShell)
```

Install all dependencies:

```bash
pip install -e ".[dev]"
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in these **required** values:

```bash
# REQUIRED - Get from https://console.anthropic.com
ANTHROPIC_API_KEY=sk-ant-...

# REQUIRED (pick ONE) - Voyage is recommended (better free tier)
VOYAGE_API_KEY=pa-...
# OR
# OPENAI_API_KEY=sk-...
```

Everything else has working defaults for local development. Leave them as-is unless you have a specific reason to change them.

**Embedding provider choice:**

| Provider | Free tier | Rate limit | Recommendation |
|----------|-----------|------------|----------------|
| Voyage AI | 200M tokens/month | 300 RPM | Use this (default) |
| OpenAI | $5 credit (expires) | 3 RPM on free tier | Causes 429 errors on free tier |

If you set `VOYAGE_API_KEY`, the system uses Voyage automatically. If you only set `OPENAI_API_KEY`, it falls back to OpenAI.

### 4. Start infrastructure (Docker)

```bash
docker compose up -d postgres redis qdrant
```

Wait for containers to be healthy:

```bash
# Check status
docker compose ps
```

You should see all three containers as "healthy" or "running":
- **postgres** on `localhost:5432`
- **redis** on `localhost:6379`
- **qdrant** on `localhost:6333`

> **Optional:** To also start a local Moodle instance for LTI testing:
> ```bash
> docker compose up -d
> ```
> This adds Moodle on `localhost:8080` (admin/Admin123!). Takes a few minutes on first start.

### 5. Run database migrations

```bash
source .venv/bin/activate   # if not already active
alembic upgrade head
```

This creates all tables in PostgreSQL. You should see output like:

```
INFO  [alembic.runtime.migration] Running upgrade  -> abc123, initial schema
INFO  [alembic.runtime.migration] Running upgrade abc123 -> def456, add memory tables
...
```

### 6. Start the backend

```bash
uvicorn docere.main:app --reload --host 0.0.0.0 --port 8000
```

Verify it's running:

```bash
curl http://localhost:8000/health
# {"status":"ok","version":"0.1.0"}
```

API docs: http://localhost:8000/docs

### 7. Start the frontend

In a new terminal:

```bash
cd frontend
npm install       # first time only
npm run dev
```

Frontend: http://localhost:5173

---

## Running Tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

Tests run against mocks (no Docker needed). Current test count: 133 tests.

To run with coverage:

```bash
pytest tests/ -v --cov=src --cov-report=term-missing
```

---

## Project Structure (key files)

```
docere-v2/
├── src/docere/
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # All env var settings (Pydantic)
│   ├── dependencies.py          # DB sessions, auth, shared clients
│   ├── api/                     # API route handlers
│   │   ├── chat.py              # POST /conversations, POST /messages
│   │   ├── instructor.py        # Instructor dashboard + classroom agent
│   │   ├── students.py          # Student profiles (instructor view)
│   │   ├── memory.py            # Student self-view of memories
│   │   ├── analytics.py         # Research analytics + strategy data
│   │   ├── courses.py           # Course management + LMS sync
│   │   ├── lms.py               # LMS webhook receivers
│   │   ├── calendar.py          # Google Calendar integration
│   │   ├── gradebook.py         # Gradebook sync wizard
│   │   └── flashcards.py        # Spaced repetition cards
│   ├── core/
│   │   ├── agent.py             # TutoringAgent (original pipeline)
│   │   ├── classroom_agent.py   # ClassroomAgent (instructor queries)
│   │   ├── graphs/              # LangGraph agent graphs
│   │   │   ├── tutoring.py      # Tutoring graph (replaces agent.py)
│   │   │   ├── classroom.py     # Classroom graph
│   │   │   └── nodes/           # Individual graph nodes
│   │   ├── memory/              # Memory layer (retrieval + storage)
│   │   ├── improvement/         # Strategy archive + evolution
│   │   └── verification/        # Process verification scoring
│   ├── integrations/
│   │   ├── llm/
│   │   │   ├── client.py        # Claude/OpenAI chat client
│   │   │   └── embeddings.py    # Voyage/OpenAI embeddings
│   │   └── vector_db/
│   │       └── qdrant.py        # Qdrant vector store
│   ├── models/                  # SQLAlchemy ORM models
│   └── services/                # Business logic services
├── frontend/                    # React + TypeScript + Vite
├── tests/                       # pytest test suite
├── alembic/                     # Database migration scripts
├── docker-compose.yml           # Infrastructure containers
├── start.sh                     # Start everything
├── stop.sh                      # Stop everything
└── status.sh                    # Check what's running
```

---

## Common Workflows

### Adding a new API endpoint

1. Add the route handler in the appropriate `src/docere/api/*.py` file
2. Define Pydantic request/response models in the same file
3. Use `Depends(get_db)` for database, `Depends(require_instructor)` for auth
4. Run `ruff check src/` to lint

### Adding a database migration

```bash
# After modifying models in src/docere/models/
alembic revision --autogenerate -m "description of change"
alembic upgrade head
```

### Running the linter

```bash
.venv/bin/ruff check src/
.venv/bin/ruff check src/ --fix   # auto-fix safe issues
```

---

## Troubleshooting

### "429 Too Many Requests" on embeddings

```
httpx.HTTPStatusError: Client error '429 Too Many Requests'
for url 'https://api.openai.com/v1/embeddings'
```

**Cause:** OpenAI free-tier API keys have a 3 requests/minute rate limit. The memory system makes multiple embedding calls per conversation, which quickly exceeds this.

**Fix (choose one):**

1. **Switch to Voyage AI (recommended).** Sign up at https://dash.voyageai.com, get an API key, and set it in `.env`:
   ```bash
   VOYAGE_API_KEY=pa-your-key-here
   # Comment out or remove OPENAI_API_KEY
   ```

2. **Upgrade your OpenAI plan.** Paid OpenAI accounts have much higher rate limits (3000+ RPM).

3. **Use both keys.** If `VOYAGE_API_KEY` is set, the system uses Voyage for embeddings automatically. You can keep `OPENAI_API_KEY` set for other purposes without conflict.

### "ModuleNotFoundError: No module named 'docere'"

You need to install the package in development mode:

```bash
source .venv/bin/activate
pip install -e ".[dev]"
```

Make sure you're running commands from the repo root (`docere-v2/`), not a subdirectory.

### "ModuleNotFoundError: No module named 'langgraph'"

LangGraph was recently added as a dependency. Reinstall:

```bash
source .venv/bin/activate
pip install -e ".[dev]"
```

### Database connection errors

```
sqlalchemy.exc.OperationalError: could not connect to server
```

Docker containers might not be running:

```bash
docker compose ps                    # check status
docker compose up -d postgres redis qdrant   # start if needed
```

Wait a few seconds for postgres to be ready, then retry.

### Alembic migration errors

```
alembic.util.exc.CommandError: Can't locate revision identified by 'xxx'
```

Your local DB is out of sync with migrations. Reset and re-run:

```bash
# WARNING: This drops all data
docker compose exec postgres psql -U docere -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
alembic upgrade head
```

### "No embedding API key configured"

```
RuntimeError: No embedding API key configured (VOYAGE_API_KEY or OPENAI_API_KEY)
```

You need at least one embedding API key in `.env`. See step 3 above.

### Frontend won't start / blank page

```bash
cd frontend
rm -rf node_modules
npm install
npm run dev
```

If you see CORS errors in the browser console, make sure the backend is running on port 8000.

### Port already in use

```bash
# Find what's using the port
lsof -i :8000    # backend
lsof -i :5173    # frontend

# Kill it
kill -9 <PID>

# Or use the stop script
./stop.sh
```

### Docker containers won't start (port conflicts)

```bash
# Stop everything and clean up
./stop.sh --all
docker compose down -v    # removes volumes too (fresh DB)
docker compose up -d postgres redis qdrant
```

### "Circuit breaker open" errors

The system has circuit breakers that trip after 5 consecutive failures to an external service (Claude API, Voyage API, Qdrant). If you see these:

1. Check your API keys are valid
2. Check your internet connection
3. Wait 30 seconds (circuit breaker auto-recovers)
4. Restart the backend if the issue persists

---

## Environment Variable Reference

See the tables in the main [README.md](../README.md#configuration-reference) for the full list. The critical ones for local dev are:

| Variable | Required | Notes |
|----------|----------|-------|
| `ANTHROPIC_API_KEY` | Yes | Claude API for tutoring + scoring |
| `VOYAGE_API_KEY` | Yes* | Embeddings. *Or use `OPENAI_API_KEY` instead |
| `DATABASE_URL` | No | Defaults to local Docker postgres |
| `REDIS_URL` | No | Defaults to local Docker redis |
| `QDRANT_URL` | No | Defaults to local Docker qdrant |
| `JWT_SECRET` | No | Defaults to dev value (change in prod) |
