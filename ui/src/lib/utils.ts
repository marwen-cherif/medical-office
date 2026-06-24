import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Fusionne des classes Tailwind (convention shadcn/ui). */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format FR d'un montant : espace pour les milliers, virgule décimale, 2 déc. */
export function formatPrix(value: number | null | undefined): string {
  const n = value ?? 0;
  return n
    .toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    .replace(/ /g, " ")
    .replace(/ /g, " ");
}
