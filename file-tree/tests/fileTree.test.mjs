import test from "node:test"
import assert from "node:assert/strict"
import { parseOpenMap, toggleOpen, isFolderOpen, treeOpenKey } from "../src/lib/fileTreeState.ts"
import { buildFileTree, filesUnder } from "../src/lib/fileTreeTransform.ts"

test("the open state is remembered per scope, and only closed folders are stored", () => {
  assert.notEqual(treeOpenKey("a"), treeOpenKey("b"))
  assert.equal(isFolderOpen({}, "src"), true)
  const m = toggleOpen({}, "src")
  assert.deepEqual(m, { src: false })
  assert.deepEqual(toggleOpen(m, "src"), {})
  assert.deepEqual(parseOpenMap("not json"), {})
})

test("paths become a nested tree, folders first", () => {
  const tree = buildFileTree([{ file_path: "b.txt" }, { file_path: "src/a.ts" }, { file_path: "src/lib/c.ts" }])
  assert.deepEqual(tree.map(n => n.name), ["src", "b.txt"])
  assert.equal(filesUnder(tree[0]).length, 2)
})
