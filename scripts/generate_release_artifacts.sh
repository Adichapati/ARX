#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

VERSION="${1:-dev}"
mkdir -p dist
rm -f dist/arx-runtime.zip

cp install.sh "dist/arx-${VERSION}-install.sh"
cp install.bat "dist/arx-${VERSION}-install.bat"
cp install.ps1 "dist/arx-${VERSION}-install.ps1"
python3 scripts/build_runtime_bundle.py --output "dist/arx-runtime.zip"

git archive --format=tar.gz --prefix="arx-${VERSION}/" -o "dist/arx-${VERSION}-source.tar.gz" HEAD

(
  cd dist
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum * > SHA256SUMS
  else
    shasum -a 256 * > SHA256SUMS
  fi
)

echo "Artifacts written to: $ROOT_DIR/dist"
echo "- arx-${VERSION}-install.sh"
echo "- arx-${VERSION}-install.bat"
echo "- arx-${VERSION}-install.ps1"
echo "- arx-runtime.zip"
echo "- arx-${VERSION}-source.tar.gz"
echo "- SHA256SUMS"
