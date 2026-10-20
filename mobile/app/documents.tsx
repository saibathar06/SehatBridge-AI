import React from "react";
import { Text } from "react-native";
import { router, useFocusEffect } from "expo-router";
import { MedicalDocument } from "../src/types";
import { useLoad } from "../src/hooks";
import { Screen, Card, Button, Notice, Busy, Empty, styles } from "../src/ui";
export default function Documents() {
  const { data, error, loading, reload } =
    useLoad<MedicalDocument[]>("/documents");
  useFocusEffect(
    React.useCallback(() => {
      void reload();
    }, [reload]),
  );
  return (
    <Screen
      back
      title="Your documents."
      subtitle="Private records, in the order you uploaded them."
      refresh={reload}
      refreshing={loading}
    >
      <Button
        title="Upload a new document"
        onPress={() => router.push("/upload")}
      />
      {!!error && <Notice error>{error}</Notice>}
      {loading && !data && <Busy />}
      {data?.map((d) => (
        <Card key={d.id}>
          <Text style={styles.h3}>
            {d.document_type} · {d.pages.length} pages
          </Text>
          <Text style={styles.muted}>
            {new Date(d.created_at * 1000).toLocaleDateString()} · {d.status}
          </Text>
          <Button
            title={
              d.status === "review" ? "Review extraction" : "Open document"
            }
            tone="soft"
            onPress={() => router.push(`/document/${d.id}`)}
          />
        </Card>
      ))}
      {data && !data.length && (
        <Empty
          title="No documents yet"
          text="Your prescriptions, reports and discharge summaries will appear here."
        />
      )}
    </Screen>
  );
}
