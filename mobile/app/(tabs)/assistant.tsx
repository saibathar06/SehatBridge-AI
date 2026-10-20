import React, { useEffect, useState } from "react";
import { Text, View } from "react-native";
import * as Speech from "expo-speech";
import {
  ExpoSpeechRecognitionModule,
  useSpeechRecognitionEvent,
} from "expo-speech-recognition";
import { Answer, Treatment } from "../../src/types";
import { api, post } from "../../src/api";
import { useAuth } from "../../src/auth";
import { useLoad, message } from "../../src/hooks";
import {
  Screen,
  Card,
  Field,
  Button,
  Chip,
  Notice,
  styles,
  colors,
  Icon,
} from "../../src/ui";

type Message = { question: string; response: Answer; language: "hi" | "en" };
export default function Assistant() {
  const { profile } = useAuth();
  const [language, setLanguage] = useState<"hi" | "en">(
    profile?.language || "hi",
  );
  const [transcript, setTranscript] = useState("");
  const [listening, setListening] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [speakAnswers, setSpeakAnswers] = useState(true);
  const [doc, setDoc] = useState<string | null>(null);
  const treatments = useLoad<Treatment[]>("/treatments");
  useSpeechRecognitionEvent("start", () => setListening(true));
  useSpeechRecognitionEvent("end", () => setListening(false));
  useSpeechRecognitionEvent("result", (event) => {
    if (event.results[0]?.transcript)
      setTranscript(event.results[0].transcript);
  });
  useSpeechRecognitionEvent("error", (event) => {
    setListening(false);
    setError(
      `Speech recognition: ${event.error}. Check microphone permission, network and the selected language pack, then retry.`,
    );
  });
  useEffect(() => {
    if (profile?.chat_history)
      void api<
        {
          question: string;
          answer: string;
          route: string;
          sources: Answer["sources"];
          language: "hi" | "en";
        }[]
      >("/chat")
        .then((data) =>
          setMessages(
            data.map((m) => ({
              question: m.question,
              response: {
                answer: m.answer,
                route: m.route,
                sources: m.sources,
              },
              language: m.language,
            })),
          ),
        )
        .catch((e) => setError(message(e)));
    return () => {
      ExpoSpeechRecognitionModule.abort();
      void Speech.stop();
    };
  }, []);
  async function start() {
    setError("");
    try {
      await Speech.stop();
      const result =
        await ExpoSpeechRecognitionModule.requestPermissionsAsync();
      if (!result.granted)
        throw new Error(
          "Microphone or speech permission denied. Enable access in device settings. You can also type your question.",
        );
      if (!ExpoSpeechRecognitionModule.isRecognitionAvailable())
        throw new Error(
          "Speech recognition is unavailable. Install or enable an Android speech service and the Hindi/English language pack.",
        );
      ExpoSpeechRecognitionModule.start({
        lang: language === "hi" ? "hi-IN" : "en-IN",
        interimResults: true,
        continuous: false,
        maxAlternatives: 1,
      });
    } catch (e) {
      setError(message(e));
    }
  }
  async function speak(text: string, lang: "hi" | "en") {
    try {
      await Speech.stop();
      const voices = await Speech.getAvailableVoicesAsync();
      const voice = voices.find((v) => v.language.startsWith(lang));
      if (!voice)
        throw new Error(
          `No ${lang === "hi" ? "Hindi" : "English"} voice installed. Add a text-to-speech voice in Android settings.`,
        );
      Speech.speak(text, {
        language: lang === "hi" ? "hi-IN" : "en-IN",
        voice: voice.identifier,
        rate: 0.9,
        onError: () =>
          setError(
            "Speech playback failed. Check your Android text-to-speech engine and language pack.",
          ),
      });
    } catch (e) {
      setError(message(e));
    }
  }
  async function send() {
    if (!transcript.trim() || busy) return;
    setBusy(true);
    setError("");
    ExpoSpeechRecognitionModule.stop();
    try {
      const response = await post<Answer>("/chat", {
        question: transcript.trim(),
        language,
        document_id: doc,
      });
      setMessages((old) => [
        ...old,
        { question: transcript.trim(), response, language },
      ]);
      setTranscript("");
      if (speakAnswers) await speak(response.answer, language);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Screen
      title="A little understanding."
      subtitle="Ask SehatBridge AI about your confirmed records."
    >
      <View style={styles.row}>
        <Chip
          label="हिन्दी"
          selected={language === "hi"}
          onPress={() => {
            ExpoSpeechRecognitionModule.stop();
            setLanguage("hi");
          }}
        />
        <Chip
          label="English"
          selected={language === "en"}
          onPress={() => {
            ExpoSpeechRecognitionModule.stop();
            setLanguage("en");
          }}
        />
        <Chip
          label={speakAnswers ? "Voice on" : "Voice off"}
          selected={speakAnswers}
          onPress={() => {
            setSpeakAnswers(!speakAnswers);
            void Speech.stop();
          }}
        />
      </View>
      <Notice>
        Push to talk, then review your transcript before sending. Device speech
        providers may process audio. SehatBridge does not store raw audio.
        Answers use your confirmed records; unclear medical instructions need
        professional verification.
      </Notice>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
        <Chip
          label="All confirmed records"
          selected={!doc}
          onPress={() => setDoc(null)}
        />
        {treatments.data?.map((t, i) => (
          <Chip
            key={t.id}
            label={`Document ${i + 1}`}
            selected={doc === t.document_id}
            onPress={() => setDoc(t.document_id)}
          />
        ))}
      </View>
      {!messages.length && (
        <Card tint={colors.tealSoft}>
          <Icon name="chatbubbles-outline" size={32} />
          <Text style={styles.h3}>Your records. Your questions.</Text>
          <Button
            title="मुझे आज कौन-कौन सी दवाई लेनी है और मेरा नेक्स्ट टेस्ट कब होगा?"
            tone="soft"
            onPress={() => {
              setLanguage("hi");
              setTranscript(
                "मुझे आज कौन-कौन सी दवाई लेनी है और मेरा नेक्स्ट टेस्ट कब होगा?",
              );
            }}
          />
          <Button
            title="Explain my discharge summary"
            tone="soft"
            onPress={() => {
              setLanguage("en");
              setTranscript("Explain my discharge summary");
            }}
          />
        </Card>
      )}
      {messages.map((m, i) => (
        <View key={i} style={{ gap: 10 }}>
          <View
            style={{
              alignSelf: "flex-end",
              backgroundColor: colors.pinkSoft,
              borderRadius: 20,
              padding: 16,
              maxWidth: "92%",
            }}
          >
            <Text style={styles.text}>{m.question}</Text>
          </View>
          <Card>
            <Text selectable style={styles.text}>
              {m.response.answer}
            </Text>
            <Text style={styles.muted}>
              {m.response.route === "structured_records"
                ? "From your confirmed records"
                : m.response.route === "document_explanation"
                  ? "AI explanation of confirmed records"
                  : "SehatBridge guidance"}
            </Text>
            {m.response.sources.map((s, n) => (
              <Text key={n} selectable style={styles.muted}>
                Page {s.page}: “{s.excerpt}”
              </Text>
            ))}
            <View style={styles.row}>
              <View style={{ flex: 1 }}>
                <Button
                  title="Play / replay"
                  icon="volume-high-outline"
                  tone="soft"
                  onPress={() => void speak(m.response.answer, m.language)}
                />
              </View>
              <View style={{ flex: 1 }}>
                <Button
                  title="Stop"
                  tone="soft"
                  onPress={() => void Speech.stop()}
                />
              </View>
            </View>
          </Card>
        </View>
      ))}
      {!!error && <Notice error>{error}</Notice>}
      <Card>
        <Text style={styles.h3}>
          {listening
            ? "Listening… tap Stop when ready."
            : "Ask in your own words."}
        </Text>
        <Button
          title={listening ? "Stop listening" : "Tap to speak"}
          icon={listening ? "stop-circle-outline" : "mic-outline"}
          tone={listening ? "teal" : "pink"}
          disabled={busy}
          onPress={() =>
            listening ? ExpoSpeechRecognitionModule.stop() : void start()
          }
        />
        <Field
          label="Review or correct your transcript"
          placeholder={
            language === "hi" ? "अपना सवाल लिखें…" : "Type your question…"
          }
          multiline
          value={transcript}
          onChangeText={setTranscript}
        />
        <Button
          title="Send reviewed question"
          loading={busy}
          disabled={!transcript.trim() || listening}
          onPress={() => void send()}
        />
      </Card>
      <Button
        title="Clear chat history"
        tone="soft"
        onPress={() => {
          void api("/chat", { method: "DELETE" })
            .then(() => {
              setMessages([]);
              void Speech.stop();
            })
            .catch((e) => setError(message(e)));
        }}
      />
    </Screen>
  );
}
