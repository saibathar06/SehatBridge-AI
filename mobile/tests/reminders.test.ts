import { test } from "node:test";
import assert from "node:assert/strict";
import { reminderDiff } from "../src/reminderPlan";

test("changed, completed and deleted doses cancel old device alerts", () => {
  const diff = reminderDiff(
    [
      { dose_id: "a", due_at: 200 },
      { dose_id: "b", due_at: 300 },
    ],
    [
      { id: "old-a", dose_id: "a", due_at: 190 },
      { id: "deleted", dose_id: "c", due_at: 250 },
    ],
    100,
  );
  assert.deepEqual(diff.cancel, ["old-a", "deleted"]);
  assert.deepEqual(
    diff.add.map((d) => d.dose_id),
    ["a", "b"],
  );
});
test("unchanged doses are retained and duplicate alerts removed", () => {
  const diff = reminderDiff(
    [
      { dose_id: "a", due_at: 200 },
      { dose_id: "a", due_at: 200 },
    ],
    [
      { id: "one", dose_id: "a", due_at: 200 },
      { id: "duplicate", dose_id: "a", due_at: 200 },
    ],
    100,
  );
  assert.deepEqual(diff, { cancel: ["duplicate"], add: [] });
});
test("queue is bounded and excludes past doses", () => {
  const diff = reminderDiff(
    Array.from({ length: 100 }, (_, i) => ({
      dose_id: String(i),
      due_at: i + 100,
    })),
    [],
    100,
  );
  assert.equal(diff.add.length, 48);
  assert.equal(diff.add[0].due_at, 101);
});
test("disabling reminder intent clears the complete app-owned queue", () => {
  assert.deepEqual(
    reminderDiff([], [{ id: "old", dose_id: "a", due_at: 200 }], 100),
    { cancel: ["old"], add: [] },
  );
});
