import React, { useState } from "react";
import { Text, View } from "react-native";
import { router, useFocusEffect } from "expo-router";
import { Treatment } from "../../src/types";
import { useLoad } from "../../src/hooks";
import {
  Screen,
  Card,
  Button,
  Chip,
  Notice,
  Empty,
  Busy,
  styles,
  colors,
} from "../../src/ui";
export default function Treatments() {
  const load = useLoad<Treatment[]>("/treatments");
  const [status, setStatus] = useState("active");
  useFocusEffect(
    React.useCallback(() => {
      void load.reload();
    }, [load.reload]),
  );
  return (
    <Screen
      title="Your treatments."
      subtitle="Every confirmed plan, together."
      refresh={load.reload}
      refreshing={load.loading}
    >
      <View style={styles.row}>
        <Chip
          label="Ongoing"
          selected={status === "active"}
          onPress={() => setStatus("active")}
        />
        <Chip
          label="Completed"
          selected={status === "completed"}
          onPress={() => setStatus("completed")}
        />
      </View>
      {!!load.error && <Notice error>{load.error}</Notice>}
      {load.loading && !load.data && <Busy />}
      {load.data
        ?.filter((t) => t.status === status)
        .map((t) => (
          <Card key={t.id}>
            <Text style={styles.h3}>
              {t.extraction.institution || "Reviewed treatment"}
            </Text>
            <Text style={styles.muted}>
              {t.extraction.document_type} ·{" "}
              {new Date(t.confirmed_at * 1000).toLocaleDateString()}
            </Text>
            <Text style={styles.text} numberOfLines={3}>
              {t.extraction.summary}
            </Text>
            <Text style={{ color: colors.teal }}>
              {t.extraction.medicines.length} medicines · {t.schedules.length}{" "}
              active schedules
            </Text>
            <Button
              title="View treatment"
              tone="soft"
              onPress={() => router.push(`/treatment/${t.id}`)}
            />
          </Card>
        ))}
      {load.data && !load.data.filter((t) => t.status === status).length && (
        <Empty
          title={
            status === "active"
              ? "Ready when you are"
              : "No completed treatments"
          }
          text="Review and confirm an uploaded document to create a treatment plan."
        />
      )}
      <Button
        title="Add treatment from a document"
        icon="add-outline"
        onPress={() => router.push("/upload")}
      />
      <Button
        title="Review unconfirmed documents"
        tone="soft"
        onPress={() => router.push("/documents")}
      />
      <Notice>
        Clear instructions matter. Verify uncertain medicines, doses and timing
        with your clinician or pharmacist.
      </Notice>
    </Screen>
  );
}
