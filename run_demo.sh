#!/usr/bin/env bash
# Start the Darwin demo: FastAPI backend (:8090) + Vite frontend (:5173).
# The frontend reads the committed run, so this works fully offline.
set -e
cd "$(dirname "$0")"
ROOT="$(pwd)"

echo "▸ Darwin demo — starting backend (:8090) and frontend (:5173)"

# backend
.venv/bin/python -m uvicorn server.api:app --port 8090 --host 0.0.0.0 &
API_PID=$!
echo "  backend pid $API_PID"

# frontend (dev server with API proxy)
( cd frontend && npm run dev -- --port 5173 ) &
WEB_PID=$!
echo "  frontend pid $WEB_PID"

trap "echo; echo 'stopping…'; kill $API_PID $WEB_PID 2>/dev/null" INT TERM
echo
echo "▸ open  http://localhost:5173"
echo "▸ API   http://localhost:8090/api/run"
echo "  (ctrl-C to stop)"
wait
