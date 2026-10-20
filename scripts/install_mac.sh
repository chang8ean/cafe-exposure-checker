#!/bin/bash
# 매일 07:30 판정 · 13:30 이어서(--resume) 를 launchd 에 등록한다.
# 사용:  bash scripts/install_mac.sh        해제:  bash scripts/install_mac.sh --uninstall
set -e
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY="$REPO/.venv/bin/python"
AGENTS="$HOME/Library/LaunchAgents"
mkdir -p "$AGENTS" "$REPO/logs"

for name in morning afternoon; do
  label="com.cafe-exposure-checker.$name"
  plist="$AGENTS/$label.plist"
  launchctl unload "$plist" 2>/dev/null || true
  rm -f "$plist"
  [ "$1" = "--uninstall" ] && { echo "해제: $label"; continue; }
  if [ "$name" = morning ]; then H=7; M=30; ARG=""; else H=13; M=30; ARG="<string>--resume</string>"; fi
  cat > "$plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key><array>
    <string>$PY</string><string>$REPO/run.py</string>$ARG
  </array>
  <key>WorkingDirectory</key><string>$REPO</string>
  <key>StartCalendarInterval</key><dict>
    <key>Hour</key><integer>$H</integer><key>Minute</key><integer>$M</integer>
  </dict>
  <key>StandardOutPath</key><string>$REPO/logs/$name.log</string>
  <key>StandardErrorPath</key><string>$REPO/logs/$name.log</string>
  <key>EnvironmentVariables</key><dict><key>PYTHONIOENCODING</key><string>utf-8</string></dict>
</dict></plist>
PLIST
  launchctl load "$plist"
  echo "등록: $label ($(printf %02d:%02d $H $M))"
done
