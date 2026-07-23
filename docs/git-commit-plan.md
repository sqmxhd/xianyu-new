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

5. Upstream source decision
   - `third_party/XianYuApis`

## Upstream decision

`third_party/XianYuApis` is currently a nested git checkout. Before committing it
to the parent repository, choose one:

- submodule: keeps upstream history clean and updates explicit;
- subtree/vendor copy: easier clone, but upstream history is folded into parent;
- do not commit upstream: require a bootstrap script to clone it during setup.

The current adapter is designed so business code does not modify upstream files.
