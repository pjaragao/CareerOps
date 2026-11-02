#!/bin/sh
# Screen, remote view and browser tools for the worker. CDP stays inside this container; the browser tools (for the Claude
# routine) and noVNC are published on the host's loopback only (docker-compose.yml). No VNC password, no remote view.
set -e

export DISPLAY=:99
rm -f /tmp/.X99-lock /tmp/.X11-unix/X99   # left by a container that was killed: Xvfb would refuse to start
Xvfb :99 -screen 0 1400x1000x24 -nolisten tcp &
sleep 1
fluxbox >/dev/null 2>&1 &

if [ -n "$VNC_PASSWORD" ]; then
    x11vnc -display :99 -forever -shared -rfbport 5900 -localhost -quiet -passwd "$VNC_PASSWORD" >/dev/null 2>&1 &
    websockify --web /usr/share/novnc 6080 localhost:5900 >/dev/null 2>&1 &
else
    echo "VNC_PASSWORD not set: noVNC is off, you cannot sign in through it"
fi

mkdir -p /data/profiles /data/run
cd /data/run

# The browser tools the Claude routine uses, one per browser. They only hold the CV and cover letter of the action (cwd).
# No --allowed-origins on the LinkedIn one: it applies to the whole browser and would cut the extension off from the backend,
# and it is no security boundary anyway. What holds the agent to its target: the tool list, and run.py auditing every navigation.
# The company-site one may refuse LinkedIn outright, on top of having no session there.
playwright-mcp --cdp-endpoint http://127.0.0.1:9222 --host 0.0.0.0 --port 8931 --allowed-hosts '*' >/dev/null 2>&1 &
playwright-mcp --cdp-endpoint http://127.0.0.1:9223 --host 0.0.0.0 --port 8932 --allowed-hosts '*' \
    --blocked-origins 'https://www.linkedin.com;https://linkedin.com' >/dev/null 2>&1 &

cd /app
exec python -m worker.main
