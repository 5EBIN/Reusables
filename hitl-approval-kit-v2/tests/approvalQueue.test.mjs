import { test } from "node:test"
import assert from "node:assert/strict"
import { enqueue, dequeue, mergePending, onResolved } from "../lib/approvalQueue.ts"

const a = id => ({ approval_id: id, action: "example_review" })

test("enqueue never duplicates", () => {
  assert.equal(enqueue(enqueue([], a("1")), a("1")).length, 1)
})

test("mergePending keeps, adds and drops by id", () => {
  const merged = mergePending([a("1"), a("2")], [a("2"), a("3")])
  assert.deepEqual(merged.map(p => p.approval_id), ["2", "3"])
})

test("any resolved status removes the request", () => {
  assert.deepEqual(onResolved([a("1")], { approval_id: "1", status: "expired" }), [])
  assert.deepEqual(dequeue([a("1")], "9").length, 1)
})
