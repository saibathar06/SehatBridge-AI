import React, { useState } from "react";
import { Text, View } from "react-native";
import { Redirect, router } from "expo-router";
import { useAuth } from "../src/auth";
import { Screen, Button, Icon, styles, colors, Busy } from "../src/ui";

const pages = [
  {
    icon: "heart-circle-outline" as const,
    title: "Your health.\nIn your language.",
    body: "Understand. Organize. Follow through. Healthcare support for you and your family.",
  },
  {
    icon: "documents-outline" as const,
    title: "Understand your\nmedical documents.",
    body: "Bring your prescription or discharge summary. Review a clear explanation in Hindi or English.",
  },
  {
    icon: "calendar-outline" as const,
    title: "Your treatment,\nbeautifully organized.",
    body: "Confirm your plan, set medicine reminders and keep track of each dose, test and follow-up.",
  },
  {
    icon: "mic-outline" as const,
    title: "A little clarity.\nA little reassurance.",
    body: "Ask about your confirmed records in your own words. Review the transcript and hear the answer aloud.",
  },
];
export default function Welcome() {
  const auth = useAuth();
  const [page, setPage] = useState(0);
  if (auth.loading)
    return (
      <Screen>
        <Busy />
      </Screen>
    );
  if (auth.profile) return <Redirect href="/(tabs)" />;
  const p = pages[page];
  return (
    <Screen>
      <View style={{ alignItems: "center", paddingTop: 24, gap: 8 }}>
        <Icon name="leaf" size={40} />
        <Text style={styles.h2}>SehatBridge AI</Text>
        <Text style={styles.muted}>Your health. Your language.</Text>
      </View>
      <View style={{ alignItems: "center", paddingVertical: 42, gap: 28 }}>
        <View
          style={{
            width: 210,
            height: 210,
            borderRadius: 105,
            backgroundColor: colors.pinkSoft,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Icon name={p.icon} size={112} color={colors.pink} />
        </View>
        <Text style={[styles.title, { textAlign: "center", fontSize: 34 }]}>
          {p.title}
        </Text>
        <Text
          style={[styles.text, { textAlign: "center", color: colors.muted }]}
        >
          {p.body}
        </Text>
        <View style={styles.row}>
          {pages.map((_, i) => (
            <View
              key={i}
              accessibilityLabel={`Step ${i + 1}`}
              style={{
                width: i === page ? 24 : 7,
                height: 7,
                borderRadius: 4,
                backgroundColor: i === page ? colors.pink : "#E9DADD",
              }}
            />
          ))}
        </View>
      </View>
      <Button
        title={page < 3 ? "Continue" : "Start your health journey"}
        onPress={() =>
          page < 3 ? setPage(page + 1) : router.push("/auth?mode=register")
        }
      />
      {page < 3 && (
        <Button
          title="Skip introduction"
          tone="soft"
          onPress={() => router.push("/auth?mode=register")}
        />
      )}
      <Button
        title="Already have an account? Sign in"
        tone="soft"
        onPress={() => router.push("/auth")}
      />
    </Screen>
  );
}
