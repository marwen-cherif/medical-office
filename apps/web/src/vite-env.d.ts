/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Devise de l'application : "EUR" (défaut) ou "TND". Cf. src/lib/format.ts. */
  readonly VITE_DEVISE?: string;
}
