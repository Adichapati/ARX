# Release Verification

Use this flow to verify release artifacts before installation.

## 1) Download artifacts from a tagged release
Expected assets:
- `arx-vX.Y.Z-install.sh`
- `arx-vX.Y.Z-install.bat`
- `arx-vX.Y.Z-source.tar.gz`
- `SHA256SUMS`

## 2) Verify checksums
Linux/macOS:
```bash
sha256sum -c SHA256SUMS
```

If your system lacks `sha256sum`:
```bash
shasum -a 256 -c SHA256SUMS
```

Windows PowerShell (manual compare):
```powershell
Get-FileHash .\arx-vX.Y.Z-install.bat -Algorithm SHA256
Get-Content .\SHA256SUMS
```

## 3) Install from pinned tag artifact
Example (replace placeholders):
```bash
curl -fsSL https://raw.githubusercontent.com/ORG_OR_USER/REPO_NAME/vX.Y.Z/install.sh | bash
```

Never use mutable branch links for production installs.
