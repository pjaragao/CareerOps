#!/bin/bash

echo "Starting X virtual framebuffer (Xvfb)..."
Xvfb :99 -screen 0 1280x1024x24 -ac +extension GLX +render -noreset &
sleep 2

echo "Starting window manager (fluxbox)..."
fluxbox -display :99 &
sleep 1

echo "Starting x11vnc server..."
x11vnc -display :99 -forever -shared -nopw -listen localhost -xkb > /app/x11vnc.log 2>&1 &
sleep 1

echo "Starting noVNC web server on port 6080..."
websockify --web /usr/share/novnc 0.0.0.0:6080 127.0.0.1:5900 &

echo "Starting Flask web application (Profile Optimizer + Jobs)..."
exec python web.py
