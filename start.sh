#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# ============================================================
#  DOCERE v2 || STARTING
# ============================================================

echo ""
echo "============================================================"
echo "  DOCERE v2 || STARTING"
echo "============================================================"
echo ""

# -- Check dependencies ----------------------------------------

for cmd in docker npm python3; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "  [ERROR] Missing required command: $cmd"
    exit 1
  fi
done

# -- Infrastructure (Docker) -----------------------------------

echo "  [1/4] INFRASTRUCTURE || STARTING"
echo "  ---- spinning up postgres, redis, qdrant ..."

docker compose up -d postgres redis qdrant

# Start Moodle if not already running
if docker compose ps moodle 2>/dev/null | grep -q "running"; then
  echo "  ---- moodle already running"
else
  echo "  ---- starting moodle + mariadb ..."
  docker compose up -d moodle-mariadb moodle
fi

echo "  ---- waiting for containers to be healthy ..."
sleep 3

# Quick health checks
RETRIES=0
MAX_RETRIES=30
until docker compose exec -T postgres pg_isready -U docere &>/dev/null; do
  RETRIES=$((RETRIES + 1))
  if [ "$RETRIES" -ge "$MAX_RETRIES" ]; then
    echo "  [ERROR] postgres did not become ready in time"
    exit 1
  fi
  sleep 1
done
echo "  ---- postgres    || READY"

RETRIES=0
until docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; do
  RETRIES=$((RETRIES + 1))
  if [ "$RETRIES" -ge "$MAX_RETRIES" ]; then
    echo "  [ERROR] redis did not become ready in time"
    exit 1
  fi
  sleep 1
done
echo "  ---- redis       || READY"

RETRIES=0
until curl -sf http://localhost:6333/healthz &>/dev/null; do
  RETRIES=$((RETRIES + 1))
  if [ "$RETRIES" -ge "$MAX_RETRIES" ]; then
    echo "  [ERROR] qdrant did not become ready in time"
    exit 1
  fi
  sleep 1
done
echo "  ---- qdrant      || READY"

echo "  [1/4] INFRASTRUCTURE || DONE"
echo ""

# -- Database migrations ----------------------------------------

echo "  [2/4] MIGRATIONS || RUNNING"
source "$DIR/.venv/bin/activate"
if [ -f "$DIR/alembic.ini" ]; then
  python3 -m alembic upgrade head 2>&1 | while read -r line; do
    echo "  ---- $line"
  done
  echo "  [2/4] MIGRATIONS || DONE"
else
  echo "  ---- no alembic.ini found, skipping"
fi
echo ""

# -- Backend (FastAPI) ------------------------------------------

echo "  [3/4] BACKEND || STARTING"
echo "  ---- uvicorn on http://localhost:8000"

mkdir -p "$DIR/.logs"

source "$DIR/.venv/bin/activate"

uvicorn docere.main:app --reload --host 0.0.0.0 --port 8000 \
  > "$DIR/.logs/backend.log" 2>&1 &
BACKEND_PID=$!

echo "$BACKEND_PID" > "$DIR/.logs/backend.pid"
echo "  ---- PID $BACKEND_PID"
echo "  [3/4] BACKEND || DONE"
echo ""

# -- Frontend (Vite) --------------------------------------------

echo "  [4/4] FRONTEND || STARTING"
echo "  ---- vite on http://localhost:5173"

cd "$DIR/frontend"
npm run dev > "$DIR/.logs/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > "$DIR/.logs/frontend.pid"
cd "$DIR"

echo "  ---- PID $FRONTEND_PID"
echo "  [4/4] FRONTEND || DONE"
echo ""

# -- Summary ----------------------------------------------------

echo "============================================================"
echo "  DOCERE v2 || RUNNING"
echo "============================================================"
echo ""
echo "  Backend   || http://localhost:8000  (PID $BACKEND_PID)"
echo "  Frontend  || http://localhost:5173  (PID $FRONTEND_PID)"
echo "  Postgres  || localhost:5432"
echo "  Redis     || localhost:6379"
echo "  Qdrant    || localhost:6333"
echo ""
echo "  Logs      || .logs/backend.log"
echo "            || .logs/frontend.log"
echo ""
echo "  Stop all  || ./stop.sh"
echo "============================================================"
echo ""
