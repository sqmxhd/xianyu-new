# third_party

This directory stores upstream code used as protocol/reference dependencies.

## XianYuApis

- Upstream: https://github.com/cv-cat/XianYuApis
- Local path: `third_party/XianYuApis`
- Policy: keep upstream files unmodified.

Project-owned changes belong in `integrations/xianyu_core`, not inside the upstream directory.

Current integration note:

- `XianYuApis` uses top-level packages named `utils` and `message`; importing it directly from business code can cause package-name collisions.
- The adapter layer must isolate those imports and expose stable project-owned models/interfaces.
