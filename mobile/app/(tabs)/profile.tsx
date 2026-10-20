import React, { useEffect, useState } from "react";
import { Alert, Text } from "react-native";
import { router } from "expo-router";
import { useAuth } from "../../src/auth";
import { api, put, forgetTokens } from "../../src/api";
import { message } from "../../src/hooks";
import {
  Screen,
  Card,
  Button,
  Field,
  Toggle,
  Notice,
  styles,
} from "../../src/ui";
import { cancelReminders, reconcileReminders } from "../../src/notifications";
export default function Profile() {
  const auth = useAuth();
  const [name, setName] = useState(auth.profile?.name || "");
  const [zone, setZone] = useState(auth.profile?.timezone || "Asia/Kolkata");
  const [hi, setHi] = useState(auth.profile?.language === "hi");
  const [history, setHistory] = useState(auth.profile?.chat_history || false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);
  async function save() {
    setBusy(true);
    setError("");
    try {
      await put("/profile", {
        name,
        timezone: zone,
        language: hi ? "hi" : "en",
        chat_history: history,
      });
      await auth.reloadProfile();
      await reconcileReminders();
      setInfo(
        "Profile saved. Existing medicine schedules retain their explicitly confirmed timezone.",
      );
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    try {
      await api("/account", { method: "DELETE" });
      await cancelReminders();
      await forgetTokens();
      await auth.reloadProfile().catch(() => {});
      router.replace("/auth");
    } catch (e) {
      setError(message(e));
    }
  }
  return (
    <Screen
      title="A space for you."
      subtitle="Profile, preferences and privacy."
    >
      <Card>
        <Field label="Your name" value={name} onChangeText={setName} />
        <Field
          label="Timezone (IANA)"
          value={zone}
          autoCapitalize="none"
          onChangeText={setZone}
        />
        <Toggle label="Prefer Hindi" value={hi} onChange={setHi} />
        <Toggle
          label="Save encrypted chat history"
          value={history}
          onChange={setHistory}
          description="Off by default. Turning this off deletes saved chat history."
        />
      </Card>
      {!!error && <Notice error>{error}</Notice>}
      {!!info && <Notice>{info}</Notice>}
      <Button title="Save profile" loading={busy} onPress={() => void save()} />
      <Button
        title="Reminders & notification settings"
        tone="soft"
        onPress={() => router.push("/settings")}
      />
      <Button
        title="Medical documents"
        tone="soft"
        onPress={() => router.push("/documents")}
      />
      <Notice>
        Medical documents may be processed by Google's Gemini service under its
        provider terms. Records and files are encrypted, but the authorized
        backend can decrypt them during processing. Device speech providers may
        process audio. SehatBridge does not retain raw audio. This app supports
        documented care and does not diagnose or prescribe.
      </Notice>
      <Button
        title="Delete chat history"
        tone="soft"
        onPress={() => {
          void api("/chat", { method: "DELETE" })
            .then(() => setInfo("Chat history deleted."))
            .catch((e) => setError(message(e)));
        }}
      />
      <Button
        title="Sign out"
        tone="teal"
        onPress={() => {
          void auth
            .logout()
            .then(() => router.replace("/auth"))
            .catch((e) => setError(message(e)));
        }}
      />
      <Button
        title="Delete my account & records"
        tone="danger"
        onPress={() =>
          Alert.alert(
            "Permanently delete your account?",
            "This deletes your live patient records, files, plans and chats. Encrypted backups follow the hosting retention policy.",
            [
              { text: "Keep account", style: "cancel" },
              {
                text: "Delete permanently",
                style: "destructive",
                onPress: () => void remove(),
              },
            ],
          )
        }
      />
    </Screen>
  );
}
