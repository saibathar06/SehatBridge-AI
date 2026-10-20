import React from "react";
import { Stack, useSegments, router } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { AuthProvider, useAuth } from "../src/auth";

function AuthGate() {
  const { profile, loading } = useAuth();
  const segments = useSegments();
  React.useEffect(() => {
    const first = segments[0] as string | undefined;
    if (!loading && !profile && first && first !== "auth")
      router.replace("/auth");
  }, [profile, loading, segments]);
  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: "#FFF9F7" },
      }}
    />
  );
}

export default function Layout() {
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <StatusBar style="dark" />
        <AuthGate />
      </AuthProvider>
    </SafeAreaProvider>
  );
}
