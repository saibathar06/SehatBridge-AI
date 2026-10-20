import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  ReactNode,
} from "react";
import { AppState } from "react-native";
import * as SecureStore from "expo-secure-store";
import * as Notifications from "expo-notifications";
import {
  api,
  forgetTokens,
  onExpired,
  post,
  refreshSession,
  saveTokens,
} from "./api";
import { Profile } from "./types";
import { cancelReminders, reconcileReminders } from "./notifications";

type AuthState = {
  profile: Profile | null;
  loading: boolean;
  accept: (tokens: {
    access_token: string;
    refresh_token: string;
  }) => Promise<void>;
  reloadProfile: () => Promise<void>;
  logout: () => Promise<void>;
};
const Auth = createContext<AuthState>(null!);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  async function reloadProfile() {
    setProfile(await api<Profile>("/profile"));
  }
  useEffect(() => {
    onExpired(() => {
      setProfile(null);
      void cancelReminders();
    });
    (async () => {
      try {
        if (await refreshSession()) await reloadProfile();
      } finally {
        setLoading(false);
      }
    })().catch(() => setLoading(false));
  }, []);
  useEffect(() => {
    if (!profile) return;
    void reconcileReminders().catch(() => {});
    const listener = AppState.addEventListener("change", (state) => {
      if (state === "active") void reconcileReminders().catch(() => {});
    });
    const tokenListener = Notifications.addPushTokenListener((token) => {
      void (async () => {
        const previousId = await SecureStore.getItemAsync("sb.device");
        if (!previousId) return;
        await api(`/notifications/devices/${previousId}`, { method: "DELETE" });
        const device = await post<{ id: string }>("/notifications/devices", {
          token: token.data,
          device_name: "Android device",
        });
        await SecureStore.setItemAsync("sb.device", device.id);
      })().catch(() => {});
    });
    const timer = setInterval(
      () => {
        void reconcileReminders().catch(() => {});
      },
      5 * 60 * 1000,
    );
    return () => {
      listener.remove();
      tokenListener.remove();
      clearInterval(timer);
    };
  }, [profile?.id]);
  async function accept(tokens: {
    access_token: string;
    refresh_token: string;
  }) {
    await saveTokens(tokens);
    await reloadProfile();
  }
  async function logout() {
    // Require server logout success before discarding a still-valid session.
    const device = await SecureStore.getItemAsync("sb.device");
    if (device)
      await api("/notifications/devices/" + device, { method: "DELETE" }).catch(
        () => {},
      );
    await post("/auth/logout");
    await SecureStore.deleteItemAsync("sb.device");
    await cancelReminders();
    await forgetTokens();
    setProfile(null);
  }
  return (
    <Auth.Provider value={{ profile, loading, accept, reloadProfile, logout }}>
      {children}
    </Auth.Provider>
  );
}
export function useAuth() {
  return useContext(Auth);
}
