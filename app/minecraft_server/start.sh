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
if command -v java21 >/dev/null 2>&1; then
  exec java21 -Xms1G -Xmx2G -jar server.jar nogui
fi
if command -v /usr/lib/jvm/java-21-openjdk-amd64/bin/java >/dev/null 2>&1; then
  exec /usr/lib/jvm/java-21-openjdk-amd64/bin/java -Xms1G -Xmx2G -jar server.jar nogui
fi
exec java -Xms1G -Xmx2G -jar server.jar nogui
