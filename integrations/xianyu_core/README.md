# xianyu_core adapter

This package is the project-owned adapter boundary around `third_party/XianYuApis`.

Rules:

- Do not import `third_party/XianYuApis` directly from business modules.
- Keep business changes out of `third_party/XianYuApis`; the directory is a
  vendored upstream snapshot with only declared compatibility overrides.
- Add proxy handling, lifecycle management, message normalization, retries, and persistence integration here.
- Only SOCKS5/SOCKS5h proxies are supported. Prefer `socks5h` so DNS resolution goes through the proxy.

Concrete implementation:

1. Load upstream helpers with isolated import paths to avoid conflicts with top-level `utils` and `message` packages.
2. Create account-scoped WebSocket sessions with per-account `proxy=` values.
3. Route MTOP HTTP requests through the same account SOCKS proxy.
4. Emit normalized `ChatMessageEvent` objects to business services.
5. Never fall back to direct networking when an account has proxy enabled.

## Product publishing

`MtopProductPublisher` owns the HTTP publishing chain. Business modules pass an
immutable `ProductPublishRequest`; they do not call upstream modules directly.

The chain is:

1. Read a checksummed local product asset, or download an external source image
   with a cookie-free session that rejects private and loopback destinations.
2. Upload the normalized image through the account SOCKS proxy.
3. Resolve the category and default shipping address through signed MTOP calls.
4. Call `mtop.idle.pc.idleitem.publish` once.
5. Verify the returned item ID against the account's on-sale list.

The final publish call is never retried after a timeout, connection failure, or
unparseable response. Those outcomes are marked `verification_required` so an
operator must check Xianyu before creating another task. Response cookie deltas
are merged by the API service with compare-and-set semantics and hot-loaded into
the long-running IM session.

## Updating upstream

Inspect the current vendored source:

```bash
npm run upstream:status
```

Copy the latest official source into the parent working tree:

```bash
npm run upstream:update
```

The updater refuses to run if the vendor source has uncommitted changes and
never creates an independent commit. Review its parent-repository diff and
commit it on `main` with the rest of the project changes.
