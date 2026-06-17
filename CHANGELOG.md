# Changelog

All notable changes to this project are documented in this file.

## Unreleased

### Fixed
- **Linux/macOS one-liner install now works.** `curl -fsSL https://arxmc.studio/install.sh | bash` previously failed because `install.sh` assumed it was already running inside a cloned checkout (it needs `requirements.txt`, `scripts/`, etc.) and could not run its interactive prompts from a pipe. `install.sh` is now bootstrap-aware: when run outside a checkout it downloads the integrity-verified `arx-runtime.zip`, unpacks it into `$ARX_INSTALL_DIR` (default `~/ARX`), and re-executes the real installer with stdin reconnected to the terminal — mirroring the Windows `install.ps1` flow.
- Installer progress bars and rule lines no longer print mojibake: replaced byte-based `tr ' ' '<glyph>'` fills (which shred multibyte UTF-8 box-drawing characters) with a multibyte-safe `repeat` helper.
- Installer launcher generation: replaced unsafe here-string with array-join in install.ps1 to avoid parsing errors when the script is executed via irm | iex. (Windows batch launcher generation)
- PowerShell bootstrap invocation: website one-liner changed to download installer to a temp file and invoke it (uses `irm -OutFile`) so `param()` blocks and full PowerShell syntax work reliably when run from the web. (arx-website update)
- Java detection robustness: fixed $ErrorActionPreference handling around `java -version` calls so stderr output is captured correctly during Java version probing (prevents premature termination of the probe).
- Checksums manifest: normalized checksums.txt to reference base filenames (install.sh, install.ps1, arx-runtime.zip) so verification works as documented on the site. (arx-website/public/checksums.txt)

### Changed
- Reworked the Linux/macOS installer terminal experience: unified the default ("underground") ASCII wordmark with the `arx` CLI/TUI branding (Delta Corps "ARX"), added a cyan→green gradient logo reveal, an animated setup loader, colorized step progress, spinner check-marks, and a polished completion panel. All visuals honour `NO_COLOR`, dumb terminals, and non-UTF locales (ASCII fallbacks).
- Updated public installer artifacts on the website to include the latest install.sh, install.ps1, and arx-runtime.zip.

### Notes
- The temp-file PowerShell invocation preserves `param()` semantics and is the recommended safe pattern for web-launched PowerShell installers.
- If you want a formal release tag, create a semver tag (vMAJOR.MINOR.PATCH) and the CI workflow will generate a GitHub Release with artifacts automatically.
