// Adapted from the user's AntarTalk checkbox modal; no AntarTalk keys/configuration are reused.
import React, {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import { ActivityIndicator, Linking, Modal, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { WebView } from "react-native-webview";
import { Button, Card, colors, Notice, styles } from "./ui";
import {
  allowCaptchaNavigation,
  GOOGLE_CAPTCHA_ORIGINS,
  isCaptchaDocument,
  isCaptchaMessage,
  parseCaptchaMessage,
} from "./captchaPolicy";

export type RecaptchaRef = { reset: () => void };
type Props = {
  pageUrl: string;
  onToken: (value: string) => void;
  onError: (message: string) => void;
  disabled?: boolean;
};

const Recaptcha = forwardRef<RecaptchaRef, Props>(
  ({ pageUrl, onToken, onError, disabled }, ref) => {
    const [visible, setVisible] = useState(false);
    const [verified, setVerified] = useState(false);
    const [ready, setReady] = useState(false);
    const [failed, setFailed] = useState(false);
    const [generation, setGeneration] = useState(0);
    const expiration = useRef<ReturnType<typeof setTimeout> | null>(null);
    const documentUrl = useRef("");
    const active = useRef(false);
    const activeGeneration = useRef(0);
    const callbacks = useRef({ onToken, onError });
    callbacks.current = { onToken, onError };
    const insets = useSafeAreaInsets();
    const clear = useCallback(() => {
      if (expiration.current) clearTimeout(expiration.current);
      expiration.current = null;
      setVerified(false);
      callbacks.current.onToken("");
    }, []);
    const fail = useCallback(() => {
      active.current = false;
      clear();
      setReady(false);
      setFailed(true);
      callbacks.current.onError(
        "Unable to load Google security verification. Check your connection and retry.",
      );
    }, [clear]);
    useEffect(
      () => () => {
        if (expiration.current) clearTimeout(expiration.current);
      },
      [],
    );
    useEffect(() => {
      if (!visible || ready || failed) return;
      const timer = setTimeout(fail, 30000);
      return () => clearTimeout(timer);
    }, [visible, ready, failed, generation, fail]);
    useImperativeHandle(
      ref,
      () => ({
        reset: () => {
          active.current = false;
          clear();
          setVisible(false);
          setFailed(false);
          documentUrl.current = "";
        },
      }),
      [clear],
    );
    const open = () => {
      if (disabled) return;
      clear();
      active.current = true;
      documentUrl.current = pageUrl;
      setReady(false);
      setFailed(false);
      activeGeneration.current += 1;
      setGeneration(activeGeneration.current);
      setVisible(true);
    };
    const close = () => {
      active.current = false;
      documentUrl.current = "";
      setVisible(false);
    };
    return (
      <Card>
        <Text style={styles.h3}>
          {verified ? "Security check complete" : "Google security check"}
        </Text>
        <Text style={styles.muted}>
          Complete Google's “I'm not a robot” checkbox before sending this
          request.
        </Text>
        <Button
          title={
            verified ? "Repeat security check" : "Open checkbox verification"
          }
          tone="soft"
          disabled={disabled}
          onPress={open}
        />
        <Modal visible={visible} animationType="slide" onRequestClose={close}>
          <View
            style={{
              flex: 1,
              backgroundColor: colors.bg,
              paddingTop: insets.top,
              paddingBottom: insets.bottom,
            }}
          >
            <View style={{ padding: 16, gap: 12 }}>
              <Text accessibilityRole="header" style={styles.h2}>
                Security verification
              </Text>
              <Text style={styles.muted}>
                Complete the checkbox and any image or audio challenge. This
                window closes when the check succeeds.
              </Text>
              <Button title="Close" tone="soft" onPress={close} />
            </View>
            {!ready && !failed && (
              <ActivityIndicator
                accessibilityLabel="Connecting to Google"
                color={colors.pink}
                style={{ margin: 12 }}
              />
            )}
            {failed ? (
              <View style={{ padding: 22, gap: 16 }}>
                <Notice error>
                  Google's security check could not load. Check your connection
                  and the configured reCAPTCHA domain.
                </Notice>
                <Button title="Retry security check" onPress={open} />
              </View>
            ) : visible ? (
              <WebView
                key={generation}
                source={{ uri: pageUrl }}
                style={{ flex: 1, backgroundColor: colors.bg }}
                originWhitelist={[
                  new URL(pageUrl).origin,
                  ...GOOGLE_CAPTCHA_ORIGINS,
                ]}
                javaScriptEnabled
                domStorageEnabled
                thirdPartyCookiesEnabled
                sharedCookiesEnabled={false}
                allowFileAccess={false}
                allowUniversalAccessFromFileURLs={false}
                mixedContentMode="never"
                setSupportMultipleWindows={false}
                onShouldStartLoadWithRequest={(request) =>
                  allowCaptchaNavigation(
                    request.url,
                    pageUrl,
                    request.isTopFrame,
                  )
                }
                onLoadStart={(event) => {
                  documentUrl.current = event.nativeEvent.url;
                }}
                onError={fail}
                onHttpError={(event) => {
                  if (isCaptchaDocument(event.nativeEvent.url, pageUrl)) fail();
                }}
                onMessage={(event) => {
                  if (
                    !active.current ||
                    generation !== activeGeneration.current
                  )
                    return;
                  if (
                    !isCaptchaMessage(
                      event.nativeEvent.url,
                      documentUrl.current,
                      pageUrl,
                    )
                  )
                    return;
                  const data = parseCaptchaMessage(event.nativeEvent.data);
                  if (!data) return;
                  if (data.type === "ready") setReady(true);
                  else if (data.type === "token") {
                    clear();
                    setVerified(true);
                    callbacks.current.onToken(data.token);
                    active.current = false;
                    setVisible(false);
                    expiration.current = setTimeout(clear, 110000);
                  } else if (data.type === "expired") clear();
                  else fail();
                }}
              />
            ) : null}
            <View style={{ padding: 16, gap: 8 }}>
              <Text style={styles.muted}>
                Protected by Google reCAPTCHA. Your token is checked by
                SehatBridge's server.
              </Text>
              <Text
                accessibilityRole="link"
                onPress={() =>
                  void Linking.openURL("https://policies.google.com/privacy")
                }
                style={{ color: colors.teal }}
              >
                Google Privacy Policy
              </Text>
              <Text
                accessibilityRole="link"
                onPress={() =>
                  void Linking.openURL("https://policies.google.com/terms")
                }
                style={{ color: colors.teal }}
              >
                Google Terms of Service
              </Text>
            </View>
          </View>
        </Modal>
      </Card>
    );
  },
);
Recaptcha.displayName = "Recaptcha";
export default Recaptcha;
