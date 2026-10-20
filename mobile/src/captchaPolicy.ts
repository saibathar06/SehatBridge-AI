export type CaptchaConfiguration = {
  enabled: boolean;
  type: "v2_checkbox";
  page_url: string | null;
};

export function parseCaptchaConfiguration(
  value: unknown,
  allowHttp: boolean,
): CaptchaConfiguration {
  if (!value || typeof value !== "object")
    throw new Error("Invalid security configuration");
  const config = value as Record<string, unknown>;
  if (typeof config.enabled !== "boolean" || config.type !== "v2_checkbox")
    throw new Error("Invalid security configuration");
  if (!config.enabled)
    return { enabled: false, type: "v2_checkbox", page_url: null };
  if (typeof config.page_url !== "string")
    throw new Error("Security page is missing");
  const url = new URL(config.page_url);
  if (
    (url.protocol !== "https:" && !(allowHttp && url.protocol === "http:")) ||
    !url.hostname ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    url.pathname !== "/api/v1/auth/mobile-recaptcha"
  ) {
    throw new Error("Invalid security page address");
  }
  return { enabled: true, type: "v2_checkbox", page_url: url.href };
}

export function isCaptchaDocument(url: string, pageUrl: string): boolean {
  try {
    const actual = new URL(url),
      expected = new URL(pageUrl);
    return (
      actual.origin === expected.origin &&
      actual.pathname === expected.pathname &&
      !actual.username &&
      !actual.password &&
      !actual.search &&
      !actual.hash
    );
  } catch {
    return false;
  }
}

export function isCaptchaMessage(
  url: string,
  documentUrl: string,
  pageUrl: string,
): boolean {
  if (!isCaptchaDocument(documentUrl, pageUrl)) return false;
  if (isCaptchaDocument(url, pageUrl)) return true;
  // Some Android WebView versions report only the document origin for bridge messages.
  try {
    const actual = new URL(url),
      expected = new URL(pageUrl);
    return (
      actual.origin === expected.origin &&
      actual.pathname === "/" &&
      !actual.username &&
      !actual.password &&
      !actual.search &&
      !actual.hash
    );
  } catch {
    return false;
  }
}

export const GOOGLE_CAPTCHA_ORIGINS = [
  "https://www.google.com",
  "https://recaptcha.google.com",
  "https://www.gstatic.com",
];

export function allowCaptchaNavigation(
  url: string,
  pageUrl: string,
  isTopFrame?: boolean,
): boolean {
  if (isCaptchaDocument(url, pageUrl)) return true;
  if (isTopFrame === true) return false;
  try {
    const parsed = new URL(url);
    return (
      !parsed.username &&
      !parsed.password &&
      GOOGLE_CAPTCHA_ORIGINS.includes(parsed.origin) &&
      parsed.pathname.startsWith("/recaptcha/")
    );
  } catch {
    return false;
  }
}

export type CaptchaMessage =
  { type: "token"; token: string } | { type: "ready" | "expired" | "error" };
export function parseCaptchaMessage(raw: string): CaptchaMessage | null {
  if (raw.length > 5000) return null;
  try {
    const value = JSON.parse(raw);
    if (
      value?.type === "token" &&
      typeof value.token === "string" &&
      value.token.length >= 20 &&
      value.token.length <= 4096
    )
      return { type: "token", token: value.token };
    if (["ready", "expired", "error"].includes(value?.type))
      return { type: value.type };
  } catch {
    /* Ignore malformed bridge messages. */
  }
  return null;
}
