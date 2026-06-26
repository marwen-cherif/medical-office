/**
 * Client HTTP typé vers la façade de services (sidecar FastAPI).
 *
 * Types générés depuis l'OpenAPI (`npm run gen:api` → src/api/schema.d.ts), donc
 * front et back restent synchrones (cf. design D2). Le jeton de session et l'URL
 * de base sont découverts au lancement (cf. lib/bridge.ts) et injectés via un
 * middleware openapi-fetch.
 */
import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "../api/schema";
import { backend } from "./bridge";
import type { ApiErrorBody } from "./errors";

const authMiddleware: Middleware = {
  async onRequest({ request }) {
    request.headers.set("Authorization", `Bearer ${backend.token}`);
    return request;
  },
};

export const client = createClient<paths>({ baseUrl: backend.baseUrl });
client.use(authMiddleware);

/** Déballe une réponse openapi-fetch : renvoie `data`, lève `ApiErrorBody` sinon. */
export function unwrap<T>(res: { data?: T; error?: unknown }): T {
  if (res.error !== undefined) throw res.error as ApiErrorBody;
  return res.data as T;
}

/**
 * Télécharge un fichier binaire (ex. export .xlsx) via fetch authentifié, puis
 * déclenche l'enregistrement côté navigateur — openapi-fetch ne gère pas les
 * réponses binaires. `query` est sérialisé en chaîne de requête. Le nom du fichier
 * provient de l'en-tête `Content-Disposition` (repli sur `fallbackName`).
 */
export async function downloadFile(
  path: string,
  fallbackName: string,
  query?: Record<string, string | number | boolean | undefined>,
): Promise<void> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(query ?? {})) {
    if (v !== undefined) qs.set(k, String(v));
  }
  const url = `${backend.baseUrl}${path}${qs.toString() ? `?${qs}` : ""}`;
  const resp = await fetch(url, { headers: { Authorization: `Bearer ${backend.token}` } });
  if (!resp.ok) throw await resp.json();
  const blob = await resp.blob();
  const disposition = resp.headers.get("Content-Disposition") ?? "";
  const match = /filename="?([^"]+)"?/.exec(disposition);
  const filename = match?.[1] ?? fallbackName;

  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(href);
}

/**
 * Consomme un flux Server-Sent Events (opérations longues) via fetch streaming —
 * `EventSource` ne permet pas l'en-tête Authorization, on lit donc le corps à la
 * main. Appelle les callbacks au fil des événements ; résout à `done`, rejette à
 * `error`.
 */
export type JobEvent =
  | { type: "progress"; value: number; message: string }
  | { type: "done"; result: unknown }
  | { type: "error"; code: string; message: string };

export async function streamJob(
  jobId: string,
  onEvent: (e: JobEvent) => void,
): Promise<void> {
  const resp = await fetch(`${backend.baseUrl}/api/events/${jobId}`, {
    headers: { Authorization: `Bearer ${backend.token}` },
  });
  if (!resp.ok || !resp.body) {
    throw { error: { code: "PRINT_FAILED", message: "Flux d'événements indisponible." } };
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const line = frame.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      const event = JSON.parse(line.slice(5).trim()) as JobEvent;
      onEvent(event);
      if (event.type === "done") return;
      if (event.type === "error") throw { error: { code: event.code, message: event.message } };
    }
  }
}
