export type DesiredReminder = { dose_id: string; due_at: number };
export type ExistingReminder = { id: string; dose_id: string; due_at: number };
export function reminderDiff(
  desired: DesiredReminder[],
  existing: ExistingReminder[],
  now: number,
  limit = 48,
) {
  const bounded = [
    ...new Map(
      desired.filter((d) => d.due_at > now).map((d) => [d.dose_id, d]),
    ).values(),
  ]
    .sort((a, b) => a.due_at - b.due_at)
    .slice(0, limit);
  const wanted = new Map(bounded.map((d) => [d.dose_id, d]));
  const retained = new Set<string>();
  const cancel: string[] = [];
  for (const e of existing) {
    const target = wanted.get(e.dose_id);
    if (!target || target.due_at !== e.due_at || retained.has(e.dose_id))
      cancel.push(e.id);
    else retained.add(e.dose_id);
  }
  return { cancel, add: bounded.filter((d) => !retained.has(d.dose_id)) };
}
