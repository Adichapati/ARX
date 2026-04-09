# ARX Development Safety Notes

This document is historical guidance from development-phase sandboxing.

Current production project identity:
- Product: ARX
- Runtime repository: `https://github.com/Adichapati/ARX`
- Website/docs repository: `https://github.com/Adichapati/arx-website`

Production operation guidance:
1. Use standard ARX install commands from README and website docs.
2. Validate checksums before production install.
3. Use dedicated runtime directories per environment.
4. Keep backups before in-place upgrades.

Note:
- Development-time local path restrictions in old notes were for staging safety and are not product guarantees.
