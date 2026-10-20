import React from "react";
import { Text } from "react-native";
import { Medicine, ScheduleInput } from "./types";
import { Card, Field, Toggle, Notice, styles } from "./ui";

export type ScheduleDraft = {
  enabled: boolean;
  times: string;
  timezone: string;
  start: string;
  end: string;
  timingConfirmed: boolean;
  verified: boolean;
  note: string;
};
export function emptySchedule(
  medicine: Medicine,
  timezone: string,
): ScheduleDraft {
  return {
    enabled: false,
    times: medicine.scheduled_times.join(", "),
    timezone,
    start: medicine.start_date || "",
    end: medicine.end_date || "",
    timingConfirmed: false,
    verified: false,
    note: "",
  };
}
export function buildSchedules(drafts: ScheduleDraft[]): ScheduleInput[] {
  return drafts.flatMap((d, i) =>
    d.enabled
      ? [
          {
            medicine_index: i,
            times: d.times
              .split(",")
              .map((v) => v.trim())
              .filter(Boolean),
            timezone: d.timezone,
            start_date: d.start,
            end_date: d.end,
            timing_confirmed: d.timingConfirmed,
            clinician_verified: d.verified,
            clarification_note: d.note,
          },
        ]
      : [],
  );
}
export function ScheduleEditor({
  medicine,
  draft,
  onChange,
}: {
  medicine: Medicine;
  draft: ScheduleDraft;
  onChange: (value: ScheduleDraft) => void;
}) {
  const update = (key: keyof ScheduleDraft, value: string | boolean) =>
    onChange({ ...draft, [key]: value });
  return (
    <Card>
      <Text style={styles.h3}>
        Reminder schedule · {medicine.name || "Unclear medicine"}
      </Text>
      <Toggle
        label="Activate reminders for this medicine"
        value={draft.enabled}
        onChange={(v) => update("enabled", v)}
      />
      {draft.enabled && (
        <>
          <Notice>
            Copy documented times or confirm appropriate timing with your
            clinician or pharmacist. No times or dates are generated
            automatically.
          </Notice>
          <Field
            label="Times (24-hour HH:MM, comma separated)"
            value={draft.times}
            onChangeText={(v) => update("times", v)}
            placeholder="Enter confirmed times"
          />
          <Field
            label="Timezone (IANA)"
            value={draft.timezone}
            onChangeText={(v) => update("timezone", v)}
            autoCapitalize="none"
          />
          <Field
            label="Confirmed start date (YYYY-MM-DD)"
            value={draft.start}
            onChangeText={(v) => update("start", v)}
          />
          <Field
            label="Confirmed end date (YYYY-MM-DD)"
            value={draft.end}
            onChangeText={(v) => update("end", v)}
          />
          <Toggle
            label="I confirm these dates and times"
            value={draft.timingConfirmed}
            onChange={(v) => update("timingConfirmed", v)}
          />
          {medicine.clarification_required && (
            <>
              <Notice error>
                This medicine has missing or uncertain details. Correct critical
                fields and record professional clarification before scheduling.
              </Notice>
              <Toggle
                label="A clinician or pharmacist verified these instructions"
                value={draft.verified}
                onChange={(v) => update("verified", v)}
              />
              <Field
                label="Clarification recorded (who and what was clarified)"
                multiline
                value={draft.note}
                onChangeText={(v) => update("note", v)}
              />
            </>
          )}
        </>
      )}
    </Card>
  );
}
