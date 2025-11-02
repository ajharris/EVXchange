#!/bin/bash


# Usage: ./start_app.sh [dev|prod]
# Default is dev (hot reload, separate servers)

set -e

MODE=${1:-dev}

# 1. Install/build frontend
cd frontend
npm install 2>&1 | tee ../frontend_install.log
if [ "$MODE" = "prod" ]; then
  npm run build 2>&1 | tee ../frontend_build.log
fi
cd ..

# 2. Set up Python venv and install backend deps
if [ ! -d "backend/venv" ]; then
  python3.12 -m venv backend/venv 2>&1 | tee backend_venv.log
fi
source backend/venv/bin/activate
pip install -r backend/requirements.txt 2>&1 | tee backend_pip_install.log

# 3. Run Alembic migrations
if [ -d "backend/migrations" ]; then
  cd backend
  export PYTHONPATH="$(cd .. && pwd)"
  ALEMBIC_CONFIG="alembic.ini"
  if [ ! -f "$ALEMBIC_CONFIG" ] && [ -f "migrations/alembic.ini" ]; then
    ALEMBIC_CONFIG="migrations/alembic.ini"
  fi
  if [ -f "venv/bin/alembic" ]; then
    venv/bin/alembic --config $ALEMBIC_CONFIG upgrade head 2>&1 | tee ../alembic.log
  elif command -v alembic &> /dev/null; then
    alembic --config $ALEMBIC_CONFIG upgrade head 2>&1 | tee ../alembic.log
  fi
  cd ..
fi

# 4. Start servers
if [ "$MODE" = "prod" ]; then
  # Production: serve built React from Flask only
  cd backend
  export PYTHONPATH="$(cd .. && pwd)"
  export FLASK_APP=run.py
  flask run 2>&1 | tee ../log
else
  # Development: start Flask, React, and optionally Mobile dev server in parallel
  cd backend
  export PYTHONPATH="$(cd .. && pwd)"
  export FLASK_APP=run.py
  export FLASK_ENV=development
  flask run 2>&1 | tee ../log &
  BACKEND_PID=$!
  cd ../frontend
  npm start 2>&1 | tee ../frontend.log &
  FRONTEND_PID=$!
  cd ..

  # Optionally start mobile app (Expo)
  if [ -d "mobile" ] && [ -f "mobile/package.json" ]; then
    echo "\n🚀 Starting mobile app (Expo)..."
    # Try to open in a new terminal tab if possible, else run in background
    if command -v gnome-terminal &> /dev/null; then
      gnome-terminal -- bash -c "cd mobile && npm install && npm start"
    elif command -v x-terminal-emulator &> /dev/null; then
      x-terminal-emulator -e "bash -c 'cd mobile && npm install && npm start'"
    else
      (cd mobile && npm install && npm start) &
    fi
  fi

  trap 'kill $BACKEND_PID $FRONTEND_PID' SIGINT SIGTERM
  wait $BACKEND_PID $FRONTEND_PID
fi
