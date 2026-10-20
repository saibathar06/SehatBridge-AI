import React, { ReactNode } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TextInputProps,
  View,
  RefreshControl,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import Ionicons from "@expo/vector-icons/Ionicons";
import { router } from "expo-router";

export const colors = {
  pink: "#D92566",
  pinkSoft: "#FCE7EF",
  teal: "#087F75",
  tealSoft: "#E4F3EE",
  navy: "#172D3B",
  muted: "#61717C",
  bg: "#FFF9F7",
  line: "#EFEBE8",
  warning: "#805000",
};
export const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  scroll: { padding: 22, paddingBottom: 36, gap: 18 },
  row: { flexDirection: "row", alignItems: "center", gap: 12 },
  between: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
  },
  title: {
    fontSize: 29,
    fontWeight: "700",
    color: colors.navy,
    letterSpacing: -0.8,
  },
  h2: { fontSize: 20, fontWeight: "700", color: colors.navy },
  h3: { fontSize: 17, fontWeight: "700", color: colors.navy },
  text: { fontSize: 16, color: colors.navy, lineHeight: 24 },
  muted: { fontSize: 14, color: colors.muted, lineHeight: 21 },
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 22,
    padding: 18,
    borderWidth: 1,
    borderColor: colors.line,
    gap: 12,
    shadowColor: "#533B40",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.035,
    shadowRadius: 12,
    elevation: 1,
  },
  button: {
    minHeight: 52,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 18,
    paddingVertical: 12,
    flexDirection: "row",
    gap: 10,
  },
  input: {
    minHeight: 52,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#DADFE0",
    borderRadius: 14,
    padding: 14,
    color: colors.navy,
    fontSize: 16,
    textAlignVertical: "top",
  },
  badge: {
    borderRadius: 10,
    paddingVertical: 5,
    paddingHorizontal: 10,
    alignSelf: "flex-start",
    backgroundColor: colors.tealSoft,
  },
});
export function Icon({
  name,
  color = colors.teal,
  size = 24,
}: {
  name: React.ComponentProps<typeof Ionicons>["name"];
  color?: React.ComponentProps<typeof Ionicons>["color"] | null;
  size?: number;
}) {
  return <Ionicons name={name} color={color ?? colors.teal} size={size} />;
}
export function Screen({
  children,
  title,
  subtitle,
  back,
  refresh,
  refreshing = false,
}: {
  children: ReactNode;
  title?: string;
  subtitle?: string;
  back?: boolean;
  refresh?: () => void;
  refreshing?: boolean;
}) {
  return (
    <SafeAreaView edges={["top", "left", "right"]} style={styles.safe}>
      <ScrollView
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={styles.scroll}
        refreshControl={
          refresh ? (
            <RefreshControl
              refreshing={refreshing}
              onRefresh={refresh}
              tintColor={colors.pink}
            />
          ) : undefined
        }
      >
        {back && (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Go back"
            onPress={() => router.back()}
            style={{
              minHeight: 44,
              justifyContent: "center",
              alignSelf: "flex-start",
              paddingRight: 22,
            }}
          >
            <Icon name="arrow-back" color={colors.navy} />
          </Pressable>
        )}
        {title && (
          <View style={{ gap: 6 }}>
            <Text accessibilityRole="header" style={styles.title}>
              {title}
            </Text>
            {subtitle && <Text style={styles.muted}>{subtitle}</Text>}
          </View>
        )}
        {children}
      </ScrollView>
    </SafeAreaView>
  );
}
export function Card({
  children,
  tint,
}: {
  children: ReactNode;
  tint?: string;
}) {
  return (
    <View style={[styles.card, tint ? { backgroundColor: tint } : {}]}>
      {children}
    </View>
  );
}
export function Button({
  title,
  onPress,
  tone = "pink",
  disabled,
  loading,
  icon,
}: {
  title: string;
  onPress: () => void;
  tone?: "pink" | "teal" | "soft" | "danger";
  disabled?: boolean;
  loading?: boolean;
  icon?: React.ComponentProps<typeof Ionicons>["name"];
}) {
  const bg = {
    pink: colors.pink,
    teal: colors.teal,
    soft: colors.tealSoft,
    danger: "#B3293B",
  }[tone];
  const foreground = tone === "soft" ? colors.teal : "#FFFFFF";
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: !!disabled || !!loading }}
      disabled={disabled || loading}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        {
          backgroundColor: bg,
          opacity: disabled || loading ? 0.5 : pressed ? 0.8 : 1,
        },
      ]}
    >
      {loading ? (
        <ActivityIndicator color={foreground} />
      ) : (
        icon && <Icon name={icon} color={foreground} size={21} />
      )}
      <Text
        style={{
          color: foreground,
          fontSize: 16,
          fontWeight: "700",
          textAlign: "center",
        }}
      >
        {title}
      </Text>
    </Pressable>
  );
}
export function Field({ label, ...props }: TextInputProps & { label: string }) {
  return (
    <View style={{ gap: 7 }}>
      <Text style={styles.muted}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        placeholderTextColor="#849098"
        {...props}
        style={[
          styles.input,
          props.multiline && { minHeight: 92 },
          props.style,
        ]}
      />
    </View>
  );
}
export function Notice({
  children,
  error = false,
}: {
  children: ReactNode;
  error?: boolean;
}) {
  return (
    <View
      accessibilityRole={error ? "alert" : undefined}
      style={{
        backgroundColor: error ? "#FFF0E0" : colors.tealSoft,
        borderRadius: 15,
        padding: 15,
      }}
    >
      <Text
        style={[styles.muted, { color: error ? colors.warning : "#176354" }]}
      >
        {children}
      </Text>
    </View>
  );
}
export function Empty({ title, text }: { title: string; text: string }) {
  return (
    <Card>
      <Icon name="folder-open-outline" size={32} />
      <Text style={styles.h3}>{title}</Text>
      <Text style={styles.muted}>{text}</Text>
    </Card>
  );
}
export function Busy() {
  return (
    <ActivityIndicator
      style={{ padding: 30 }}
      color={colors.pink}
      size="large"
    />
  );
}
export function Toggle({
  label,
  value,
  onChange,
  description,
}: {
  label: string;
  value: boolean;
  onChange: (v: boolean) => void;
  description?: string;
}) {
  return (
    <Pressable
      accessibilityRole="checkbox"
      accessibilityState={{ checked: value }}
      onPress={() => onChange(!value)}
      style={[styles.row, { minHeight: 48, paddingVertical: 8 }]}
    >
      <Icon
        name={value ? "checkbox" : "square-outline"}
        color={value ? colors.teal : colors.muted}
      />
      <View style={{ flex: 1 }}>
        <Text style={styles.text}>{label}</Text>
        {description && <Text style={styles.muted}>{description}</Text>}
      </View>
    </Pressable>
  );
}
export function Chip({
  label,
  selected,
  onPress,
}: {
  label: string;
  selected?: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={{
        minHeight: 44,
        justifyContent: "center",
        paddingHorizontal: 14,
        borderRadius: 12,
        backgroundColor: selected ? colors.teal : "#F2EFED",
      }}
    >
      <Text
        style={{ color: selected ? "white" : colors.navy, fontWeight: "600" }}
      >
        {label}
      </Text>
    </Pressable>
  );
}
