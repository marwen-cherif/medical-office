import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

/**
 * Système de raccourcis clavier de l'application.
 *
 * Objectif : rendre chaque action « souris » déclenchable au clavier et exposer
 * les raccourcis de façon découvrable (tooltips + carte globale via `?`).
 *
 * Conception robuste pour un cabinet **français (clavier AZERTY)** :
 * - les **chiffres** sont reconnus via `event.code` (`Digit1`…) → `Alt+1` marche
 *   sans `Maj` sur AZERTY ;
 * - les **lettres** sont reconnues via `event.key` (la lettre réellement produite) ;
 * - les caractères « shiftés » comme `?` sont matchés sur le caractère produit, donc
 *   indépendants de la disposition.
 *
 * Un raccourci à modificateur (Ctrl/Alt/Cmd) se déclenche même dans un champ de
 * saisie ; un raccourci « touche nue » (`?`, `/`) est ignoré pendant la saisie.
 * Tous les raccourcis sont suspendus tant qu'une surcouche modale (dialog, menu,
 * liste de sélection) est ouverte — elle gère son propre clavier.
 */

// ── Plateforme ──────────────────────────────────────────────────────────────
const isMac =
  typeof navigator !== "undefined" &&
  /mac|iphone|ipad|ipod/i.test(navigator.platform || navigator.userAgent || "");

// ── Types ───────────────────────────────────────────────────────────────────
export interface ShortcutDef {
  /** Combinaison, ex. `"alt+n"`, `"alt+1"`, `"?"`, `"/"`, `"mod+s"`. Insensible à la casse. */
  keys: string;
  /** Libellé affiché dans la carte des raccourcis (et les tooltips). */
  description: string;
  /** Groupe d'affichage dans la carte (ex. `"Navigation"`, `"Patients"`). */
  group: string;
  /** Action déclenchée. */
  handler: (e: KeyboardEvent) => void;
  /** `false` ⇒ listé dans la carte mais inactif (ex. action indisponible). Défaut : `true`. */
  enabled?: boolean;
  /** Déclencher même quand un champ de saisie a le focus. Défaut : vrai si combo à modificateur. */
  allowInInput?: boolean;
  /** `preventDefault` au déclenchement. Défaut : `true`. */
  preventDefault?: boolean;
  /** Tri au sein du groupe (croissant). Défaut : ordre d'enregistrement. */
  order?: number;
  /** Actif mais **masqué** de la carte (ex. alias `F1` du `?`). Défaut : `false`. */
  hidden?: boolean;
}

interface ParsedCombo {
  ctrl: boolean;
  alt: boolean;
  meta: boolean;
  /** `Maj` explicitement demandé dans la combinaison. */
  shift: boolean;
  /** Jeton de touche normalisé : `"n"`, `"1"`, `"?"`, `"enter"`, `"arrowleft"`, `"escape"`… */
  key: string;
}

// ── Parsing ─────────────────────────────────────────────────────────────────
const KEY_ALIASES: Record<string, string> = {
  esc: "escape",
  del: "delete",
  return: "enter",
  space: "space",
  spacebar: "space",
  up: "arrowup",
  down: "arrowdown",
  left: "arrowleft",
  right: "arrowright",
  plus: "+",
};

function normalizeKeyToken(token: string): string {
  const t = token.toLowerCase();
  return KEY_ALIASES[t] ?? t;
}

function parseCombo(keys: string): ParsedCombo {
  const combo: ParsedCombo = { ctrl: false, alt: false, meta: false, shift: false, key: "" };
  // `split("+")` casse le raccourci littéral `+` ; on le gère via l'alias "plus".
  const parts = keys
    .trim()
    .split("+")
    .map((s) => s.trim())
    .filter(Boolean);
  for (const part of parts) {
    const p = part.toLowerCase();
    if (p === "ctrl" || p === "control") combo.ctrl = true;
    else if (p === "alt" || p === "option") combo.alt = true;
    else if (p === "meta" || p === "cmd" || p === "command" || p === "win" || p === "super")
      combo.meta = true;
    else if (p === "mod") {
      if (isMac) combo.meta = true;
      else combo.ctrl = true;
    } else if (p === "shift") combo.shift = true;
    else combo.key = normalizeKeyToken(part);
  }
  return combo;
}

// ── Correspondance évènement ⇄ combinaison ─────────────────────────────────
/** Caractères candidats produits par l'évènement (clé logique + position physique). */
function eventChars(e: KeyboardEvent): Set<string> {
  const set = new Set<string>();
  if (e.key && e.key.length === 1) set.add(e.key.toLowerCase());
  const code = e.code || "";
  if (code.startsWith("Digit")) set.add(code.slice(5)); // Digit1 → "1" (AZERTY sans Maj)
  else if (/^Numpad\d$/.test(code)) set.add(code.slice(6));
  else if (code.startsWith("Key")) set.add(code.slice(3).toLowerCase()); // KeyN → "n"
  return set;
}

