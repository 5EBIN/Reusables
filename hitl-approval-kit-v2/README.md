# hitl-approval-kit-v2

**Category:** backend-helpers  
**Origin:** extracted from a production Next.js/FastAPI app.

**Variant of:** `approval-gate` (existing module). **How it differs:** that module is a risk table with a two-person rule and executors; this one is the request lifecycle (TTL, revision requests, idempotent resolve, wait-and-resume) with a client queue and card.

## What it does
Approval request lifecycle (create idempotently per grouping key, resolve by status approved / rejected / revision_requested / expired, atomic claim, TTL expiry sweep, wait-for-decision) plus a frontend half: resolved-event interpretation, a pending-approval queue with reconnect merge, and a generic card.

## Problem it solved
A boolean 'approved' loses why a request ended, double clicks raced, and stale requests never expired.

## Public interface
* `app/approvals/lifecycle.py`: `def resolved_fields(approval_id: str, status: str, action: str) -> dict`
* `app/approvals/lifecycle.py`: `async def await_approval_decision(approval_id: str, timeout_s: int=86400) -> dict`
* `app/approvals/lifecycle.py`: `async def get_pending_approvals(project_id: str, db: AsyncSession) -> list[ApprovalRequest]`
* `app/approvals/resolve.py`: `class ApprovalError`
* `app/approvals/resolve.py`: `async def create_request(owner_id: str, action: str, details: dict, db: AsyncSession, *, group_key: str | None=None, on_request: Hook | None=None) -> ApprovalRequest`
* `app/approvals/resolve.py`: `async def resolve_request(approval_id: str, owner_id: str, status: str, db: AsyncSession, *, feedback: str='', decided_by: str | None=None, on_resolve: Hook | None=None) -> ApprovalRequest`
* `app/approvals/resolve.py`: `async def expire_stale(db: AsyncSession, ttl: timedelta, *, on_resolve: Hook | None=None) -> list[str]`
* `components/ApprovalCard.tsx`: `interface ApprovalCardProps`
* `components/ApprovalCard.tsx`: `function ApprovalCard(`
* `lib/approvalQueue.ts`: `interface PendingApproval`
* `lib/approvalQueue.ts`: `function enqueue(queue: PendingApproval[], a: PendingApproval): PendingApproval[]`
* `lib/approvalQueue.ts`: `function dequeue(queue: PendingApproval[], id: string): PendingApproval[]`
* `lib/approvalQueue.ts`: `function mergePending(queue: PendingApproval[], serverPending: PendingApproval[]): PendingApproval[]`
* `lib/approvalQueue.ts`: `function onResolved(queue: PendingApproval[], event:`
* `lib/approvalResolved.ts`: `const RESUME_ACTIONS: ReadonlySet<string>`
* `lib/approvalResolved.ts`: `interface Resolved`
* `lib/approvalResolved.ts`: `function resolvedApproval(data: unknown): Resolved`
* `lib/approvalResolved.ts`: `function shouldResume(data: unknown): boolean`
* `lib/approvalResolved.ts`: `function resolvedText(data: unknown): string`

## Dependencies
Python (`deps.txt`): `sqlalchemy[asyncio]>=2.0`
JavaScript (`deps.json`): `react`

## Stubs and what the host must provide
`src/app/_stubs.py` / `src/_stubs.ts` keep imports resolvable. The host must replace: `ApprovalRequest`, `AsyncSessionLocal`.

## Known limits
The ORM model and DB session are host stubs; revision-needs-feedback and the status vocabulary are rules written for this kit around the extracted claim/wait code. Notification is a hook (SSE optional).

## Quality
B (3 frontend tests copied; backend untested here)  
Tests copied: 1 (copied from the source, not run here).

## How to reuse
Call `create_request`, `resolve_request`, `expire_stale` from your routes and a periodic task.

(Stub signatures were derived from the host code they stand for; they carry no behaviour.)
