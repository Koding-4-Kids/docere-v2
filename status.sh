#!/usr/bin/env bash

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# ============================================================
#  DOCERE v2 || STATUS
# ============================================================

echo ""
echo "============================================================"
echo "  DOCERE v2 || STATUS"
echo "============================================================"
echo ""

# -- Backend ----------------------------------------------------

if [ -f "$DIR/.logs/backend.pid" ]; then
  BACKEND_PID=$(cat "$DIR/.logs/backend.pid")
  if kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "  Backend   || RUNNING  (PID $BACKEND_PID)"
  else
    echo "  Backend   || DOWN     (stale PID $BACKEND_PID)"
  fi
else
  echo "  Backend   || DOWN     (no PID file)"
fi

# -- Frontend ---------------------------------------------------

if [ -f "$DIR/.logs/frontend.pid" ]; then
  FRONTEND_PID=$(cat "$DIR/.logs/frontend.pid")
  if kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "  Frontend  || RUNNING  (PID $FRONTEND_PID)"
  else
    echo "  Frontend  || DOWN     (stale PID $FRONTEND_PID)"
  fi
else
  echo "  Frontend  || DOWN     (no PID file)"
fi

# -- Docker containers ------------------------------------------

echo ""
echo "  -- CONTAINERS ----------------------------------------"
echo ""

for svc in postgres redis qdrant; do
  STATE=$(docker compose ps --format '{{.State}}' "$svc" 2>/dev/null || echo "not found")
  HEALTH=$(docker compose ps --format '{{.Health}}' "$svc" 2>/dev/null || echo "")
  if [ -n "$HEALTH" ] && [ "$HEALTH" != "" ]; then
    printf "  %-10s || %-10s (%s)\n" "$svc" "$STATE" "$HEALTH"
  else
    printf "  %-10s || %s\n" "$svc" "$STATE"
  fi
done

# Check optional moodle
MOODLE_STATE=$(docker compose ps --format '{{.State}}' moodle 2>/dev/null || echo "")
if [ -n "$MOODLE_STATE" ] && [ "$MOODLE_STATE" != "" ]; then
  printf "  %-10s || %s\n" "moodle" "$MOODLE_STATE"
fi

echo ""

# -- Quick health pings -----------------------------------------

echo "  -- HEALTH CHECKS ------------------------------------"
echo ""

if curl -sf http://localhost:8000/health &>/dev/null; then
  echo "  API /health     || OK"
else
  echo "  API /health     || UNREACHABLE"
fi

if curl -sf http://localhost:5173 &>/dev/null; then
  echo "  Vite dev server || OK"
else
  echo "  Vite dev server || UNREACHABLE"
fi

if curl -sf http://localhost:6333/healthz &>/dev/null; then
  echo "  Qdrant          || OK"
else
  echo "  Qdrant          || UNREACHABLE"
fi

echo ""
echo "============================================================"
echo ""
