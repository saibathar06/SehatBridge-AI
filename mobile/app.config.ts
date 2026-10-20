import type { ExpoConfig } from "expo/config";

const config: ExpoConfig = {
  name: "SehatBridge AI",
  slug: "sehatbridge-ai",
  scheme: "sehatbridge",
  version: "1.0.0",
  orientation: "portrait",
  userInterfaceStyle: "light",
  platforms: ["android", "ios"],
  android: {
    package: "com.sehatbridge.patient",
    ...(process.env.GOOGLE_SERVICES_JSON
      ? { googleServicesFile: process.env.GOOGLE_SERVICES_JSON }
      : {}),
    permissions: ["RECORD_AUDIO", "POST_NOTIFICATIONS"],
    blockedPermissions: ["android.permission.READ_MEDIA_AUDIO"],
  },
  plugins: [
    "expo-router",
    "expo-secure-store",
    "expo-document-picker",
    [
      "expo-image-picker",
      {
        photosPermission: "Select medical document pages to upload.",
        cameraPermission: "Photograph medical document pages.",
        microphonePermission: false,
      },
    ],
    ["expo-notifications", { color: "#EF4279" }],
    [
      "expo-speech-recognition",
      {
        microphonePermission: "Use the microphone for push-to-talk questions.",
        speechRecognitionPermission:
          "Recognize Hindi or English questions. Your device speech provider may process audio.",
      },
    ],
  ],
  extra: {
    eas: { projectId: process.env.EXPO_PUBLIC_EAS_PROJECT_ID || undefined },
  },
};
export default config;
