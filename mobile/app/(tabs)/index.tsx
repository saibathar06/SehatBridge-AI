import React from "react";
import { Text, View, Pressable } from "react-native";
import { router, useFocusEffect } from "expo-router";
import { useLoad } from "../../src/hooks";
import { Profile, Treatment, MedicalDocument, Dose } from "../../src/types";
import {
  Screen,
  Card,
  Button,
  styles,
  colors,
  Icon,
  Notice,
  Busy,
  Empty,
} from "../../src/ui";
import { DoseRow } from "../../src/DoseRow";

type Dashboard = {
  profile: Profile;
  plans: Treatment[];
  doses: Dose[];
  documents: MedicalDocument[];
  counts: Record<string, number>;
};
export default function Home() {
  const { data, loading, error, reload } = useLoad<Dashboard>("/dashboard");
  useFocusEffect(
    React.useCallback(() => {
      void reload();
    }, [reload]),
  );
  return (
    <Screen refresh={reload} refreshing={loading}>
      <View style={styles.between}>
        <View>
          <Text style={styles.muted}>Let's care for your health today.</Text>
          <Text style={styles.title}>
            {data?.profile.name
              ? `Hello, ${data.profile.name.split(" ")[0]}.`
              : "Welcome to SehatBridge."}
          </Text>
        </View>
        <Pressable
          accessibilityLabel="Reminder settings"
          accessibilityRole="button"
          style={{ padding: 12 }}
          onPress={() => router.push("/settings")}
        >
          <Icon name="notifications-outline" />
        </Pressable>
      </View>
      <Pressable
        accessibilityRole="button"
        onPress={() => router.push("/(tabs)/assistant")}
      >
        <Card>
          <View style={styles.row}>
            <Icon name="chatbubbles-outline" />
            <View style={{ flex: 1 }}>
              <Text style={styles.h3}>A question on your mind?</Text>
              <Text style={styles.muted}>Ask in Hindi or English.</Text>
            </View>
            <Icon name="mic-outline" color={colors.pink} />
          </View>
        </Card>
      </Pressable>
      <Card tint={colors.pinkSoft}>
        <Text style={styles.h3}>Your day, a little clearer.</Text>
        <Text style={styles.muted}>Today's confirmed medication schedule</Text>
        <View style={styles.between}>
          {[
            ["Taken", "taken"],
            ["Remaining", "upcoming"],
            ["Missed", "missed"],
          ].map(([label, key]) => (
            <View key={key}>
              <Text style={[styles.title, { color: colors.pink }]}>
                {data?.counts[key] ?? 0}
              </Text>
              <Text style={styles.muted}>{label}</Text>
            </View>
          ))}
        </View>
      </Card>
      <View style={styles.row}>
        <View style={{ flex: 1 }}>
          <Button
            title="Upload document"
            icon="scan-outline"
            onPress={() => router.push("/upload")}
          />
        </View>
        <View style={{ flex: 1 }}>
          <Button
            title="Documents"
            tone="soft"
            icon="documents-outline"
            onPress={() => router.push("/documents")}
          />
        </View>
      </View>
      {!!error && <Notice error>{error}</Notice>}
      {loading && !data && <Busy />}
      <View style={styles.between}>
        <Text style={styles.h2}>Today's medicines</Text>
        <Pressable
          onPress={() => router.push("/tracker")}
          accessibilityRole="button"
          style={{ padding: 10 }}
        >
          <Text style={{ color: colors.teal }}>View history</Text>
        </Pressable>
      </View>
      {data?.doses.map((d) => (
        <DoseRow key={d.id} dose={d} reload={reload} />
      ))}
      {data && !data.doses.length && (
        <Empty
          title="Your schedule starts here"
          text="Upload your medical document, review the extracted details and confirm your medicine times."
        />
      )}
      {data?.plans.map((t) => (
        <Pressable
          key={t.id}
          accessibilityRole="button"
          onPress={() => router.push(`/treatment/${t.id}`)}
        >
          <Card>
            <Text style={styles.h3}>
              {t.extraction.institution || "Confirmed treatment"}
            </Text>
            <Text numberOfLines={2} style={styles.muted}>
              {t.extraction.summary}
            </Text>
            {[...t.extraction.tests, ...t.extraction.follow_ups].map((f, i) => (
              <Text key={i} style={styles.muted}>
                {f.name} ·{" "}
                {f.date || f.time_window || "Date needs clarification"}
              </Text>
            ))}
          </Card>
        </Pressable>
      ))}
      <Text style={styles.h2}>Recent documents</Text>
      {data?.documents
        .slice(-3)
        .reverse()
        .map((d) => (
          <Button
            key={d.id}
            title={`${d.document_type} · ${d.status}`}
            tone="soft"
            onPress={() => router.push(`/document/${d.id}`)}
          />
        ))}
      {process.env.EXPO_PUBLIC_DEMO_ENABLED !== "false" && (
        <>
          <Text style={styles.h2}>Explore demonstration care</Text>
          <Text style={styles.muted}>
            Synthetic providers. No real booking or order.
          </Text>
          <View style={styles.row}>
            <View style={{ flex: 1 }}>
              <Button
                title="Appointments & labs"
                tone="soft"
                onPress={() => router.push("/(tabs)/appointments")}
              />
            </View>
            <View style={{ flex: 1 }}>
              <Button
                title="Pharmacy demo"
                tone="soft"
                onPress={() => router.push("/pharmacy")}
              />
            </View>
          </View>
        </>
      )}
    </Screen>
  );
}
