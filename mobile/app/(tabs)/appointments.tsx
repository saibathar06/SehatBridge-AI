import React, { useState } from "react";
import { Text, View } from "react-native";
import { useLoad, message } from "../../src/hooks";
import { api, post } from "../../src/api";
import {
  Screen,
  Card,
  Button,
  Notice,
  Busy,
  Chip,
  Field,
  styles,
} from "../../src/ui";
type Provider = {
  id: string;
  name: string;
  kind: string;
  specialty?: string;
  languages: string[];
  tests?: string[];
};
type Booking = {
  id: string;
  status: string;
  provider: string;
  starts: string;
  kind: string;
};
export default function Appointments() {
  const [kind, setKind] = useState("doctor");
  const [language, setLanguage] = useState("");
  const [search, setSearch] = useState("");
  const providers = useLoad<Provider[]>(
    `/demo/providers?kind=${kind}${language ? "&language=" + language : ""}`,
  );
  const bookings = useLoad<Booking[]>("/demo/bookings");
  const [slots, setSlots] = useState<{ id: string; starts: string }[]>([]);
  const [selected, setSelected] = useState<Provider | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState("");
  async function select(p: Provider) {
    setError("");
    setBusy(true);
    try {
      setSlots(await api(`/demo/providers/${p.id}/slots`));
      setSelected(p);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  async function book(slotId: string) {
    setBusy(true);
    setError("");
    try {
      await post("/demo/bookings", { slot_id: slotId });
      setInfo(
        "Demonstration booking saved — no real appointment or laboratory booking has been made.",
      );
      setSelected(null);
      await bookings.reload();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Screen
      title="Care, when you need it."
      subtitle="Explore the appointment and laboratory demonstration."
    >
      <Notice>
        Demonstration only — synthetic providers and availability. No real
        appointment or laboratory booking will be made.
      </Notice>
      {process.env.EXPO_PUBLIC_DEMO_ENABLED === "false" ? (
        <Notice>Demonstration features are disabled for this build.</Notice>
      ) : (
        <>
          <View style={styles.row}>
            <Chip
              label="Doctor visit"
              selected={kind === "doctor"}
              onPress={() => {
                setKind("doctor");
                setSelected(null);
              }}
            />
            <Chip
              label="Lab tests"
              selected={kind === "laboratory"}
              onPress={() => {
                setKind("laboratory");
                setSelected(null);
              }}
            />
          </View>
          <Field
            label="Search provider or specialty"
            value={search}
            onChangeText={setSearch}
          />
          <View style={styles.row}>
            <Chip
              label="All languages"
              selected={!language}
              onPress={() => setLanguage("")}
            />
            <Chip
              label="Hindi"
              selected={language === "Hindi"}
              onPress={() => setLanguage("Hindi")}
            />
            <Chip
              label="English"
              selected={language === "English"}
              onPress={() => setLanguage("English")}
            />
          </View>
          {!!(error || providers.error || bookings.error) && (
            <Notice error>{error || providers.error || bookings.error}</Notice>
          )}
          {!!info && <Notice>{info}</Notice>}
          {providers.loading && <Busy />}
          {providers.data
            ?.filter((p) =>
              `${p.name} ${p.specialty || ""}`
                .toLowerCase()
                .includes(search.toLowerCase()),
            )
            .map((p) => (
              <Card key={p.id}>
                <Text style={styles.h3}>{p.name}</Text>
                <Text style={styles.muted}>
                  {p.specialty || p.tests?.join(" · ")}
                </Text>
                <Text style={styles.muted}>
                  {p.languages.join(" · ")} · synthetic provider
                </Text>
                <Button
                  title="View profile & demonstration slots"
                  tone="soft"
                  loading={busy}
                  onPress={() => void select(p)}
                />
              </Card>
            ))}
          {selected && (
            <Card>
              <Text style={styles.h3}>{selected.name}</Text>
              {slots.length ? (
                slots.map((s) => (
                  <Button
                    key={s.id}
                    title={new Date(s.starts).toLocaleString()}
                    tone="soft"
                    loading={busy}
                    onPress={() => void book(s.id)}
                  />
                ))
              ) : (
                <Text style={styles.muted}>
                  No demonstration slots available.
                </Text>
              )}
            </Card>
          )}
          <Text style={styles.h2}>Your demonstration bookings</Text>
          {bookings.data?.map((b) => (
            <Card key={b.id}>
              <Text style={styles.h3}>{b.provider}</Text>
              <Text style={styles.muted}>
                {new Date(b.starts).toLocaleString()} · {b.status}
              </Text>
              <Text style={styles.muted}>
                Demonstration booking — no real appointment has been made.
              </Text>
              {b.status === "booked" && (
                <Button
                  title="Cancel demonstration booking"
                  tone="soft"
                  onPress={() => {
                    void api(`/demo/bookings/${b.id}`, { method: "DELETE" })
                      .then(bookings.reload)
                      .catch((e) => setError(message(e)));
                  }}
                />
              )}
            </Card>
          ))}
        </>
      )}
    </Screen>
  );
}
