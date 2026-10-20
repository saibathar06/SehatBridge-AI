import { test } from "node:test";
import assert from "node:assert/strict";
import {
  allowCaptchaNavigation,
  isCaptchaDocument,
  isCaptchaMessage,
  parseCaptchaConfiguration,
  parseCaptchaMessage,
} from "../src/captchaPolicy";

const page = "https://api.example.test/api/v1/auth/mobile-recaptcha";
test("server security config fails closed on missing/malformed flags and unsafe page URLs", () => {
  for (const config of [
    {},
    { enabled: "false" },
    { enabled: true, type: "v2_checkbox", page_url: "javascript:alert(1)" },
    {
      enabled: true,
      type: "v2_checkbox",
      page_url: "https://api.example.test/other",
    },
    {
      enabled: true,
      type: "v2_checkbox",
      page_url:
        "https://user:password@api.example.test/api/v1/auth/mobile-recaptcha",
    },
  ]) {
    assert.throws(() => parseCaptchaConfiguration(config, false));
  }
  assert.equal(
    parseCaptchaConfiguration(
      { enabled: false, type: "v2_checkbox", page_url: null },
      false,
    ).enabled,
    false,
  );
});
test("release rejects HTTP; development allows an explicitly configured localhost page", () => {
  const value = {
    enabled: true,
    type: "v2_checkbox",
    page_url: "http://localhost:8000/api/v1/auth/mobile-recaptcha",
  };
  assert.throws(() => parseCaptchaConfiguration(value, false));
  assert.equal(parseCaptchaConfiguration(value, true).page_url, value.page_url);
});
test("bridge accepts only the exact loaded page or its Android-reported origin", () => {
  assert.ok(isCaptchaMessage(page, page, page));
  assert.ok(isCaptchaMessage("https://api.example.test", page, page));
  for (const url of [
    "https://evil.test",
    page + "/evil",
    page + "?injected=true",
    "https://www.google.com/recaptcha/api2/anchor",
    "https://user@api.example.test/",
  ]) {
    assert.equal(isCaptchaMessage(url, page, page), false);
  }
  assert.equal(
    isCaptchaMessage(page, "https://api.example.test/other", page),
    false,
  );
  assert.equal(isCaptchaDocument(page + "#injected", page), false);
});
test("Google challenge frames are allowed while external top-level navigation is denied", () => {
  assert.ok(allowCaptchaNavigation(page, page, true));
  assert.ok(
    allowCaptchaNavigation(
      "https://www.google.com/recaptcha/api2/bframe",
      page,
      false,
    ),
  );
  assert.equal(
    allowCaptchaNavigation(
      "https://www.google.com/recaptcha/api2/bframe",
      page,
      true,
    ),
    false,
  );
  for (const url of [
    "https://evil.test",
    "https://www.google.com/search",
    "file:///private/data",
    "http://www.google.com/recaptcha/anchor",
  ])
    assert.equal(allowCaptchaNavigation(url, page, false), false);
});
test("bridge tokens are bounded and expiry/errors have explicit event types", () => {
  assert.deepEqual(
    parseCaptchaMessage(
      JSON.stringify({
        type: "token",
        token: "synthetic-token-for-unit-testing",
      }),
    ),
    { type: "token", token: "synthetic-token-for-unit-testing" },
  );
  assert.equal(
    parseCaptchaMessage(JSON.stringify({ type: "token", token: "short" })),
    null,
  );
  assert.equal(
    parseCaptchaMessage(
      JSON.stringify({ type: "token", token: "a".repeat(4097) }),
    ),
    null,
  );
  assert.equal(parseCaptchaMessage("unreadable"), null);
  assert.deepEqual(parseCaptchaMessage('{"type":"expired"}'), {
    type: "expired",
  });
  assert.deepEqual(parseCaptchaMessage('{"type":"error"}'), { type: "error" });
});
