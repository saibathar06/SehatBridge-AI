import React, { useEffect, useState } from "react";
import { Text, Alert } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { Treatment } from "../../src/types";
import { useLoad, message } from "../../src/hooks";
import { put, post } from "../../src/api";
import {
  Screen,
  Card,
  Button,
  Notice,
  Busy,
  Toggle,
  styles,
} from "../../src/ui";
import {
  ScheduleEditor,
  ScheduleDraft,
  emptySchedule,
  buildSchedules,
} from "../../src/ScheduleEditor";
import { reconcileReminders } from "../../src/notifications";
import { useAuth } from "../../src/auth";
export default function Details() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { profile } = useAuth();
  const load = useLoad<Treatment>(`/treatments/${id}`);
  const [edit, setEdit] = useState(false);
  const [drafts, setDrafts] = useState<ScheduleDraft[]>([]);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (load.data) {
      const t = load.data;
      setDrafts(
        t.extraction.medicines.map((m, i) => {
          const s = t.schedules.find((s) => s.medicine_index === i);
          return s
            ? {
                enabled: true,
                times: s.times.join(", "),
                timezone: s.timezone,
                start: s.start_date,
                end: s.end_date,
                timingConfirmed: false,
                verified: s.clinician_verified,
                note: s.clarification_note,
              }
            : emptySchedule(m, profile?.timezone || "Asia/Kolkata");
        }),
      );
    }
  }, [load.data]);
  async function save() {
    setBusy(true);
    setError("");
    try {
      await put(`/treatments/${id}/schedules`, {
        revision: load.data?.revision,
        confirmed,
        schedules: buildSchedules(drafts),
      });
      await reconcileReminders();
      setEdit(false);
      setConfirmed(false);
      await load.reload();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  async function complete() {
    try {
      await post(`/treatments/${id}/complete`);
      await reconcileReminders();
      await load.reload();
    } catch (e) {
      setError(message(e));
    }
  }
  const t = load.data;
  return (
    <Screen
      back
      title="Your treatment plan."
      refresh={load.reload}
      refreshing={load.loading}
    >
      {!!(load.error || error) && <Notice error>{load.error || error}</Notice>}
      {load.loading && !t && <Busy />}
      {t && (
        <>
          <Card>
            <Text style={styles.h3}>
              {t.extraction.institution || "Confirmed medical document"}
            </Text>
            <Text style={styles.text}>{t.extraction.summary}</Text>
            <Text style={styles.muted}>
              {t.status} · revision {t.revision}
            </Text>
          </Card>
          {t.extraction.review_flags.map((f, i) => (
            <Notice error key={i}>
              {f}
            </Notice>
          ))}
          <Text style={styles.h2}>Medicines</Text>
          {t.extraction.medicines.map((m, i) => (
            <Card key={i}>
              <Text style={styles.h3}>
                {m.name || "Unclear name"} {m.strength}
              </Text>
              <Text style={styles.text}>
                {m.dose || "Unclear dose"} {m.dose_unit} ·{" "}
                {m.frequency || "Frequency unclear"}
              </Text>
              <Text style={styles.muted}>
                {m.food_instructions}
                {m.special_instructions ? "\n" + m.special_instructions : ""}
              </Text>
              <Text style={styles.muted}>
                Duration: {m.duration || "Not documented"} · route:{" "}
                {m.route || "Not documented"}
              </Text>
              {m.clarification_required && (
                <Notice error>
                  {m.review_flags.join("\n") ||
                    "Professional clarification required"}
                </Notice>
              )}
              <Text style={styles.muted}>
                Source page {m.source.page}: {m.source.excerpt}
              </Text>
            </Card>
          ))}
          <Text style={styles.h2}>Tests & follow-ups</Text>
          {[...t.extraction.tests, ...t.extraction.follow_ups].map((f, i) => (
            <Card key={i}>
              <Text style={styles.h3}>{f.name}</Text>
              <Text style={styles.text}>
                {f.date || f.time_window || "Date needs clarification"}
              </Text>
              <Text style={styles.muted}>
                Page {f.source.page}: {f.source.excerpt}
              </Text>
            </Card>
          ))}
          <Text style={styles.h2}>Diet & care</Text>
          {t.extraction.instructions.map((f, i) => (
            <Card key={i}>
              <Text style={styles.text}>{f.text}</Text>
              <Text style={styles.muted}>
                {f.direct_instruction
                  ? "Documented instruction"
                  : "Explanatory summary"}{" "}
                · page {f.source.page}
              </Text>
            </Card>
          ))}
          <Button
            title="View original document"
            tone="soft"
            onPress={() => router.push(`/document/${t.document_id}`)}
          />
          <Button
            title="Dose history & adherence"
            tone="soft"
            onPress={() => router.push("/tracker")}
          />
          {t.status === "active" && (
            <>
              <Button
                title={
                  edit
                    ? "Close schedule editor"
                    : "Review or change reminder schedules"
                }
                tone="teal"
                onPress={() => setEdit(!edit)}
              />
              {edit && (
                <>
                  {t.extraction.medicines.map(
                    (m, i) =>
                      drafts[i] && (
                        <ScheduleEditor
                          key={i}
                          medicine={m}
                          draft={drafts[i]}
                          onChange={(v) =>
                            setDrafts((old) =>
                              old.map((a, n) => (n === i ? v : a)),
                            )
                          }
                        />
                      ),
                  )}
                  <Toggle
                    label="I confirm these revised schedules"
                    value={confirmed}
                    onChange={setConfirmed}
                  />
                  <Button
                    title="Save & reconcile reminders"
                    loading={busy}
                    disabled={!confirmed}
                    onPress={() => void save()}
                  />
                </>
              )}
              <Button
                title="Mark treatment completed"
                tone="soft"
                onPress={() =>
                  Alert.alert(
                    "Complete this treatment?",
                    "Complete only when the documented course has ended or your clinician confirms. Future reminders will stop.",
                    [
                      { text: "Keep active", style: "cancel" },
                      {
                        text: "Mark completed",
                        onPress: () => void complete(),
                      },
                    ],
                  )
                }
              />
            </>
          )}
        </>
      )}
    </Screen>
  );
}
