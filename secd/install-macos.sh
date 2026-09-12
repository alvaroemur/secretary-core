#!/bin/sh
set -eu

if [ "$(uname -s)" != "Darwin" ]; then
  echo "This installer supports macOS only." >&2
  exit 1
fi

: "${SECRETARY_INSTANCE:?Set SECRETARY_INSTANCE to your instance directory.}"

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
NODE_BIN=$(command -v node)
INSTANCE=$(CDPATH= cd -- "$SECRETARY_INSTANCE" && pwd)
LABEL=${SECD_LAUNCHD_LABEL:-org.secretary.secd}
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$INSTANCE/.secd/logs"

escape_xml() {
  printf '%s' "$1" | sed \
    -e 's/&/\&amp;/g' \
    -e 's/</\&lt;/g' \
    -e 's/>/\&gt;/g' \
    -e 's/"/\&quot;/g'
}

mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$(escape_xml "$LABEL")</string>
  <key>ProgramArguments</key>
  <array>
    <string>$(escape_xml "$NODE_BIN")</string>
    <string>$(escape_xml "$SCRIPT_DIR/server.mjs")</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>SECRETARY_INSTANCE</key><string>$(escape_xml "$INSTANCE")</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$(escape_xml "$LOG_DIR/stdout.log")</string>
  <key>StandardErrorPath</key><string>$(escape_xml "$LOG_DIR/stderr.log")</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl kickstart -k "gui/$(id -u)/$LABEL"
echo "Installed $LABEL. Check http://127.0.0.1:${SECD_PORT:-8910}/health"
