#!/bin/sh
# run.sh — entry point for the Docksmith sample app
#
# Demonstrates:
#   - ENV values injected from image config (GREETING, APP_VERSION)
#   - ENV override via: docksmith run -e GREETING=Hi myapp:latest
#   - WORKDIR set to /app (this script runs from /app)
#   - Visible output so the demo step clearly passes

echo "============================================"
echo " Docksmith Sample App v${APP_VERSION}"
echo "============================================"
echo ""
echo "${GREETING}, from inside the container!"
echo ""
echo "Container filesystem check:"
echo "  Working directory : $(pwd)"
echo "  Files in /app     : $(ls /app)"
echo ""
echo "Environment variables:"
echo "  GREETING    = ${GREETING}"
echo "  APP_VERSION = ${APP_VERSION}"
echo ""
echo "Isolation check: writing a test file inside the container..."
echo "this file should NOT appear on the host" > /tmp/isolation_test.txt
echo "  Written: /tmp/isolation_test.txt"
echo ""
echo "Done. Exit 0."
