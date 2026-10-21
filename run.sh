#!/usr/bin/env bash
# Doodle Theater: set up and start the server with one command (macOS / Linux).
#
#   ./run.sh            install on first run, then start on port 8787
#   ./run.sh --setup    install only, don't start
#   ./run.sh --help     show this
#
# Another port: DT_PORT=8788 ./run.sh
set -euo pipefail

case "${1:-}" in
  -h|--help) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
esac

root="$(cd "$(dirname "$0")" && pwd)"
server="$root/server"
venv="$server/.venv"
py="$venv/bin/python"
export DT_PORT="${DT_PORT:-8787}"   # the QR code on the TV uses it too

if [ ! -x "$py" ]; then
  echo "Creating server/.venv (needs Python 3.10+)..."
  python3 -m venv "$venv"
fi

# Install once; delete server/.venv/.installed to force a reinstall.
if [ "${1:-}" = "--setup" ] || [ ! -f "$venv/.installed" ]; then
  echo "Installing the server and rig packages (a few minutes the first time)..."
  "$py" -m pip install --quiet --upgrade pip
  "$py" -m pip install --quiet fastapi uvicorn python-multipart python-dotenv segno pillow numpy \
      opencv-python-headless boto3 strands-agents pytest httpx
  "$py" -m pip install --quiet -e "$root/rig"
  touch "$venv/.installed"
fi
if [ "${1:-}" = "--setup" ]; then echo "Setup done. Start with ./run.sh"; exit 0; fi

cd "$server"
ip="$("$py" -c 'from doodle_theater.config import lan_ip; print(lan_ip())')"
cat <<EOF

Doodle Theater server on port $DT_PORT
  TV on this Wi-Fi (Fire TV / Android TV):  http://$ip:$DT_PORT   <- 'Set server address' on the TV
  Android TV emulator on this laptop:       http://10.0.2.2:$DT_PORT   (no setup needed on port 8787)
  Phone: scan the QR code on the TV's 'Add a star' screen.
  Check it in a browser:                    http://localhost:$DT_PORT/api/cast
Press Ctrl+C to stop.

EOF
exec "$py" -m uvicorn doodle_theater.app:app --host 0.0.0.0 --port "$DT_PORT"
