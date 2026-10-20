import React, { useEffect, useState } from "react";
import { Text, Image, Alert } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { MedicalDocument } from "../../src/types";
import { useLoad, message } from "../../src/hooks";
import { api, post, pageDataUri } from "../../src/api";
import { Screen, Card, Button, Notice, Busy, styles } from "../../src/ui";
import { reconcileReminders } from "../../src/notifications";

export default function Document() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { data, error, loading, reload } = useLoad<MedicalDocument>(
    `/documents/${id}`,
  );
  const [localError, setLocalError] = useState("");
  const [preview, setPreview] = useState("");
  useEffect(() => {
    if (data && ["queued", "processing"].includes(data.status)) {
      const timer = setInterval(() => void reload(), 4000);
      return () => clearInterval(timer);
    }
  }, [data?.status, reload]);
  async function view(pageId: string) {
    setLocalError("");
    try {
      setPreview(await pageDataUri(id, pageId, "image/png"));
    } catch (e) {
      setLocalError(message(e));
    }
  }
  async function remove() {
    try {
      await api(`/documents/${id}`, { method: "DELETE" });
      await reconcileReminders();
      router.replace("/documents");
    } catch (e) {
      setLocalError(message(e));
    }
  }
  return (
    <Screen
      back
      title="Document details."
      subtitle={
        data ? `${data.document_type} · ${data.pages.length} ordered pages` : ""
      }
      refresh={reload}
      refreshing={loading}
    >
      {loading && !data && <Busy />}
      {!!(error || localError) && <Notice error>{error || localError}</Notice>}
      {data && (
        <>
          <Card>
            <Text style={styles.h3}>Status: {data.status}</Text>
            {data.status === "queued" || data.status === "processing" ? (
              <>
                <Busy />
                <Text style={styles.muted}>
                  You can leave this screen. Processing continues on the backend
                  worker.
                </Text>
              </>
            ) : null}
            {data.error && <Notice error>{data.error}</Notice>}
            {data.status === "error" && (
              <Button
                title="Retry processing"
                onPress={() => {
                  void post(`/documents/${id}/retry`)
                    .then(reload)
                    .catch((e) => setLocalError(message(e)));
                }}
              />
            )}
            {(data.status === "review" || data.status === "confirmed") && (
              <Button
                title={
                  data.status === "review"
                    ? "Review & confirm"
                    : "View extracted source record"
                }
                onPress={() => router.push(`/review/${id}`)}
              />
            )}
          </Card>
          {data.pages.map((p) => (
            <Button
              key={p.id}
              title={`View source page ${p.position}`}
              tone="soft"
              onPress={() => void view(p.id)}
            />
          ))}
          {!!preview && (
            <Card>
              <Image
                source={{ uri: preview }}
                accessibilityLabel="Private source document page"
                style={{ width: "100%", height: 520, resizeMode: "contain" }}
              />
              <Button
                title="Close page preview"
                tone="soft"
                onPress={() => setPreview("")}
              />
            </Card>
          )}
          <Button
            title="Delete document & associated plan"
            tone="danger"
            onPress={() =>
              Alert.alert(
                "Delete this document?",
                "This deletes the source and associated treatment, doses and schedules. Device reminders will be reconciled.",
                [
                  { text: "Keep", style: "cancel" },
                  {
                    text: "Delete",
                    style: "destructive",
                    onPress: () => void remove(),
                  },
                ],
              )
            }
          />
        </>
      )}
    </Screen>
  );
}