const CODE_NAMED: Record<string, string> = {
  Space: "space",
  Enter: "enter",
  NumpadEnter: "enter",
  Escape: "escape",
  Tab: "tab",
  Backspace: "backspace",
  Delete: "delete",
  ArrowUp: "arrowup",
  ArrowDown: "arrowdown",
  ArrowLeft: "arrowleft",
  ArrowRight: "arrowright",
};

function eventMatchesCombo(e: KeyboardEvent, combo: ParsedCombo): boolean {
  if (combo.ctrl !== e.ctrlKey) return false;
  if (combo.alt !== e.altKey) return false;
  if (combo.meta !== e.metaKey) return false;
  // `Maj` n'est exigé que s'il est explicite : un raccourci comme `?` produit déjà
  // `shiftKey=true` selon la disposition, on ne veut pas l'imposer ni l'interdire.
  if (combo.shift && !e.shiftKey) return false;

  const k = combo.key;
  if (!k) return false;
  if (k.length === 1) return eventChars(e).has(k);
  const named = e.key.toLowerCase() === " " ? "space" : e.key.toLowerCase();
  return named === k || CODE_NAMED[e.code] === k;
}

// ── Contexte de saisie / surcouches ────────────────────────────────────────
function isEditableTarget(el: EventTarget | null): boolean {
  const node = el as HTMLElement | null;
  if (!node || node.nodeType !== 1) return false;
  const tag = node.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
    return !(node as HTMLInputElement).disabled && !(node as HTMLInputElement).readOnly;
  }
  return node.isContentEditable;
}

/** Vrai si une surcouche Radix (dialog, menu, liste de sélection) est ouverte. */
function overlayOpen(): boolean {
  return !!document.querySelector(
    '[role="dialog"][data-state="open"],' +
      '[role="alertdialog"][data-state="open"],' +
      '[role="menu"][data-state="open"],' +
      '[role="listbox"][data-state="open"]',
  );
}

// ── Registre + contexte ────────────────────────────────────────────────────
interface RegistryEntry {
  def: ShortcutDef;
  combo: ParsedCombo;
  seq: number;
}

/** API d'enregistrement — **identité stable** (ne change jamais), pour que l'effet de
 * `useShortcut` ne se réexécute pas à chaque mutation du registre (sinon : boucle). */
interface ShortcutsApi {
  register: (id: number, def: ShortcutDef) => void;
  unregister: (id: number) => void;
}

/** État observable — change à chaque (dé)enregistrement et à l'ouverture de l'aide. */
interface ShortcutsState {
  /** Liste courante triée (groupe → order → ordre d'enregistrement). */
  shortcuts: ShortcutDef[];
  helpOpen: boolean;
  openHelp: () => void;
  closeHelp: () => void;
  toggleHelp: () => void;
}

const ShortcutsApiContext = createContext<ShortcutsApi | null>(null);
const ShortcutsStateContext = createContext<ShortcutsState | null>(null);

let idCounter = 0;
function nextId(): number {
  return ++idCounter;
}

