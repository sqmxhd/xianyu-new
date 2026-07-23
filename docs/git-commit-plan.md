# Git commit plan

Do not commit dependencies, build output, local env files, SQLite data, or caches.

Run before committing:

```bash
npm run git:audit
git status --short --ignored
```

## Recommended commit groups

1. Backend core/admin API
   - `apps/api/`
   - `integrations/xianyu_core/`
   - `tools/internal_healthcheck.py`

2. Frontend Ant admin
   - `apps/admin/src/`
   - `apps/admin/package.json`
   - `apps/admin/package-lock.json`

3. Workspace scripts and env templates
   - `package.json`
   - `package-lock.json`
   - `.env.example`
   - `.gitignore`

4. Deployment/docs
   - `docs/`
   - `deploy/`
   - `tools/update_xianyu_apis.py`
   - `tools/git_audit.py`

5. Upstream source
   - `third_party/XianYuApis`
   - `third_party/XianYuApis.vendor.json`

## Upstream policy

`third_party/XianYuApis` is vendored directly into the parent repository. The
source commit is recorded in `third_party/XianYuApis.vendor.json`. Official
upstream refreshes and project compatibility changes remain ordinary parent
working-tree changes and are committed on `main` together.

Business integration code remains under `integrations/xianyu_core`.
