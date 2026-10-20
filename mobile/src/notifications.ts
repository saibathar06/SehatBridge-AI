import * as Notifications from "expo-notifications";
import { Platform } from "react-native";
import { api, post } from "./api";
import { NotificationIntent } from "./types";
import { reminderDiff } from "./reminderPlan";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});
let reconciling: Promise<string> | null = null;
export async function requestNotificationPermission() {
  if (Platform.OS === "android")
    await Notifications.setNotificationChannelAsync("health", {
      name: "Health reminders",
      importance: Notifications.AndroidImportance.HIGH,
      lockscreenVisibility: Notifications.AndroidNotificationVisibility.PRIVATE,
    });
  const result = await Notifications.requestPermissionsAsync();
  return result.granted;
}
export async function cancelReminders() {
  if (reconciling) await reconciling.catch(() => {});
  const queue = await Notifications.getAllScheduledNotificationsAsync();
  for (const item of queue)
    if (item.content.data?.sehatbridge)
      await Notifications.cancelScheduledNotificationAsync(item.identifier);
}
export async function reconcileReminders(): Promise<string> {
  if (reconciling) return reconciling;
  reconciling = (async () => {
    const intent = await api<NotificationIntent>("/notifications/intent");
    const permission = await Notifications.getPermissionsAsync();
    const queue = await Notifications.getAllScheduledNotificationsAsync();
    const existing = queue
      .filter((n) => n.content.data?.sehatbridge)
      .map((n) => ({
        id: n.identifier,
        dose_id: String(n.content.data?.dose_id),
        due_at: Number(n.content.data?.due_at),
      }));
    // Select one channel per device: remote preference avoids local/FCM duplicate alerts.
    const local =
      intent.preferences.enabled &&
      !intent.preferences.remote_enabled &&
      permission.granted;
    const diff = reminderDiff(
      local ? intent.doses : [],
      existing,
      Date.now() / 1000,
    );
    for (const id of diff.cancel)
      await Notifications.cancelScheduledNotificationAsync(id);
    for (const dose of diff.add)
      await Notifications.scheduleNotificationAsync({
        content: {
          title: "SehatBridge AI",
          body: "You have a scheduled health reminder.",
          sound: "default",
          data: {
            sehatbridge: true,
            dose_id: dose.dose_id,
            due_at: dose.due_at,
          },
        },
        trigger: {
          type: Notifications.SchedulableTriggerInputTypes.DATE,
          date: new Date(dose.due_at * 1000),
          channelId: "health",
        },
      });
    if (!permission.granted && intent.preferences.enabled)
      return "Notifications are blocked. Enable them in Android settings.";
    return intent.preferences.remote_enabled
      ? "Remote reminders selected. An FCM-configured Android build is required."
      : `Reminder window synced (${local ? intent.doses.length : 0} upcoming alerts).`;
  })();
  try {
    return await reconciling;
  } finally {
    reconciling = null;
  }
}
export async function registerRemoteDevice() {
  if (Platform.OS !== "android")
    throw new Error("FCM registration is supported on Android.");
  const result = await Notifications.getDevicePushTokenAsync();
  return await post<{ id: string }>("/notifications/devices", {
    token: result.data,
    device_name: "Android device",
  });
}
export async function testReminder() {
  if (!(await requestNotificationPermission()))
    throw new Error("Notification permission was denied.");
  await Notifications.scheduleNotificationAsync({
    content: {
      title: "SehatBridge AI",
      body: "This is your test health reminder.",
      data: { sehatbridge: true },
    },
    trigger: {
      type: Notifications.SchedulableTriggerInputTypes.TIME_INTERVAL,
      seconds: 10,
      channelId: "health",
    },
  });
}
