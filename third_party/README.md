# third_party

This directory stores upstream code used as protocol/reference dependencies.

## XianYuApis

- Official upstream: https://github.com/cv-cat/XianYuApis
- Local path: `third_party/XianYuApis`
- Policy: vendored source tracked directly by the parent repository. Upstream
  refreshes and project compatibility changes are reviewed and committed on the
  parent `main` branch together.
- Source metadata: `third_party/XianYuApis.vendor.json`

Business integration changes belong in `integrations/xianyu_core`. The vendor
directory only contains upstream snapshots and narrowly scoped compatibility
files declared in the source metadata.

Current integration note:

- `XianYuApis` uses top-level packages named `utils` and `message`; importing it directly from business code can cause package-name collisions.
- The adapter layer must isolate those imports and expose stable project-owned models/interfaces.
- `utils/package.json` is a project compatibility override that keeps the
  upstream Node utilities in CommonJS mode.

```bash
npm run upstream:status
npm run upstream:update
```

The update command only changes the parent working tree. It does not create an
independent commit; review the diff and commit it with the rest of `main`.
