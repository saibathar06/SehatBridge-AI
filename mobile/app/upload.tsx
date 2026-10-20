import React, { useState, useRef, useEffect } from "react";
import { Image, Text, View, Alert } from "react-native";
import * as DocumentPicker from "expo-document-picker";
import * as ImagePicker from "expo-image-picker";
import * as ImageManipulator from "expo-image-manipulator";
import { File, Paths } from "expo-file-system";
import { router } from "expo-router";
import { uploadDocument } from "../src/api";
import {
  Screen,
  Card,
  Button,
  Field,
  Toggle,
  Notice,
  Chip,
  Icon,
  styles,
  colors,
} from "../src/ui";
import { message } from "../src/hooks";
type FilePage = { uri: string; name: string; mime: string };
export default function Upload() {
  const [files, setFiles] = useState<FilePage[]>([]);
  const [kind, setKind] = useState("prescription");
  const [consent, setConsent] = useState(false);
  const [grouped, setGrouped] = useState(false);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const cached = useRef(new Set<string>());
  useEffect(() => {
    for (const file of files) cached.current.add(file.uri);
  }, [files]);
  useEffect(
    () => () => {
      // Only remove app-owned cache copies, never the patient's original gallery files.
      const prefix = Paths.cache.uri.endsWith("/")
        ? Paths.cache.uri
        : Paths.cache.uri + "/";
      for (const uri of cached.current)
        if (uri.startsWith(prefix)) {
          try {
            const file = new File(uri);
            if (file.exists) file.delete();
          } catch {
            /* OS cache cleanup is the fallback. */
          }
        }
    },
    [],
  );
  async function pickFiles() {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: ["application/pdf", "image/jpeg", "image/png"],
        multiple: true,
        copyToCacheDirectory: true,
      });
      if (!result.canceled) {
        setFiles((old) => [
          ...old,
          ...result.assets.map((a) => ({
            uri: a.uri,
            name: a.name,
            mime: a.mimeType || "application/pdf",
          })),
        ]);
        setGrouped(false);
      }
    } catch (e) {
      setError(message(e));
    }
  }
  async function pickImages(camera = false) {
    try {
      const permission = camera
        ? await ImagePicker.requestCameraPermissionsAsync()
        : await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!permission.granted)
        throw new Error(
          "Permission denied. Enable camera/photos in device settings or choose a file.",
        );
      const result = camera
        ? await ImagePicker.launchCameraAsync({
            mediaTypes: ["images"],
            quality: 1,
          })
        : await ImagePicker.launchImageLibraryAsync({
            mediaTypes: ["images"],
            allowsMultipleSelection: true,
            orderedSelection: true,
            quality: 1,
          });
      if (!result.canceled) {
        setFiles((old) => [
          ...old,
          ...result.assets.map((a, i) => ({
            uri: a.uri,
            name: a.fileName || `page-${Date.now()}-${i}.jpg`,
            mime: a.mimeType || "image/jpeg",
          })),
        ]);
        setGrouped(false);
      }
    } catch (e) {
      setError(message(e));
    }
  }
  function move(i: number, direction: number) {
    setFiles((old) => {
      const next = [...old];
      [next[i], next[i + direction]] = [next[i + direction], next[i]];
      return next;
    });
  }
  async function rotate(i: number) {
    try {
      const result = await ImageManipulator.manipulateAsync(
        files[i].uri,
        [{ rotate: 90 }],
        { compress: 0.95, format: ImageManipulator.SaveFormat.JPEG },
      );
      setFiles((old) =>
        old.map((f, n) =>
          n === i
            ? {
                ...f,
                uri: result.uri,
                mime: "image/jpeg",
                name: `rotated-${i}.jpg`,
              }
            : f,
        ),
      );
    } catch (e) {
      setError(message(e));
    }
  }
  async function send() {
    if (!grouped || !consent || !files.length) {
      setError("Confirm the page group and AI processing consent first.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const form = new FormData();
      form.append("document_type", kind);
      form.append("ai_consent", "true");
      for (const f of files)
        form.append("files", {
          uri: f.uri,
          name: f.name,
          type: f.mime,
        } as unknown as Blob);
      const doc = await uploadDocument(form, setProgress);
      router.replace(`/document/${doc.id}`);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Screen
      back
      title="Bring your records."
      subtitle="One prescription or discharge summary per upload group."
    >
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
        {[
          ["prescription", "Prescription"],
          ["discharge", "Discharge summary"],
          ["laboratory", "Lab report"],
          ["other", "Other"],
        ].map(([id, label]) => (
          <Chip
            key={id}
            label={label}
            selected={kind === id}
            onPress={() => setKind(id)}
          />
        ))}
      </View>
      <Card>
        <View style={{ alignItems: "center", padding: 20, gap: 12 }}>
          <Icon name="scan-outline" size={54} color={colors.pink} />
          <Text style={styles.h3}>A clearer picture of your care.</Text>
          <Text style={[styles.muted, { textAlign: "center" }]}>
            PDF, JPG or PNG · up to 20 MB per group · 40 pages. Include the
            entire page in good light.
          </Text>
        </View>
        <Button
          title="Take a photo"
          icon="camera-outline"
          onPress={() => void pickImages(true)}
          disabled={busy}
        />
        <Button
          title="Select photos"
          tone="soft"
          onPress={() => void pickImages()}
          disabled={busy}
        />
        <Button
          title="Choose PDF or image files"
          tone="soft"
          onPress={() => void pickFiles()}
          disabled={busy}
        />
      </Card>
      {files.map((f, i) => (
        <Card key={`${i}:${f.uri}`}>
          <Text style={styles.h3}>
            Page {i + 1}
            {f.mime === "application/pdf"
              ? " · PDF (internal order preserved)"
              : ""}
          </Text>
          {f.mime !== "application/pdf" ? (
            <Image
              source={{ uri: f.uri }}
              accessibilityLabel={`Selected document page ${i + 1}`}
              style={{
                width: "100%",
                height: 190,
                resizeMode: "contain",
                borderRadius: 12,
              }}
            />
          ) : (
            <Icon name="document-text-outline" size={54} />
          )}
          <Text numberOfLines={1} style={styles.muted}>
            {f.name}
          </Text>
          <View style={styles.row}>
            <View style={{ flex: 1 }}>
              <Button
                title="Move up"
                tone="soft"
                disabled={i === 0 || busy}
                onPress={() => move(i, -1)}
              />
            </View>
            <View style={{ flex: 1 }}>
              <Button
                title="Move down"
                tone="soft"
                disabled={i === files.length - 1 || busy}
                onPress={() => move(i, 1)}
              />
            </View>
          </View>
          {f.mime !== "application/pdf" && (
            <Button
              title="Rotate 90°"
              tone="soft"
              disabled={busy}
              onPress={() => void rotate(i)}
            />
          )}
          <Button
            title="Remove page"
            tone="soft"
            disabled={busy}
            onPress={() => {
              setFiles((old) => old.filter((_, n) => n !== i));
              setGrouped(false);
            }}
          />
        </Card>
      ))}
      <Toggle
        label="These pages belong to one document"
        value={grouped}
        onChange={setGrouped}
        description="Upload a separate prescription as a separate group."
      />
      <Notice>
        Document pages will be processed by Google's Gemini service. Its
        provider privacy terms apply. AI can misread handwriting; review every
        instruction before confirming. Do not upload documents you are not
        authorized to share.
      </Notice>
      <Toggle
        label="I agree to AI processing of this document"
        value={consent}
        onChange={setConsent}
      />
      {busy && (
        <Text style={styles.muted}>
          Uploading {Math.round(progress * 100)}% · processing continues on the
          server
        </Text>
      )}
      {!!error && <Notice error>{error}</Notice>}
      <Button
        title="Upload & understand"
        loading={busy}
        disabled={!files.length || !grouped || !consent}
        onPress={() => void send()}
      />
    </Screen>
  );
}
