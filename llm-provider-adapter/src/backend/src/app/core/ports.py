"""Ports: vendor-neutral protocols and our own types."""
from dataclasses import dataclass, field
from typing import Any, Protocol


class AuthError(Exception):
    pass


class RateLimited(AuthError):
    """Upstream identity provider throttled the call; surfaced as our 429 + Retry-After."""

    def __init__(self, retry_after: int = 60):
        super().__init__("rate limited")
        self.retry_after = retry_after


class AuthUnavailable(AuthError):
    """Upstream identity provider unreachable / 5xx / timed out; surfaced as 503 where it cannot leak account existence."""


@dataclass(frozen=True)
class Principal:
    subject: str
    issuer: str
    email: str | None = None
    email_verified: bool = False
    mfa: bool = False                                   # the token's aal is aal2
    session_id: str | None = None                       # the token's session_id claim
    aal: str = "aal1"                                   # aal1 | aal2
    amr: tuple[tuple[str, int | None], ...] = ()        # authentication methods used, (method, unix time), as Supabase lists them
    iat: int | None = None
    exp: int | None = None
    name: str | None = None                             # the name given at sign-up (provider metadata); display only, never used for access


class AuthProvider(Protocol):
    async def averify(self, bearer: str) -> Principal: ...
    async def alive(self, bearer: str) -> int | None: ...   # asks the identity provider itself, uncached, whether this session is still good: AuthError when it is not, AuthUnavailable when it cannot be reached; returns the number of verified authenticator factors when the provider says
    async def ready(self) -> bool: ...                   # can it verify tokens right now (signing keys available)?


class ObjectStore(Protocol):
    async def put(self, key: str, data: bytes) -> None: ...
    async def get(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...


@dataclass
class Job:
    id: str
    org_id: str
    kind: str
    payload: dict[str, Any]
    attempts: int = 0


class JobQueue(Protocol):
    async def enqueue(self, conn: Any, kind: str, payload: dict[str, Any], *, run_after: Any = None) -> str: ...


@dataclass
class Message:
    channel: str  # email|sms|whatsapp
    to: str
    template_id: str
    locale: str = "en"
    vars: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str = ""


@dataclass
class Receipt:
    provider_ref: str
    status: str = "sent"


class Notifier(Protocol):
    async def send(self, msg: Message) -> Receipt: ...


class RateLimiter(Protocol):
    def allow(self, key: str) -> bool: ...


class LLMClient(Protocol):
    async def plan(self, text: str, catalog: dict[str, Any]) -> dict[str, Any]: ...
    async def classify(self, texts: list[str], theme_ids: list[str]) -> list[str]: ...
    async def draft_survey(self, brief: str, language: str, goal: str) -> dict[str, Any]: ...
    async def propose_themes(self, texts: list[str], max_themes: int) -> list[dict[str, Any]]: ...
    async def narrate(self, kind: str, computed: dict[str, float], labels: dict[str, str]) -> list[dict[str, Any]]: ...
    async def extract_facts(self, page_text: str, question: str) -> list[dict[str, Any]]: ...
    async def propose_benchmarks(self, evidence_text: str, dimensions: list[str]) -> list[dict[str, Any]]: ...
    async def interview_next(self, objective: str, answer: str, language: str) -> dict[str, Any]: ...
    async def propose_cluster_labels(self, clusters: list[dict[str, Any]]) -> list[dict[str, Any]]: ...
    async def answer_from_evidence(self, question: str, evidence: list[dict[str, str]], labels: dict[str, str]) -> list[dict[str, Any]]: ...
    async def classify_sentiment(self, texts: list[str], hint: str | None = None) -> list[dict[str, Any]]: ...


class EmbeddingProvider(Protocol):
    """Text -> unit vectors. Vectors are only comparable within one model_id (dimension is per model)."""
    model_id: str
    dim: int
    languages: frozenset[str]          # answer languages the model is trusted on ('en'; add 'ar' only for a multilingual model that passed evaluation)
    async def embed(self, texts: list[str], kind: str = "document") -> list[list[float]]: ...   # kind: 'document' | 'query'
