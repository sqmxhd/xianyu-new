import os
import threading
import unittest


os.environ.setdefault("XIANYU_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("XIANYU_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ.setdefault("XIANYU_JWT_SECRET", "test-secret-with-sufficient-length")

from integrations.xianyu_core.upstream import (
    DEFAULT_PLATFORM_HTTP_TIMEOUT,
    _harden_upstream_api_class,
)


class _Session:
    def __init__(self) -> None:
        self.timeouts: list[object] = []

    def request(self, _method: str, _url: str, **kwargs):  # type: ignore[no-untyped-def]
        self.timeouts.append(kwargs.get("timeout"))
        return object()


class _AlwaysExpiredApi:
    def __init__(self) -> None:
        self.session = _Session()
        self.calls = 0

    def get_token(self):  # type: ignore[no-untyped-def]
        self.calls += 1
        self.session.request("POST", "https://example.test/token")
        return self.get_token()


class _ConcurrentRefreshApi:
    barrier = threading.Barrier(2)

    def __init__(self) -> None:
        self.session = _Session()
        self.calls: dict[int, int] = {}

    def get_token(self):  # type: ignore[no-untyped-def]
        thread_id = threading.get_ident()
        count = self.calls.get(thread_id, 0) + 1
        self.calls[thread_id] = count
        if count == 1:
            self.barrier.wait(timeout=1)
            return self.get_token()
        return {"data": {"accessToken": str(thread_id)}}


class UpstreamHttpSafetyTests(unittest.TestCase):
    def test_token_expiry_recursion_is_bounded_and_timeout_is_defaulted(self) -> None:
        api = _harden_upstream_api_class(_AlwaysExpiredApi)()
        with self.assertRaisesRegex(RuntimeError, "bounded refresh attempts"):
            api.get_token()
        self.assertEqual(api.calls, 2)
        self.assertEqual(api.session.timeouts, [DEFAULT_PLATFORM_HTTP_TIMEOUT] * 2)

    def test_explicit_timeout_is_preserved(self) -> None:
        api = _harden_upstream_api_class(_AlwaysExpiredApi)()
        api.session.request("GET", "https://example.test", timeout=(1, 2))
        self.assertEqual(api.session.timeouts[-1], (1, 2))

    def test_concurrent_token_retries_have_thread_local_depth(self) -> None:
        api = _harden_upstream_api_class(_ConcurrentRefreshApi)()
        results: list[dict[str, object]] = []
        errors: list[BaseException] = []

        def run() -> None:
            try:
                results.append(api.get_token())
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=run) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2)
        self.assertFalse(errors)
        self.assertEqual(len(results), 2)


if __name__ == "__main__":
    unittest.main()
