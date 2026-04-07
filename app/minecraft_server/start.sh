#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f server.jar ]; then
  echo "server.jar not found. Run install.sh first." >&2
  exit 1
fi
if [ ! -f eula.txt ]; then
  echo "eula=true" > eula.txt
fi
exec java -Xms1G -Xmx2G -jar server.jar nogui
