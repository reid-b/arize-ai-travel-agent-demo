#!/bin/bash
# Double-click to start Sojourns by Arize AI.
# First run creates a private .venv and installs dependencies (takes a minute or two).
cd "$(dirname "$0")" || exit 1
mkdir -p logs

URL="http://localhost:8000"
VENV=".venv"
PATH="$PATH:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin"

pause_and_exit() { echo; read -n 1 -s -r -p "Press any key to close."; exit 1; }

# Already running? Just open it.
if curl -fs "$URL/health" >/dev/null 2>&1; then
  open "$URL"
  exit 0
fi

# Look for a Python 3.11+ in PATH and the usual install locations.
find_python() {
  local c
  for c in python3.13 python3.12 python3.11 python3 python \
    "$HOME"/anaconda3/bin/python "$HOME"/miniconda3/bin/python "$HOME"/miniforge3/bin/python \
    "$HOME"/opt/anaconda3/bin/python "$HOME"/opt/miniconda3/bin/python \
    "$HOME"/anaconda3/envs/*/bin/python "$HOME"/miniconda3/envs/*/bin/python \
    "$HOME"/miniforge3/envs/*/bin/python "$HOME"/opt/anaconda3/envs/*/bin/python \
    "$HOME"/.pyenv/versions/*/bin/python \
    "$HOME"/.local/share/uv/python/*/bin/python3 \
    /Library/Frameworks/Python.framework/Versions/*/bin/python3 \
    /opt/homebrew/bin/python3.1[1-3] /usr/local/bin/python3.1[1-3]; do
    if command -v "$c" >/dev/null 2>&1 && \
       "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
      echo "$c"; return 0
    fi
  done
  return 1
}

# First-time setup: build the virtual environment.
if [ ! -x "$VENV/bin/python" ]; then
  PY="$(find_python)"
  if [ -n "$PY" ]; then
    echo "Setting up with $PY ($("$PY" --version 2>&1)) ..."
    "$PY" -m venv "$VENV" || { echo "Couldn't create the virtual environment."; pause_and_exit; }
  else
    echo "No Python 3.11+ was found on this Mac."
    echo "Sojourns can install 'uv' (https://astral.sh/uv), which downloads Python 3.12"
    echo "into your user folder. No admin rights needed."
    read -r -p "Install uv and Python 3.12 now? [y/N] " ans
    case "$ans" in
      y|Y|yes|YES) ;;
      *) echo "Okay. Install Python 3.11+ from https://www.python.org/downloads/ and try again."; pause_and_exit ;;
    esac
    if ! command -v uv >/dev/null 2>&1; then
      curl -LsSf https://astral.sh/uv/install.sh | sh || { echo "uv install failed."; pause_and_exit; }
      PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    fi
    uv venv --seed --python 3.12 "$VENV" || { echo "Couldn't create the environment with uv."; pause_and_exit; }
  fi
fi

# Install dependencies once.
if [ ! -f "$VENV/.deps-installed" ]; then
  echo "Installing dependencies. This only happens the first time..."
  "$VENV/bin/python" -m pip install --upgrade pip >/dev/null 2>&1
  "$VENV/bin/python" -m pip install \
    "langgraph>=0.2,<0.3" "langchain>=0.3,<0.4" "langchain-community>=0.3,<0.4" \
    "langchain-openai>=0.2,<0.3" "ddgs>=9.0,<10" "python-dotenv>=1.0,<2" \
    "fastapi>=0.115,<0.116" "uvicorn>=0.32,<0.33" requests \
    || { echo "Dependency install failed. Check your internet connection."; pause_and_exit; }
  touch "$VENV/.deps-installed"
fi

if [ ! -f .env ]; then
  echo "No .env file found. Create one with: OPENAI_API_KEY=your_key"
  pause_and_exit
fi

# --- Arize Phoenix: tracing + local trace viewer ------------------------------
PHX_URL="http://localhost:6006"
PHX_VENV=".venv-phoenix"   # Phoenix gets its own environment so it can't clash with the app's pins
PHX_PID=""
cleanup() { [ -n "$PHX_PID" ] && kill "$PHX_PID" 2>/dev/null; }
trap cleanup EXIT

if [ ! -f "$VENV/.tracing-installed" ]; then
  echo "Installing tracing packages (first time only)..."
  if "$VENV/bin/python" -m pip install arize-phoenix-otel openinference-instrumentation-langchain; then
    touch "$VENV/.tracing-installed"
  else
    echo "Tracing packages failed to install. Continuing without tracing."
  fi
fi

if curl -fs "$PHX_URL" >/dev/null 2>&1; then
  echo "Phoenix is already running at $PHX_URL"
elif [ -f "$VENV/.tracing-installed" ]; then
  if [ ! -x "$PHX_VENV/bin/phoenix" ]; then
    echo "Setting up Arize Phoenix (first time only, this can take a few minutes)..."
    # --only-binary: use prebuilt packages only. Without it, pip can pick the newest
    # version of a dependency (e.g. pyarrow) that has no build for Intel Macs and then
    # fail trying to compile it. With it, pip falls back to an older version that works.
    if "$VENV/bin/python" -m venv "$PHX_VENV" \
       && "$PHX_VENV/bin/python" -m pip install --upgrade pip >/dev/null 2>&1 \
       && "$PHX_VENV/bin/python" -m pip install --only-binary :all: arize-phoenix >logs/phoenix-install.log 2>&1; then
      echo "Phoenix installed."
    else
      echo "Couldn't install Phoenix. Last lines of logs/phoenix-install.log:"
      tail -8 logs/phoenix-install.log 2>/dev/null
      echo "Continuing without the trace viewer."
    fi
  fi
  if [ -x "$PHX_VENV/bin/phoenix" ]; then
    "$PHX_VENV/bin/phoenix" serve >logs/phoenix.log 2>&1 &
    PHX_PID=$!
    echo "Starting Phoenix at $PHX_URL (log: logs/phoenix.log)..."
    # Wait for it, so the app can connect its tracing on startup (up to ~60 seconds).
    for _ in $(seq 1 60); do
      curl -fs "$PHX_URL" >/dev/null 2>&1 && { echo "Phoenix is up."; break; }
      kill -0 "$PHX_PID" 2>/dev/null || { echo "Phoenix exited early. Last lines of logs/phoenix.log:"; tail -8 logs/phoenix.log; PHX_PID=""; break; }
      sleep 1
    done
  fi
fi

# Open the browser once the server answers (up to ~30 seconds).
(
  for _ in $(seq 1 30); do
    if curl -fs "$URL/health" >/dev/null 2>&1; then open "$URL"; exit 0; fi
    sleep 1
  done
) &

export SOJOURNS_AUTOSHUTDOWN=1   # stop the server when the last browser tab closes

echo "Starting Sojourns at $URL  (traces: $PHX_URL)"
echo "It stops on its own when you close the browser tab. Ctrl+C also works."
"$VENV/bin/python" -m uvicorn api:app

echo
echo "[sojourns] Server stopped. Safe travels."

# Close this Terminal window (best effort; ignored if it isn't allowed).
TTY_NAME="$(tty 2>/dev/null)"
if [ -n "$TTY_NAME" ] && [ "$TTY_NAME" != "not a tty" ]; then
  ( sleep 1.5; osascript -e "tell application \"Terminal\"
    repeat with w in windows
      repeat with t in tabs of w
        if tty of t is \"$TTY_NAME\" then close w
      end repeat
    end repeat
  end tell" >/dev/null 2>&1 ) &
fi
