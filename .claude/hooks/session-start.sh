#!/bin/bash
set -euo pipefail

# Only run in remote (Claude Code on the web) environments
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# Install Python dependencies
pip install -r "$CLAUDE_PROJECT_DIR/requirements.txt"

# Start Flask server in the background (kill any previous instance first)
pkill -f "python $CLAUDE_PROJECT_DIR/app.py" 2>/dev/null || true
nohup python "$CLAUDE_PROJECT_DIR/app.py" > /tmp/flask-server.log 2>&1 &
