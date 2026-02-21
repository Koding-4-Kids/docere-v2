#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# ============================================================
#  DOCERE v2 || STOPPING
# ============================================================

echo ""
echo "============================================================"
echo "  DOCERE v2 || STOPPING"
echo "============================================================"
echo ""

# -- Frontend ---------------------------------------------------

echo "  [1/3] FRONTEND || STOPPING"
if [ -f "$DIR/.logs/frontend.pid" ]; then
  FRONTEND_PID=$(cat "$DIR/.logs/frontend.pid")
  if kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
    # Also kill any child node processes
    pkill -P "$FRONTEND_PID" 2>/dev/null || true
    echo "  ---- killed PID $FRONTEND_PID"
  else
    echo "  ---- not running (stale PID $FRONTEND_PID)"
  fi
  rm -f "$DIR/.logs/frontend.pid"
else
  echo "  ---- no PID file found, skipping"
fi
echo "  [1/3] FRONTEND || DONE"
echo ""

# -- Backend ----------------------------------------------------

echo "  [2/3] BACKEND || STOPPING"
if [ -f "$DIR/.logs/backend.pid" ]; then
  BACKEND_PID=$(cat "$DIR/.logs/backend.pid")
  if kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
    pkill -P "$BACKEND_PID" 2>/dev/null || true
    echo "  ---- killed PID $BACKEND_PID"
  else
    echo "  ---- not running (stale PID $BACKEND_PID)"
  fi
  rm -f "$DIR/.logs/backend.pid"
else
  echo "  ---- no PID file found, skipping"
fi

# Catch any remaining uvicorn processes for this project
REMAINING=$(pgrep -f "uvicorn docere.main:app" 2>/dev/null || true)
if [ -n "$REMAINING" ]; then
  echo "  ---- cleaning up remaining uvicorn processes: $REMAINING"
  echo "$REMAINING" | xargs kill 2>/dev/null || true
fi
echo "  [2/3] BACKEND || DONE"
echo ""

# -- Infrastructure (Docker) ------------------------------------

echo "  [3/3] INFRASTRUCTURE || STOPPING"
if [ "$1" = "--all" ]; then
  echo "  ---- stopping ALL containers (including moodle)"
  docker compose down
else
  echo "  ---- stopping core services (use --all to include moodle)"
  docker compose stop postgres redis qdrant
fi
echo "  [3/3] INFRASTRUCTURE || DONE"
echo ""

# -- Cleanup ----------------------------------------------------

rm -f "$DIR/.logs/backend.pid" "$DIR/.logs/frontend.pid"

echo "============================================================"
echo "  DOCERE v2 || STOPPED"
echo "============================================================"
echo ""
