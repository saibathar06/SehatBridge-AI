import React, { useEffect, useState } from "react";
import { Linking } from "react-native";
import * as SecureStore from "expo-secure-store";
import { useLoad, message } from "../src/hooks";
import { Preferences } from "../src/types";
import { api, put, post } from "../src/api";
import { Screen, Card, Button, Field, Toggle, Notice } from "../src/ui";
import { useAuth } from "../src/auth";
import {
  requestNotificationPermission,
  reconcileReminders,
  testReminder,
  registerRemoteDevice,
} from "../src/notifications";
export default function Settings() {
  const auth = useAuth();
  const load = useLoad<Preferences>("/notifications/preferences");
  const [prefs, setPrefs] = useState<Preferences>({
    enabled: false,
    remote_enabled: false,
    quiet_start: null,
    quiet_end: null,
  });
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (load.data) setPrefs(load.data);
  }, [load.data]);
  async function action(callback: () => Promise<unknown>, success: string) {
    setBusy(true);
    setError("");
    setInfo("");
    try {
      await callback();
      setInfo(success);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  async function save() {
    if (prefs.enabled && !(await requestNotificationPermission()))
      throw new Error(
        "Notifications denied. Open device settings to allow reminders.",
      );
    if (prefs.remote_enabled) {
      const capability = await api<{ remote_configured: boolean }>(
        "/notifications/intent",
      );
      if (!capability.remote_configured)
        throw new Error(
          "Configure Firebase server credentials before enabling remote reminders.",
        );
      const device = await registerRemoteDevice();
      await SecureStore.setItemAsync("sb.device", device.id);
    } else {
      const device = await SecureStore.getItemAsync("sb.device");
      if (device) {
        await api(`/notifications/devices/${device}`, { method: "DELETE" });
        await SecureStore.deleteItemAsync("sb.device");
      }
    }
    await put("/notifications/preferences", prefs);
    setInfo(await reconcileReminders());
  }
  return (
    <Screen
      back
      title="A timely nudge."
      subtitle="Choose how SehatBridge reminds you."
    >
      <Notice>
        Reminders use confirmed schedules. Local reminders cover a rolling
        seven-day window, capped at 48 alerts. Open the app regularly to refresh
        it. Android battery settings, notification permission, reboot behavior
        and device scheduling limits can affect delivery.
      </Notice>
      <Card>
        <Toggle
          label="Enable health reminders"
          value={prefs.enabled}
          onChange={(v) => setPrefs({ ...prefs, enabled: v })}
        />
        <Toggle
          label="Use remote FCM instead of local alerts"
          value={prefs.remote_enabled}
          onChange={(v) => setPrefs({ ...prefs, remote_enabled: v })}
          description="Requires a Firebase-configured Android build and internet. Use local reminders for the first demonstration."
        />
        <Field
          label="Quiet hours start (HH:MM, blank to disable)"
          value={prefs.quiet_start || ""}
          onChangeText={(v) => setPrefs({ ...prefs, quiet_start: v || null })}
        />
        <Field
          label="Quiet hours end (HH:MM)"
          value={prefs.quiet_end || ""}
          onChangeText={(v) => setPrefs({ ...prefs, quiet_end: v || null })}
        />
        <Notice>
          Quiet hours suppress alerts; they do not move or change your
          prescribed schedule. Lock-screen messages contain generic
          health-reminder text.
        </Notice>
      </Card>
      {!!(error || load.error) && <Notice error>{error || load.error}</Notice>}
      {!!info && <Notice>{info}</Notice>}
      <Button
        title="Save & synchronize reminders"
        loading={busy}
        onPress={() =>
          void action(save, "Reminder preferences saved and synchronized.")
        }
      />
      <Button
        title="Test reminder in 10 seconds"
        tone="soft"
        loading={busy}
        onPress={() =>
          void action(
            testReminder,
            "Test scheduled. Put the app in the background and wait 10 seconds.",
          )
        }
      />
      <Button
        title="Open Android app settings"
        tone="soft"
        onPress={() => void Linking.openSettings()}
      />
      <Card>
        <Field
          label="Current password"
          secureTextEntry
          autoCapitalize="none"
          value={oldPassword}
          onChangeText={setOldPassword}
        />
        <Field
          label="New password (12+ characters)"
          secureTextEntry
          autoCapitalize="none"
          value={newPassword}
          onChangeText={setNewPassword}
        />
        <Button
          title="Change password & sign out"
          tone="soft"
          loading={busy}
          onPress={() =>
            void action(async () => {
              await post("/auth/password", {
                old_password: oldPassword,
                new_password: newPassword,
              });
              await auth.reloadProfile().catch(() => {});
            }, "Password changed. Please sign in again.")
          }
        />
      </Card>
    </Screen>
  );
}
