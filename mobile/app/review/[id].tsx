import React, { useEffect, useState } from "react";
import { Text, View, Image } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { Extraction, MedicalDocument, Medicine } from "../../src/types";
import { api, put, post, pageDataUri } from "../../src/api";
import { useLoad, message } from "../../src/hooks";
import { useAuth } from "../../src/auth";
import {
  Screen,
  Card,
  Field,
  Button,
  Notice,
  Toggle,
  Chip,
  Busy,
  styles,
} from "../../src/ui";
import {
  ScheduleEditor,
  ScheduleDraft,
  emptySchedule,
  buildSchedules,
} from "../../src/ScheduleEditor";
import { reconcileReminders } from "../../src/notifications";

export default function Review() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { profile } = useAuth();
  const load = useLoad<{ revision: number; extraction: Extraction }>(
    `/documents/${id}/analysis`,
  );
  const document = useLoad<MedicalDocument>(`/documents/${id}`);
  const [ex, setEx] = useState<Extraction | null>(null);
  const [schedules, setSchedules] = useState<ScheduleDraft[]>([]);
  const [section, setSection] = useState("Summary");
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [source, setSource] = useState("");
  const [sourceText, setSourceText] = useState("");
  const readOnly = document.data?.status === "confirmed";
  useEffect(() => {
    if (load.data) {
      setEx(load.data.extraction);
      setSchedules(
        load.data.extraction.medicines.map((m) =>
          emptySchedule(m, profile?.timezone || "Asia/Kolkata"),
        ),
      );
    }
  }, [load.data]);
  async function showSource(page: number, excerpt: string) {
    try {
      const p = document.data?.pages.find((p) => p.position === page);
      if (!p)
        throw new Error(
          "Source page unavailable. Open document history and retry.",
        );
      setSourceText(`Page ${page}: ${excerpt}`);
      setSource(await pageDataUri(id, p.id, "image/png"));
    } catch (e) {
      setError(message(e));
    }
  }
  function medicineField(i: number, key: keyof Medicine, value: string) {
    setEx((old) =>
      old
        ? {
            ...old,
            medicines: old.medicines.map((m, n) =>
              n === i ? { ...m, [key]: value || null } : m,
            ),
          }
        : old,
    );
  }
  async function save(activate: boolean) {
    if (!ex || !load.data) return;
    setBusy(true);
    setError("");
    try {
      const saved = await put<{ revision: number; extraction: Extraction }>(
        `/documents/${id}/analysis`,
        { revision: load.data.revision, extraction: ex },
      );
      load.setData(saved);
      if (activate) {
        // Keep the user's reviewed schedule values before draft reload initializes the editor.
        const result = await post<{ id: string }>(`/documents/${id}/confirm`, {
          revision: saved.revision,
          confirmed,
          schedules: buildSchedules(schedules),
        });
        await reconcileReminders();
        router.replace(`/treatment/${result.id}`);
      }
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Screen
      back
      title={readOnly ? "Source extraction." : "A little review. A safer plan."}
      subtitle="AI extraction is a draft until you review and confirm it."
    >
      {load.loading && !ex && <Busy />}
      {!!(error || load.error) && <Notice error>{error || load.error}</Notice>}
      {ex && (
        <>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
            {[
              "Summary",
              "Medicines",
              "Tests & visits",
              "Diet & care",
              "Schedules",
            ].map((s) => (
              <Chip
                key={s}
                label={s}
                selected={s === section}
                onPress={() => setSection(s)}
              />
            ))}
          </View>
          {ex.review_flags.map((f, i) => (
            <Notice error key={i}>
              {f}
            </Notice>
          ))}
          {section === "Summary" && (
            <Card>
              <Field
                editable={!readOnly}
                label="Document summary"
                multiline
                value={ex.summary}
                onChangeText={(v) => setEx({ ...ex, summary: v })}
              />
              <Field
                editable={!readOnly}
                label="Document date (blank if absent)"
                value={ex.document_date || ""}
                onChangeText={(v) => setEx({ ...ex, document_date: v || null })}
              />
              <Field
                editable={!readOnly}
                label="Hospital / clinic"
                value={ex.institution || ""}
                onChangeText={(v) => setEx({ ...ex, institution: v || null })}
              />
              <Field
                editable={!readOnly}
                label="Clinician"
                value={ex.clinician || ""}
                onChangeText={(v) => setEx({ ...ex, clinician: v || null })}
              />
              <Field
                editable={!readOnly}
                label="Documented clinical context"
                multiline
                value={ex.clinical_context || ""}
                onChangeText={(v) =>
                  setEx({ ...ex, clinical_context: v || null })
                }
              />
            </Card>
          )}
          {section === "Medicines" && (
            <>
              {!ex.medicines.length && (
                <Notice>No medicines were extracted from this document.</Notice>
              )}
              {ex.medicines.map((m, i) => (
                <Card key={i}>
                  <Text style={styles.h3}>
                    Medicine {i + 1} · {m.confidence} confidence
                  </Text>
                  {m.clarification_required && (
                    <Notice error>
                      Professional clarification required.{" "}
                      {m.review_flags.join(" ")}
                    </Notice>
                  )}
                  {(
                    [
                      "name",
                      "brand_generic",
                      "strength",
                      "dose",
                      "dose_unit",
                      "route",
                      "frequency",
                      "duration",
                      "start_date",
                      "end_date",
                      "food_instructions",
                      "special_instructions",
                    ] as const
                  ).map((key) => (
                    <Field
                      key={key}
                      editable={!readOnly}
                      label={key.replace(/_/g, " ")}
                      value={m[key] || ""}
                      onChangeText={(v) => medicineField(i, key, v)}
                    />
                  ))}
                  <Field
                    editable={!readOnly}
                    label="Source page number"
                    keyboardType="number-pad"
                    value={String(m.source.page)}
                    onChangeText={(v) =>
                      setEx({
                        ...ex,
                        medicines: ex.medicines.map((a, n) =>
                          n === i
                            ? {
                                ...a,
                                source: { ...a.source, page: Number(v) || 1 },
                              }
                            : a,
                        ),
                      })
                    }
                  />
                  <Field
                    editable={!readOnly}
                    label="Supporting source excerpt"
                    multiline
                    value={m.source.excerpt}
                    onChangeText={(v) =>
                      setEx({
                        ...ex,
                        medicines: ex.medicines.map((a, n) =>
                          n === i
                            ? { ...a, source: { ...a.source, excerpt: v } }
                            : a,
                        ),
                      })
                    }
                  />
                  <Button
                    title={`View source · page ${m.source.page}`}
                    tone="soft"
                    onPress={() =>
                      void showSource(m.source.page, m.source.excerpt)
                    }
                  />
                </Card>
              ))}
              {!readOnly && (
                <Button
                  title="Add a medicine documented in the source"
                  tone="soft"
                  onPress={() => {
                    const medicine: Medicine = {
                      name: null,
                      brand_generic: null,
                      strength: null,
                      dose: null,
                      dose_unit: null,
                      route: null,
                      frequency: null,
                      scheduled_times: [],
                      duration: null,
                      start_date: null,
                      end_date: null,
                      food_instructions: null,
                      special_instructions: null,
                      source: { page: 1, excerpt: "" },
                      confidence: "low",
                      clarification_required: true,
                      review_flags: [
                        "Added during patient review; verify with clinician/pharmacist.",
                      ],
                    };
                    setEx({ ...ex, medicines: [...ex.medicines, medicine] });
                    setSchedules([
                      ...schedules,
                      emptySchedule(
                        medicine,
                        profile?.timezone || "Asia/Kolkata",
                      ),
                    ]);
                  }}
                />
              )}
            </>
          )}
          {section === "Tests & visits" && (
            <>
              {(["tests", "follow_ups"] as const).map((key) => (
                <React.Fragment key={key}>
                  <Text style={styles.h2}>
                    {key === "tests"
                      ? "Laboratory investigations"
                      : "Follow-up visits"}
                  </Text>
                  {!ex[key].length && (
                    <Notice>No records extracted in this section.</Notice>
                  )}
                  {ex[key].map((f, i) => (
                    <Card key={i}>
                      <Field
                        editable={!readOnly}
                        label="Name"
                        value={f.name}
                        onChangeText={(v) =>
                          setEx({
                            ...ex,
                            [key]: ex[key].map((a, n) =>
                              n === i ? { ...a, name: v } : a,
                            ),
                          })
                        }
                      />
                      <Field
                        editable={!readOnly}
                        label="Date (YYYY-MM-DD or leave blank)"
                        value={f.date || ""}
                        onChangeText={(v) =>
                          setEx({
                            ...ex,
                            [key]: ex[key].map((a, n) =>
                              n === i ? { ...a, date: v || null } : a,
                            ),
                          })
                        }
                      />
                      <Field
                        editable={!readOnly}
                        label="Documented time window"
                        value={f.time_window || ""}
                        onChangeText={(v) =>
                          setEx({
                            ...ex,
                            [key]: ex[key].map((a, n) =>
                              n === i ? { ...a, time_window: v || null } : a,
                            ),
                          })
                        }
                      />
                      {!!f.review_flags.length && (
                        <Notice error>{f.review_flags.join("\n")}</Notice>
                      )}
                      <Button
                        title={`View source · page ${f.source.page}`}
                        tone="soft"
                        onPress={() =>
                          void showSource(f.source.page, f.source.excerpt)
                        }
                      />
                    </Card>
                  ))}
                </React.Fragment>
              ))}
            </>
          )}
          {section === "Diet & care" && (
            <>
              {!ex.instructions.length && (
                <Notice>No diet or care instructions extracted.</Notice>
              )}
              {ex.instructions.map((f, i) => (
                <Card key={i}>
                  <Text style={styles.h3}>
                    {f.kind} ·{" "}
                    {f.direct_instruction
                      ? "Documented instruction"
                      : "Explanatory summary"}
                  </Text>
                  <Field
                    editable={!readOnly}
                    label="Instruction"
                    multiline
                    value={f.text}
                    onChangeText={(v) =>
                      setEx({
                        ...ex,
                        instructions: ex.instructions.map((a, n) =>
                          n === i ? { ...a, text: v } : a,
                        ),
                      })
                    }
                  />
                  <Button
                    title={`View source · page ${f.source.page}`}
                    tone="soft"
                    onPress={() =>
                      void showSource(f.source.page, f.source.excerpt)
                    }
                  />
                </Card>
              ))}
            </>
          )}
          {section === "Schedules" &&
            (readOnly ? (
              <Notice>Manage confirmed schedules from Treatments.</Notice>
            ) : (
              <>
                <Notice>
                  Leave a medicine disabled when its timing needs clarification.
                  Confirming a plan alone does not activate unscheduled medicine
                  reminders.
                </Notice>
                {ex.medicines.map(
                  (m, i) =>
                    schedules[i] && (
                      <ScheduleEditor
                        key={i}
                        medicine={m}
                        draft={schedules[i]}
                        onChange={(v) =>
                          setSchedules((old) =>
                            old.map((s, n) => (n === i ? v : s)),
                          )
                        }
                      />
                    ),
                )}
              </>
            ))}
          {!!source && (
            <Card>
              <Text style={styles.muted}>{sourceText}</Text>
              <Image
                source={{ uri: source }}
                accessibilityLabel="Referenced source page"
                style={{ width: "100%", height: 480, resizeMode: "contain" }}
              />
              <Button
                title="Close source"
                tone="soft"
                onPress={() => setSource("")}
              />
            </Card>
          )}
          {!readOnly && (
            <>
              <Button
                title="Save review draft"
                tone="soft"
                loading={busy}
                onPress={() => void save(false)}
              />
              <Toggle
                label="I reviewed the source and confirm this plan"
                value={confirmed}
                onChange={setConfirmed}
                description="Unclear instructions must be checked with your treating clinician or pharmacist."
              />
              <Button
                title="Confirm plan & save schedules"
                disabled={!confirmed}
                loading={busy}
                onPress={() => void save(true)}
              />
            </>
          )}
        </>
      )}
    </Screen>
  );
}