export function ShortcutsProvider({ children }: { children: React.ReactNode }) {
  const registry = useRef<Map<number, RegistryEntry>>(new Map());
  const seqRef = useRef(0);
  const [version, setVersion] = useState(0);
  const [helpOpen, setHelpOpen] = useState(false);

  const register = useCallback((id: number, def: ShortcutDef) => {
    registry.current.set(id, { def, combo: parseCombo(def.keys), seq: ++seqRef.current });
    setVersion((v) => v + 1);
  }, []);

  const unregister = useCallback((id: number) => {
    if (registry.current.delete(id)) setVersion((v) => v + 1);
  }, []);

  const openHelp = useCallback(() => setHelpOpen(true), []);
  const closeHelp = useCallback(() => setHelpOpen(false), []);
  const toggleHelp = useCallback(() => setHelpOpen((o) => !o), []);

  // Écouteur clavier global unique.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.defaultPrevented || e.isComposing) return;
      // `Alt`/`Ctrl`/`Shift`/`Meta` seuls : laisser passer (pas une combinaison).
      if (e.key === "Alt" || e.key === "Control" || e.key === "Shift" || e.key === "Meta") return;
      if (overlayOpen()) return;

      const editable = isEditableTarget(document.activeElement) || isEditableTarget(e.target);

      // Premier match l'emporte ; les plus récemment enregistrés (écran/onglet courant)
      // priment sur les globaux pour une même combinaison.
      const entries = [...registry.current.values()].sort((a, b) => b.seq - a.seq);
      for (const { def, combo } of entries) {
        if (def.enabled === false) continue;
        if (!eventMatchesCombo(e, combo)) continue;
        const hasModifier = combo.ctrl || combo.alt || combo.meta;
        const allowInInput = def.allowInInput ?? hasModifier;
        if (editable && !allowInInput) continue;
        if (def.preventDefault !== false) e.preventDefault();
        def.handler(e);
        return;
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const shortcuts = useMemo(() => {
    void version; // recalcul à chaque mutation du registre
    return [...registry.current.values()]
      .sort((a, b) => (a.def.order ?? 0) - (b.def.order ?? 0) || a.seq - b.seq)
      .map((e) => e.def);
  }, [version]);

  // `api` : identité stable (register/unregister sont des useCallback) → l'effet de
  // `useShortcut` ne se réexécute jamais à cause d'un changement de contexte.
  const api = useMemo<ShortcutsApi>(() => ({ register, unregister }), [register, unregister]);
  const state = useMemo<ShortcutsState>(
    () => ({ shortcuts, helpOpen, openHelp, closeHelp, toggleHelp }),
    [shortcuts, helpOpen, openHelp, closeHelp, toggleHelp],
  );

  return (
    <ShortcutsApiContext.Provider value={api}>
      <ShortcutsStateContext.Provider value={state}>{children}</ShortcutsStateContext.Provider>
    </ShortcutsApiContext.Provider>
  );
}

/** État observable (liste des raccourcis + état de l'aide) — pour la barre latérale et la carte. */
export function useShortcutsContext(): ShortcutsState {
  const ctx = useContext(ShortcutsStateContext);
  if (!ctx) throw new Error("useShortcutsContext doit être utilisé sous <ShortcutsProvider>");
  return ctx;
}

type ShortcutInput = ShortcutDef | false | null | undefined;

/**
 * Enregistre un ou plusieurs raccourcis pour la durée de vie du composant.
 * Les valeurs falsy sont ignorées (permet `useShortcut([cond && {...}])`).
 *
 * Le `handler` passe toujours par une ref → pas de réenregistrement à chaque
 * frappe ; le réenregistrement n'a lieu que si la « signature » change
 * (keys / description / group / enabled / order / flags).
 */
export function useShortcut(input: ShortcutInput | ShortcutInput[]): void {
  const api = useContext(ShortcutsApiContext);
  const defs = (Array.isArray(input) ? input : [input]).filter(Boolean) as ShortcutDef[];

  const ref = useRef<ShortcutDef[]>(defs);
  ref.current = defs;

  const sig = defs
    .map(
      (d) =>
        `${d.keys}|${d.description}|${d.group}|${d.enabled !== false}|${d.order ?? 0}|` +
        `${d.allowInInput ?? ""}|${d.preventDefault ?? ""}|${d.hidden ?? false}`,
    )
    .join("§");

  useEffect(() => {
    if (!api) return;
    const ids = ref.current.map((_, i) => {
      const id = nextId();
      api.register(id, {
        ...ref.current[i],
        handler: (e) => ref.current[i]?.handler(e),
      });
      return id;
    });
    return () => ids.forEach((id) => api.unregister(id));
    // `sig` capture tout changement de définition pertinent ; le handler vit dans `ref`.
    // `api` est d'identité stable → pas de réenregistrement intempestif.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, sig]);
}

// ── Affichage ───────────────────────────────────────────────────────────────
const NAMED_DISPLAY: Record<string, string> = {
  enter: "Entrée",
  escape: "Échap",
  space: "Espace",
  tab: "Tab",
  backspace: "Retour",
  delete: "Suppr",
  arrowup: "↑",
  arrowdown: "↓",
  arrowleft: "←",
  arrowright: "→",
};

function displayKey(key: string): string {
  if (!key) return "";
  if (NAMED_DISPLAY[key]) return NAMED_DISPLAY[key];
  if (key.length === 1) return key.toUpperCase();
  return key.charAt(0).toUpperCase() + key.slice(1);
}

/** Convertit une combinaison en jetons d'affichage, ex. `"alt+n"` → `["Alt", "N"]`. */
export function comboToKeys(keys: string): string[] {
  const c = parseCombo(keys);
  const tokens: string[] = [];
  if (c.ctrl) tokens.push(isMac ? "⌃" : "Ctrl");
  if (c.alt) tokens.push(isMac ? "⌥" : "Alt");
  if (c.shift) tokens.push(isMac ? "⇧" : "Maj");
  if (c.meta) tokens.push(isMac ? "⌘" : "Win");
  tokens.push(displayKey(c.key));
  return tokens;
}
