"""Observability primitives: metric registry (Prometheus text), PII-safe log fields. Pure, in-process."""
import hashlib
import re
import threading
from collections import defaultdict

BUCKETS = (0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_LONG = re.compile(r"/[A-Za-z0-9_\-]{24,}")
SECRET_KEYS = re.compile(r"(authorization|password|token|secret|cookie|otp|code|key)", re.IGNORECASE)


def route_label(path: str) -> str:
    """Collapse ids/tokens so label cardinality is bounded and no token ever lands in a metric or log."""
    return _LONG.sub("/:token", _UUID.sub(":id", path))[:120]


def hash_ref(v: str | None) -> str | None:
    return hashlib.sha256(v.encode()).hexdigest()[:12] if v else None


def scrub(d: dict) -> dict:
    return {k: ("[redacted]" if SECRET_KEYS.search(k) else v) for k, v in d.items()}


class Registry:
    def __init__(self):
        self._l = threading.Lock()
        self.count: dict[tuple, int] = defaultdict(int)
        self.hist: dict[tuple, list[int]] = defaultdict(lambda: [0] * (len(BUCKETS) + 1))
        self.sum: dict[tuple, float] = defaultdict(float)
        self.untrusted_calls: dict[str, int] = defaultdict(int)

    def untrusted(self, reason: str) -> None:
        """A call to /v1 or /public/v1 that did not carry a valid X-Acme-Proxy-Key."""
        with self._l:
            self.untrusted_calls[reason] += 1

    def observe(self, method: str, route: str, status: int, seconds: float) -> None:
        k = (method, route_label(route), str(status)[0] + "xx")
        with self._l:
            self.count[k] += 1
            self.sum[k] += seconds
            h = self.hist[k]
            for i, b in enumerate(BUCKETS):
                if seconds <= b:
                    h[i] += 1
            h[-1] += 1

    def render(self) -> str:
        out = ["# TYPE app_http_requests_total counter"]
        with self._l:
            for reason, n in sorted(self.untrusted_calls.items()):
                out.append(f'app_untrusted_proxy_calls_total{{reason="{reason}"}} {n}')
            for (m, r, s), n in sorted(self.count.items()):
                out.append(f'app_http_requests_total{{method="{m}",route="{r}",status="{s}"}} {n}')
            out.append("# TYPE app_http_request_seconds histogram")
            for k in sorted(self.hist):
                m, r, s = k
                h = self.hist[k]
                for i, b in enumerate(BUCKETS):
                    out.append(f'app_http_request_seconds_bucket{{method="{m}",route="{r}",status="{s}",le="{b}"}} {h[i]}')
                out.append(f'app_http_request_seconds_bucket{{method="{m}",route="{r}",status="{s}",le="+Inf"}} {h[-1]}')
                out.append(f'app_http_request_seconds_sum{{method="{m}",route="{r}",status="{s}"}} {round(self.sum[k], 6)}')
                out.append(f'app_http_request_seconds_count{{method="{m}",route="{r}",status="{s}"}} {h[-1]}')
        return "\n".join(out) + "\n"
