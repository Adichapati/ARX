# Changelog

All notable changes to this project are documented in this file.

## Unreleased

### Fixed
- Installer launcher generation: replaced unsafe here-string with array-join in install.ps1 to avoid parsing errors when the script is executed via irm | iex. (Windows batch launcher generation)
- PowerShell bootstrap invocation: website one-liner changed to download installer to a temp file and invoke it (uses `irm -OutFile`) so `param()` blocks and full PowerShell syntax work reliably when run from the web. (arx-website update)
- Java detection robustness: fixed $ErrorActionPreference handling around `java -version` calls so stderr output is captured correctly during Java version probing (prevents premature termination of the probe).
- Checksums manifest: normalized checksums.txt to reference base filenames (install.sh, install.ps1, arx-runtime.zip) so verification works as documented on the site. (arx-website/public/checksums.txt)

### Changed
- Updated public installer artifacts on the website to include the latest install.sh, install.ps1, and arx-runtime.zip.

### Notes
- The temp-file PowerShell invocation preserves `param()` semantics and is the recommended safe pattern for web-launched PowerShell installers.
- If you want a formal release tag, create a semver tag (vMAJOR.MINOR.PATCH) and the CI workflow will generate a GitHub Release with artifacts automatically.
