/**
 * Découverte du backend (port éphémère + jeton de session).
 *
 * Trois sources, dans l'ordre :
 *  1. `window.__CRM_BACKEND__` — injecté par la coquille Tauri au démarrage,
 *     après lecture du handshake `CRM_SERVER_READY {json}` sur le stdout du
 *     sidecar (cf. crm/server.py et src-tauri).
 *  2. Variables d'env Vite (`VITE_CRM_PORT` / `VITE_CRM_TOKEN`) — pratique en
 *     `npm run dev` contre un sidecar lancé à la main
 *     (`python -m crm.server --port 8765 --token devtoken`).
 *  3. Valeurs par défaut de dev (port 8765, jeton « devtoken »).
 */

export type Backend = { baseUrl: string; token: string };

declare global {
  interface Window {
    __CRM_BACKEND__?: { host?: string; port: number; token: string };
  }
}

export function resolveBackend(): Backend {
  const injected = typeof window !== "undefined" ? window.__CRM_BACKEND__ : undefined;
  if (injected?.port && injected?.token) {
    const host = injected.host ?? "127.0.0.1";
    return { baseUrl: `http://${host}:${injected.port}`, token: injected.token };
  }
  const port = import.meta.env.VITE_CRM_PORT ?? "8765";
  const token = import.meta.env.VITE_CRM_TOKEN ?? "devtoken";
  return { baseUrl: `http://127.0.0.1:${port}`, token };
}

export const backend = resolveBackend();
