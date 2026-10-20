import * as SecureStore from "expo-secure-store";

export const API_URL =
  process.env.EXPO_PUBLIC_API_URL || "http://10.0.2.2:8000/api/v1";
if (!__DEV__ && !API_URL.startsWith("https://")) {
  throw new Error(
    "Release builds require an HTTPS backend. Set EXPO_PUBLIC_API_URL before EAS Build.",
  );
}
type Tokens = { access_token: string; refresh_token: string };
let access: string | null = null;
let refreshing: Promise<boolean> | null = null;
let expired: (() => void) | null = null;
export function onExpired(callback: () => void) {
  expired = callback;
}
export async function saveTokens(tokens: Tokens) {
  await SecureStore.setItemAsync("sb.refresh", tokens.refresh_token);
  access = tokens.access_token;
}
export async function forgetTokens() {
  access = null;
  await SecureStore.deleteItemAsync("sb.refresh");
}
export async function refreshSession(): Promise<boolean> {
  if (refreshing) return refreshing;
  refreshing = (async () => {
    const token = await SecureStore.getItemAsync("sb.refresh");
    if (!token) return false;
    try {
      const result = await fetchWithTimeout(`${API_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: token }),
      });
      if (!result.ok) {
        if (result.status === 401) await forgetTokens();
        return false;
      }
      await saveTokens(await result.json());
      return true;
    } catch {
      return false;
    }
  })();
  try {
    return await refreshing;
  } finally {
    refreshing = null;
  }
}
async function fetchWithTimeout(url: string, options: RequestInit) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 75000);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  let response: Response;
  try {
    response = await fetchWithTimeout(API_URL + path, {
      ...options,
      headers: {
        ...(options.body && !(options.body instanceof FormData)
          ? { "Content-Type": "application/json" }
          : {}),
        ...(access ? { Authorization: `Bearer ${access}` } : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new Error(
      "Unable to reach SehatBridge. Check your connection and backend address, then retry.",
    );
  }
  if (response.status === 401 && retry && !path.startsWith("/auth/")) {
    if (await refreshSession()) return api<T>(path, options, false);
    expired?.();
  }
  const result = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new Error(
      result.error?.message || `Request failed (${response.status})`,
    );
  return result as T;
}
export function post<T>(path: string, body?: unknown) {
  return api<T>(path, {
    method: "POST",
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
}
export function put<T>(path: string, body: unknown) {
  return api<T>(path, { method: "PUT", body: JSON.stringify(body) });
}
export async function pageDataUri(
  documentId: string,
  pageId: string,
  mime: string,
) {
  const response = await fetchWithTimeout(
    `${API_URL}/documents/${documentId}/pages/${pageId}?preview=true`,
    { headers: { Authorization: `Bearer ${access}` } },
  );
  if (!response.ok)
    throw new Error(
      "Unable to load private source page. Sign in again and retry.",
    );
  const blob = await response.blob();
  return await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}
export async function uploadDocument(
  form: FormData,
  onProgress: (n: number) => void,
) {
  // Refresh before uploading so a large multipart body never needs an automatic replay.
  if (!(await refreshSession()))
    throw new Error("Please sign in again before uploading.");
  return await new Promise<import("./types").MedicalDocument>(
    (resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", API_URL + "/documents");
      xhr.setRequestHeader("Authorization", `Bearer ${access}`);
      xhr.timeout = 120000;
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) onProgress(event.loaded / event.total);
      };
      xhr.onload = () => {
        try {
          const result = JSON.parse(xhr.responseText);
          if (xhr.status >= 200 && xhr.status < 300) resolve(result);
          else reject(new Error(result.error?.message || "Upload failed"));
        } catch {
          reject(
            new Error(
              "Upload response was unreadable. Check document history before retrying.",
            ),
          );
        }
      };
      xhr.onerror = () =>
        reject(
          new Error(
            "Upload connection failed. Check document history before retrying.",
          ),
        );
      xhr.ontimeout = () =>
        reject(
          new Error(
            "Upload timed out. Check document history before retrying.",
          ),
        );
      xhr.send(form);
    },
  );
}
