#!/bin/bash
# End-to-end test without LinkedIn: real backend + real worker + real extension in a real Chromium, against fake_linkedin.py and
# a throwaway PostgreSQL. Touches no real data: its own network, database and volumes, all removed at the end.
#   automation/tests/e2e/run.sh [--keep] [--claude]
#     --keep    leave the containers running (noVNC on 127.0.0.1:16080, password e2e)
#     --claude  also run the real Claude routine on one stuck action (uses your Claude plan)
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
E2E="$ROOT/automation/tests/e2e"
# E2E_NAME: another set of names, when a container of an earlier run cannot be removed (a process stuck in the kernel)
NAME="${E2E_NAME:-careerops-e2e}"
NET=$NAME
PG=$NAME-pg
BACKEND=$NAME-backend
WORKER=$NAME-worker
FAKE=$NAME-fake
PDF=$NAME-gotenberg
export E2E_WORKER=$WORKER
# the worker's ports on the host: noVNC, then the two browser tools (E2E_PORT shifts them, for the same reason)
P="${E2E_PORT:-0}"
export E2E_MCP_LINKEDIN=$((18931 + P)) E2E_MCP_ATS=$((18932 + P))
PYTHON="${E2E_PYTHON:-python3}"
KEEP=""; CLAUDE=""
for a in "$@"; do [ "$a" = "--keep" ] && KEEP=1; [ "$a" = "--claude" ] && CLAUDE=1; done

cleanup() {
    [ -n "$KEEP" ] && return
    docker rm -f "$WORKER" "$FAKE" "$BACKEND" "$PG" "$PDF" >/dev/null 2>&1
    docker network rm "$NET" >/dev/null 2>&1
    docker volume rm $NAME-output >/dev/null 2>&1
}
trap cleanup EXIT
docker rm -f "$WORKER" "$FAKE" "$BACKEND" "$PG" "$PDF" >/dev/null 2>&1
docker network rm "$NET" >/dev/null 2>&1
docker volume rm $NAME-output >/dev/null 2>&1

set -e
echo "== images"
docker build -q -t careerops-automation:e2e --build-context extension="$ROOT/extension" "$ROOT/automation" >/dev/null
docker build -q -t careerops-backend:e2e --build-context config="$ROOT/config" --build-context extension="$ROOT/extension" "$ROOT/backend" >/dev/null

echo "== stack"
docker network create "$NET" >/dev/null
docker run -d --name "$PG" --network "$NET" --memory 256m -e POSTGRES_PASSWORD=e2e -p 127.0.0.1:15432:5432 postgres:15-alpine >/dev/null
until docker exec "$PG" pg_isready -U postgres >/dev/null 2>&1; do sleep 1; done
sleep 2
docker exec -i "$PG" psql -q -U postgres -d postgres < "$ROOT/backend/tests/schema_base.sql" >/dev/null

# Any hour, no gap between writes: everything else is the real configuration
CONFIG="$(mktemp -d)"
cp -r "$ROOT/config/." "$CONFIG/"
# settings.json is local (gitignored) and config is mounted read-only: without it the backend tries to create it and fails
[ -f "$CONFIG/settings.json" ] || cp "$ROOT/config/settings.example.json" "$CONFIG/settings.json"
"$PYTHON" - "$CONFIG/automation.yml" <<'EOF'
import re, sys
p = sys.argv[1]; t = open(p, encoding="utf-8").read()
t = re.sub(r"window: \{start_hour: \d+, end_hour: \d+\}", "window: {start_hour: 0, end_hour: 24}", t)
t = re.sub(r"(reply_scan_hours|inbox_scan_hours): \[[\d, ]*\]", r"\1: []", t)   # the scenarios start these themselves
t = t.replace("write_gap_minutes: [5, 20]", "write_gap_minutes: [0, 0]")
t = t.replace("search_hours: [9, 15]", "search_hours: []").replace("check_hours: [7, 19]", "check_hours: []").replace("feed_scan_hours: [10, 16]", "feed_scan_hours: []").replace("follow_scan_hours: [11]", "follow_scan_hours: []")
t = t.replace("external_apply: false", "external_apply: true")
open(p, "w", encoding="utf-8").write(t)
EOF
docker run -d --name "$FAKE" --network "$NET" --memory 128m -p 127.0.0.1:18443:8443 -v "$E2E:/e2e:ro" careerops-automation:e2e python /e2e/fake_linkedin.py 8443 >/dev/null
# the CV and cover letter PDFs of the applications
docker run -d --name "$PDF" --network "$NET" --memory 400m gotenberg/gotenberg:8 >/dev/null
docker run -d --name "$BACKEND" --network "$NET" --memory 600m -p 127.0.0.1:18005:8000 -v "$CONFIG:/app/config:ro" -v $NAME-output:/app/output \
    -e SUPABASE_DB_HOST="$PG" -e SUPABASE_DB_PASSWORD=e2e -e CAREEROPS_APPROVER_TOKEN=e2e-approver -e CAREEROPS_WORKER_TOKEN=e2e-worker \
    -e AI_PROVIDER=openai -e AI_API_KEY=x -e AI_MODEL=fake -e AI_BASE_URL="http://$FAKE:8080/v1" \
    -e GOTENBERG_URL="http://$PDF:3000" -e AUTOMATION_ALLOW_FINAL_SUBMIT=true careerops-backend:e2e >/dev/null
until curl -sf http://127.0.0.1:18005/health >/dev/null; do sleep 1; done

docker run -d --init --name "$WORKER" --network "$NET" --memory 2500m --shm-size 1g \
    -p 127.0.0.1:$((16080 + P)):6080 -p 127.0.0.1:$E2E_MCP_LINKEDIN:8931 -p 127.0.0.1:$E2E_MCP_ATS:8932 \
    -v $NAME-output:/app/output \
    -e CAREEROPS_API_BASE="http://$BACKEND:8000/api" -e CAREEROPS_WORKER_TOKEN=e2e-worker -e VNC_PASSWORD=e2e \
    -e BROWSER_IGNORE_HTTPS_ERRORS=1 -e BROWSER_MODE="${BROWSER_MODE:-xvfb}" \
    -e "BROWSER_EXTRA_ARGS=--host-resolver-rules=MAP www.linkedin.com $FAKE:8443,MAP fake-ats.example $FAKE:8443|--ignore-certificate-errors" \
    careerops-automation:e2e >/dev/null

echo "== scenarios"
set +e
E2E_CLAUDE="$CLAUDE" E2E_PG=127.0.0.1:15432 "$PYTHON" "$E2E/scenarios.py"
code=$?
if [ $code -ne 0 ]; then
    echo "== worker log"; docker logs --tail 40 "$WORKER" 2>&1
    echo "== backend log"; docker logs --tail 25 "$BACKEND" 2>&1
fi
docker stats --no-stream --format 'memory: {{.Name}} {{.MemUsage}}' "$WORKER" "$BACKEND"
echo "RESULT exit=$code"
exit $code
