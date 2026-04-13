# ARX Release Verification

Use this guide to verify installer artifacts before running them.

## Official artifact endpoints

- `https://arxmc.studio/install.sh`
- `https://arxmc.studio/install.ps1`
- `https://arxmc.studio/arx-runtime.zip` (lean bootstrap runtime bundle)
- `https://arxmc.studio/checksums.txt`

GitHub fallback:

- `https://github.com/Adichapati/ARX/releases`

---

## 1) Download checksum manifest

Linux/macOS:

```bash
curl -fsSL https://arxmc.studio/checksums.txt -o checksums.txt
```

Windows PowerShell:

```powershell
Invoke-WebRequest https://arxmc.studio/checksums.txt -OutFile checksums.txt
```

---

## 2) Download artifact(s)

Examples:

```bash
curl -fsSL https://arxmc.studio/install.sh -o install.sh
curl -fsSL https://arxmc.studio/install.ps1 -o install.ps1
curl -fsSL https://arxmc.studio/arx-runtime.zip -o arx-runtime.zip
```

---

## 3) Verify SHA-256 checksums

Linux:

```bash
sha256sum -c checksums.txt
```

macOS (if `sha256sum` is unavailable):

```bash
shasum -a 256 install.sh install.ps1 arx-runtime.zip
cat checksums.txt
```

Windows PowerShell (manual compare):

```powershell
Get-FileHash .\install.ps1 -Algorithm SHA256
Get-FileHash .\arx-runtime.zip -Algorithm SHA256
Get-Content .\checksums.txt
```

Expected result:
- Hash values must match exactly.
- If any file mismatches, delete it and re-download.

---

## 4) Install only after verification

Linux/macOS recommended stable path:

```bash
git clone https://github.com/Adichapati/ARX.git
cd ARX
./install.sh
```

Windows bootstrap path:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://arxmc.studio/install.ps1 | iex"
```

---

## Verification failure policy

If checksum verification fails:

1. Do not run the file.
2. Re-download from the official endpoint or GitHub release.
3. Re-verify hashes.
4. If mismatch persists, report privately via `security@arxmc.studio`.
