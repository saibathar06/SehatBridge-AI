import React, { useState } from "react";
import { Text, View } from "react-native";
import { Dose } from "./types";
import { Card, styles, colors, Icon, Button, Notice } from "./ui";
import { post, api } from "./api";
import { message } from "./hooks";
import { reconcileReminders } from "./notifications";

export function DoseRow({ dose, reload }: { dose: Dose; reload: () => void }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<string[] | null>(null);
  async function mark(status: Dose["status"]) {
    setBusy(true);
    setError("");
    try {
      await post(`/doses/${dose.id}/events`, {
        status,
        expected_status: dose.status,
        idempotency_key: `${dose.id}:${Date.now()}`,
      });
      await reconcileReminders();
      reload();
      setHistory(null);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card>
      <View style={styles.row}>
        <View
          style={{
            backgroundColor:
              dose.status === "taken" ? colors.tealSoft : colors.pinkSoft,
            padding: 12,
            borderRadius: 18,
          }}
        >
          <Icon
            name={
              dose.status === "taken" ? "checkmark-circle" : "medical-outline"
            }
            color={dose.status === "taken" ? colors.teal : colors.pink}
          />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.h3}>
            {dose.medicine.name} {dose.medicine.strength}
          </Text>
          <Text style={styles.muted}>
            {dose.medicine.dose} {dose.medicine.dose_unit} ·{" "}
            {dose.medicine.food_instructions || "No food instruction recorded"}
          </Text>
        </View>
        <Text style={styles.muted}>
          {new Date(dose.due_at * 1000).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
            timeZone: dose.timezone,
          })}
        </Text>
      </View>
      <Text
        style={[
          styles.muted,
          { color: dose.status === "taken" ? colors.teal : colors.muted },
        ]}
      >
        {dose.status} · {dose.timezone}
      </Text>
      {dose.status !== "taken" && (
        <View style={styles.row}>
          <View style={{ flex: 1 }}>
            <Button
              title="Taken"
              tone="teal"
              loading={busy}
              onPress={() => void mark("taken")}
            />
          </View>
          <View style={{ flex: 1 }}>
            <Button
              title="Skipped"
              tone="soft"
              loading={busy}
              onPress={() => void mark("skipped")}
            />
          </View>
        </View>
      )}
      {dose.status !== "upcoming" && (
        <Button
          title="Correct to upcoming"
          tone="soft"
          loading={busy}
          onPress={() => void mark("upcoming")}
        />
      )}
      <Button
        title="Dose event history"
        tone="soft"
        onPress={() => {
          void api<{ before: string; status: string; recorded_at: number }[]>(
            `/doses/${dose.id}/events`,
          )
            .then((events) =>
              setHistory(
                events.map(
                  (e) =>
                    `${e.before} → ${e.status} · ${new Date(e.recorded_at * 1000).toLocaleString()}`,
                ),
              ),
            )
            .catch((e) => setError(message(e)));
        }}
      />
      {history && (
        <Text style={styles.muted}>
          {history.length ? history.join("\n") : "No recorded dose events."}
        </Text>
      )}
      {!!error && <Notice error>{error}</Notice>}
    </Card>
  );
}
