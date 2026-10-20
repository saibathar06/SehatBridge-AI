import React from "react";
import { Tabs, Redirect } from "expo-router";
import { useAuth } from "../../src/auth";
import { colors, Icon, Screen, Busy } from "../../src/ui";

export default function TabLayout() {
  const { profile, loading } = useAuth();
  if (loading)
    return (
      <Screen>
        <Busy />
      </Screen>
    );
  if (!profile) return <Redirect href="/auth" />;
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.teal,
        tabBarInactiveTintColor: colors.muted,
        tabBarStyle: {
          backgroundColor: "#FFFFFF",
          borderTopColor: colors.line,
          paddingTop: 8,
        },
        tabBarLabelStyle: { fontSize: 10, fontWeight: "600" },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Home",
          tabBarIcon: ({ focused }) => (
            <Icon
              name="home-outline"
              color={focused ? colors.teal : colors.muted}
            />
          ),
        }}
      />
      <Tabs.Screen
        name="treatments"
        options={{
          title: "Treatments",
          tabBarIcon: ({ focused }) => (
            <Icon
              name="document-text-outline"
              color={focused ? colors.teal : colors.muted}
            />
          ),
        }}
      />
      <Tabs.Screen
        name="assistant"
        options={{
          title: "AI Assistant",
          tabBarIcon: ({ focused }) => (
            <Icon
              name="chatbubbles-outline"
              color={focused ? colors.teal : colors.muted}
            />
          ),
        }}
      />
      <Tabs.Screen
        name="appointments"
        options={{
          title: "Appointments",
          tabBarIcon: ({ focused }) => (
            <Icon
              name="calendar-outline"
              color={focused ? colors.teal : colors.muted}
            />
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: "Profile",
          tabBarIcon: ({ focused }) => (
            <Icon
              name="person-outline"
              color={focused ? colors.teal : colors.muted}
            />
          ),
        }}
      />
    </Tabs>
  );
}
