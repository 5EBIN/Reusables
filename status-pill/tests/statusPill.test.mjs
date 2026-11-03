import { test } from "node:test"
import assert from "node:assert/strict"
import { statusPill, countsAsPass } from "../src/lib/statusPill.ts"

test("a known status gets its pill", () => {
  assert.equal(statusPill("job", "done").kind, "pass")
  assert.equal(statusPill("review", "rejected").kind, "fail")
})

test("an unknown status is neutral, shows its raw text and never counts as a pass", () => {
  const p = statusPill("job", "mystery")
  assert.equal(p.kind, "neutral")
  assert.equal(p.label, "mystery")
  assert.equal(countsAsPass(p), false)
})

test("every pill has a label and an icon", () => {
  for (const v of ["queued", "running", "done", "failed"]) {
    const p = statusPill("job", v)
    assert.ok(p.label && p.icon)
  }
})
