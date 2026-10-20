import React, { useState, useEffect, useRef, useCallback } from "react";
import { Text, View } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { useAuth } from "../src/auth";
import { api, post } from "../src/api";
import { Screen, Field, Button, Notice, styles, Toggle } from "../src/ui";
import { message } from "../src/hooks";
import Recaptcha, { RecaptchaRef } from "../src/Recaptcha";
import {
  CaptchaConfiguration,
  parseCaptchaConfiguration,
} from "../src/captchaPolicy";

export default function Authentication() {
  const params = useLocalSearchParams<{ mode?: string }>();
  const [mode, setMode] = useState(
    params.mode === "register" ? "register" : "login",
  );
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [purpose, setPurpose] = useState<"verify" | "reset">("verify");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [privacy, setPrivacy] = useState(false);
  const [security, setSecurity] = useState<CaptchaConfiguration | null>(null);
  const [securityLoading, setSecurityLoading] = useState(true);
  const [securityError, setSecurityError] = useState("");
  const [captchaToken, setCaptchaToken] = useState("");
  const captcha = useRef<RecaptchaRef>(null);
  const submitting = useRef(false);
  const auth = useAuth();
  const loadSecurity = useCallback(async () => {
    setSecurityLoading(true);
    setSecurityError("");
    try {
      setSecurity(
        parseCaptchaConfiguration(
          await api<unknown>("/auth/recaptcha-config"),
          __DEV__,
        ),
      );
    } catch (e) {
      setSecurity(null);
      setSecurityError(message(e));
    } finally {
      setSecurityLoading(false);
    }
  }, []);
  useEffect(() => {
    void loadSecurity();
  }, [loadSecurity]);
  useEffect(() => {
    captcha.current?.reset();
    setCaptchaToken("");
  }, [mode, purpose]);
  const securityReady =
    security !== null && (!security.enabled || !!captchaToken);
  function resetCaptcha() {
    setCaptchaToken("");
    captcha.current?.reset();
  }
  async function resend() {
    if (submitting.current) return;
    if (!securityReady) {
      setError("Complete the security check before requesting another code.");
      return;
    }
    submitting.current = true;
    setBusy(true);
    setError("");
    try {
      await post("/auth/otp/request", {
        email: email.trim(),
        purpose,
        recaptcha_token: captchaToken || null,
      });
      setInfo("If the account exists, a new verification code was requested.");
    } catch (e) {
      setError(message(e));
    } finally {
      resetCaptcha();
      submitting.current = false;
      setBusy(false);
    }
  }
  async function submit() {
    if (submitting.current) return;
    if (mode !== "otp" && !securityReady) {
      setError(
        "Load security settings and complete the Google checkbox first.",
      );
      return;
    }
    submitting.current = true;
    setBusy(true);
    setError("");
    setInfo("");
    try {
      if (mode === "register") {
        if (!privacy)
          throw new Error(
            "Please read and acknowledge the privacy explanation.",
          );
        await post("/auth/register", {
          email: email.trim(),
          password,
          recaptcha_token: captchaToken || null,
        });
        setPurpose("verify");
        setMode("otp");
        setInfo(
          "Check your email. If the development console provider is selected, the code appears in the backend terminal.",
        );
      } else if (mode === "recover") {
        await post("/auth/otp/request", {
          email: email.trim(),
          purpose: "reset",
          recaptcha_token: captchaToken || null,
        });
        setPurpose("reset");
        setMode("otp");
        setInfo("If your account exists, a reset code was sent.");
      } else {
        const tokens = await post<{
          access_token: string;
          refresh_token: string;
        }>(
          mode === "otp" ? "/auth/otp/verify" : "/auth/login",
          mode === "otp"
            ? {
                email: email.trim(),
                code,
                purpose,
                ...(purpose === "reset" ? { new_password: password } : {}),
              }
            : {
                email: email.trim(),
                password,
                recaptcha_token: captchaToken || null,
              },
        );
        await auth.accept(tokens);
        router.replace(mode === "otp" ? "/(tabs)/profile" : "/(tabs)");
      }
    } catch (e) {
      setError(message(e));
    } finally {
      if (mode !== "otp") resetCaptcha();
      submitting.current = false;
      setBusy(false);
    }
  }
  return (
    <Screen
      back
      title={
        mode === "register"
          ? "A healthier start."
          : mode === "otp"
            ? "Check your inbox."
            : mode === "recover"
              ? "Reset your password."
              : "Welcome back."
      }
      subtitle="Your records, together in one place."
    >
      <Field
        label="Email address"
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        keyboardType="email-address"
        autoComplete="email"
      />
      {(mode === "login" ||
        mode === "register" ||
        (mode === "otp" && purpose === "reset")) && (
        <Field
          label={
            purpose === "reset" && mode === "otp"
              ? "New password (12+ characters)"
              : "Password (12+ characters)"
          }
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          autoCapitalize="none"
          autoComplete={mode === "login" ? "current-password" : "new-password"}
        />
      )}
      {mode === "otp" && (
        <Field
          label="Six-digit verification code"
          keyboardType="number-pad"
          value={code}
          onChangeText={setCode}
          maxLength={6}
          autoComplete="one-time-code"
        />
      )}
      {mode === "register" && (
        <>
          <Notice>
            Medical documents are private and encrypted. If you choose AI
            processing, document pages are sent to Google's Gemini service under
            its provider privacy terms. Voice recognition may use your device's
            speech provider. SehatBridge does not retain raw audio. Review
            instructions with your clinician when unclear.
          </Notice>
          <Toggle
            label="I have read the privacy explanation"
            value={privacy}
            onChange={setPrivacy}
          />
        </>
      )}
      {!!info && <Notice>{info}</Notice>}
      {!!error && <Notice error>{error}</Notice>}
      {securityLoading && <Notice>Loading security settings…</Notice>}
      {!!securityError && (
        <>
          <Notice error>{securityError}</Notice>
          <Button
            title="Retry security settings"
            tone="soft"
            disabled={securityLoading || busy}
            onPress={() => void loadSecurity()}
          />
        </>
      )}
      {security?.enabled && security.page_url && (
        <Recaptcha
          ref={captcha}
          pageUrl={security.page_url}
          disabled={busy}
          onToken={setCaptchaToken}
          onError={setError}
        />
      )}
      {mode === "otp" && security?.enabled && (
        <Text style={styles.muted}>
          The security check above is required only when resending the email.
          Entering your existing OTP does not require another CAPTCHA.
        </Text>
      )}
      <Button
        title={
          mode === "otp"
            ? "Verify and continue"
            : mode === "register"
              ? "Create account"
              : mode === "recover"
                ? "Send reset code"
                : "Sign in"
        }
        loading={busy}
        disabled={mode !== "otp" && !securityReady}
        onPress={() => void submit()}
      />
      {mode === "otp" && (
        <Button
          title="Resend code (60-second cooldown)"
          tone="soft"
          disabled={!securityReady || busy}
          onPress={() => void resend()}
        />
      )}
      {mode === "login" && (
        <>
          <Button
            title="Forgot password?"
            tone="soft"
            onPress={() => {
              setMode("recover");
              setError("");
            }}
          />
          <Button
            title="Verify an existing account"
            tone="soft"
            onPress={() => {
              setMode("otp");
              setPurpose("verify");
            }}
          />
        </>
      )}
      <Button
        title={mode === "login" ? "Create an account" : "Back to sign in"}
        tone="soft"
        onPress={() => {
          setMode(mode === "login" ? "register" : "login");
          setError("");
          setInfo("");
        }}
      />
    </Screen>
  );
}
