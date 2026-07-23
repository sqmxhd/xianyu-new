# fingerprint-chromium

Managed upstream browser binary directory.

- Upstream: https://github.com/adryfish/fingerprint-chromium
- License: BSD-3-Clause
- `releases/` contains versioned, locally installed Linux binaries.
- `downloads/` contains temporary upload/download artifacts.
- Project-owned integration code belongs under `apps/api/xianyu_admin_api`.

Binary releases are installed by the system settings page and should not be
modified in place. Account cookies and browser profiles are stored under
`data/browser-profiles`, never in this directory.
