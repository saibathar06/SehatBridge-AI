import React, { useState } from "react";
import { Text, View } from "react-native";
import { useLoad } from "../src/hooks";
import { Dose } from "../src/types";
import {
  Screen,
  Chip,
  Notice,
  Busy,
  Empty,
  styles,
  Card,
  Button,
} from "../src/ui";
import { DoseRow } from "../src/DoseRow";
import { useAuth } from "../src/auth";
export default function Tracker() {
  const [offset, setOffset] = useState(0);
  const { profile } = useAuth();
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: profile?.timezone || "Asia/Kolkata",
    year: "numeric",
    month: "numeric",
    day: "numeric",
  }).formatToParts(new Date());
  const value = (type: string) =>
    Number(parts.find((p) => p.type === type)?.value);
  const day = new Date(
    Date.UTC(value("year"), value("month") - 1, value("day") + offset, 12),
  );
  const load = useLoad<Dose[]>(`/doses?day_offset=${offset}`);
  const doses = load.data || [];
  return (
    <Screen
      back
      title="Medicine tracker."
      subtitle={
        day.toLocaleDateString([], {
          weekday: "long",
          day: "numeric",
          month: "long",
          timeZone: "UTC",
        }) + ` · ${profile?.timezone}`
      }
      refresh={load.reload}
      refreshing={load.loading}
    >
      <View style={styles.row}>
        <View style={{ flex: 1 }}>
          <Button
            title="Previous day"
            tone="soft"
            disabled={offset <= -366}
            onPress={() => setOffset(offset - 1)}
          />
        </View>
        <View style={{ flex: 1 }}>
          <Button
            title="Next day"
            tone="soft"
            disabled={offset >= 7}
            onPress={() => setOffset(offset + 1)}
          />
        </View>
      </View>
      <Button title="Today" tone="soft" onPress={() => setOffset(0)} />
      <Card>
        <Text style={styles.h3}>
          {doses.filter((d) => d.status === "taken").length} / {doses.length}{" "}
          recorded taken
        </Text>
        <Text style={styles.muted}>
          A reminder opening never records a dose. Record what happened, and
          correct mistakes in the event history.
        </Text>
      </Card>
      <Notice>
        A missed dose does not mean you should double the next dose. Ask your
        pharmacist or clinician about unclear instructions.
      </Notice>
      {!!load.error && <Notice error>{load.error}</Notice>}
      {load.loading && !load.data && <Busy />}
      {doses.map((d) => (
        <DoseRow key={d.id} dose={d} reload={load.reload} />
      ))}
      {load.data && !doses.length && (
        <Empty
          title="No scheduled doses"
          text="Only confirmed, active schedules create doses. Past records begin when the schedule was activated."
        />
      )}
    </Screen>
  );
}
