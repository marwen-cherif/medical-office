import * as React from "react";
import { Check, ChevronDown, Plus, Search, X } from "lucide-react";
import { cn } from "@/lib/utils";

export type ComboboxOption = {
  value: string;
  label: string;
  /** Texte additionnel pris en compte par la recherche (code, synonymes…). */
  keywords?: string;
  disabled?: boolean;
};

export interface ComboboxProps {
  options: ComboboxOption[];
  value: string | null | undefined;
  onChange: (value: string) => void;
  placeholder?: string;
  searchPlaceholder?: string;
  emptyText?: string;
  disabled?: boolean;
  /** Classe du déclencheur (bouton). */
  className?: string;
  /** Classe du panneau flottant. */
  contentClassName?: string;
  /** id posé sur le déclencheur (pour `<Label htmlFor>`). */
  id?: string;
  /** Bouton d'effacement quand une valeur est sélectionnée (émet `onChange("")`). */
  allowClear?: boolean;
  /**
   * Autorise la **création** d'une valeur : si la saisie ne correspond à aucune
   * option, une rangée « Créer « … » » l'ajoute (émet `onChange(saisie)`). La
   * valeur retenue peut alors être hors de `options` (texte libre).
   */
  creatable?: boolean;
  /** Libellé de la rangée de création (défaut : « Créer « X » »). */
  createLabel?: (query: string) => string;
}

// Hauteur de ligne FIXE : indispensable au fenêtrage (virtualisation) ci-dessous.
const ROW_HEIGHT = 34;
// Nombre de lignes visibles avant scroll (hauteur du panneau).
const MAX_VISIBLE = 8;
// Lignes rendues au-delà de la fenêtre visible (haut + bas) pour un scroll fluide.
const OVERSCAN = 6;

/** Replie casse + accents pour une recherche tolérante (« Égée » ⇒ « egee »). */
function fold(s: string): string {
  return s.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
}

type Entry =
  | { kind: "option"; opt: ComboboxOption }
  | { kind: "create"; label: string };

/**
 * Liste déroulante **commune** avec **recherche**, **virtualisation** et, en option,
 * **création** de valeurs (`creatable`).
 *
 * Filtrage client (libellé + `keywords`, insensible casse/accents) et rendu
 * **fenêtré à hauteur de ligne fixe** : seules les lignes visibles (+ marge) sont
 * montées, donc des listes de milliers d'options restent fluides — la
 * virtualisation est **toujours active** (coût nul sur les petites listes).
 *
 * Le panneau est rendu **inline** (pas de portail) : indispensable pour fonctionner
 * dans une modale Radix, dont le piège à focus rendrait un champ de recherche
 * portalisé non focusable (donc non saisissable). Clic-extérieur et Échap gérés ici.
 */
export function Combobox({
  options,
  value,
  onChange,
  placeholder = "Sélectionner…",
  searchPlaceholder = "Rechercher…",
  emptyText = "Aucun résultat.",
  disabled,
  className,
  contentClassName,
  id,
  allowClear = false,
  creatable = false,
  createLabel = (q) => `Créer « ${q} »`,
}: ComboboxProps) {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [active, setActive] = React.useState(0);
  const [scrollTop, setScrollTop] = React.useState(0);
  const rootRef = React.useRef<HTMLDivElement>(null);
  const scrollRef = React.useRef<HTMLDivElement>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const triggerRef = React.useRef<HTMLButtonElement>(null);
  const listboxId = React.useId();

  const selected = React.useMemo(
    () => options.find((o) => o.value === value) ?? null,
    [options, value],
  );
  // Valeur creatable hors `options` : on affiche tout de même le texte courant.
  const hasValue = value != null && value !== "";
  const triggerLabel = selected ? selected.label : hasValue ? String(value) : "";

  const filtered = React.useMemo(() => {
    const q = fold(query.trim());
    if (!q) return options;
    return options.filter(
      (o) => fold(o.label).includes(q) || (o.keywords ? fold(o.keywords).includes(q) : false),
    );
  }, [options, query]);

  // Rangée de création (en queue de liste) si la saisie n'existe pas déjà.
  const q = query.trim();
  const exists = q !== "" && options.some((o) => fold(o.value) === fold(q) || fold(o.label) === fold(q));
  const showCreate = creatable && q !== "" && !exists;
  const entries: Entry[] = React.useMemo(() => {
    const opts: Entry[] = filtered.map((opt) => ({ kind: "option", opt }));
    return showCreate ? [...opts, { kind: "create", label: q }] : opts;
  }, [filtered, showCreate, q]);

  // Fenêtre rendue : [startIndex, endIndex[ autour de la position de scroll.
  const total = entries.length * ROW_HEIGHT;
  const startIndex = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
  const endIndex = Math.min(entries.length, startIndex + MAX_VISIBLE + OVERSCAN * 2);
  const windowed = entries.slice(startIndex, endIndex);

  // Ouverture : recherche vidée, position active = sélection courante, scroll remis à zéro,
  // focus sur le champ de recherche (panneau inline ⇒ focusable même en modale).
  React.useEffect(() => {
    if (!open) return;
    setQuery("");
    setScrollTop(0);
    const idx = value ? options.findIndex((o) => o.value === value) : 0;
    setActive(idx < 0 ? 0 : idx);
    inputRef.current?.focus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Fermeture au clic en dehors du composant (le panneau étant inline, pas de
  // gestion « dismissable layer » de Radix : on l'assure nous-mêmes).
  React.useEffect(() => {
    if (!open) return;
    function onPointerDown(e: PointerEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown, true);
    return () => document.removeEventListener("pointerdown", onPointerDown, true);
  }, [open]);

  // La saisie change le filtre : on repart en haut de liste.
  React.useEffect(() => {
    setActive(0);
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
    setScrollTop(0);
  }, [query]);

  // Garde la ligne active visible (hauteur fixe ⇒ calcul exact).
  React.useEffect(() => {
    const el = scrollRef.current;
    if (!el || !open) return;
    const top = active * ROW_HEIGHT;
    const bottom = top + ROW_HEIGHT;
    if (top < el.scrollTop) el.scrollTop = top;
    else if (bottom > el.scrollTop + el.clientHeight) el.scrollTop = bottom - el.clientHeight;
  }, [active, open]);

  function entryDisabled(i: number): boolean {
    const e = entries[i];
    return e?.kind === "option" ? !!e.opt.disabled : false;
  }

  function moveActive(dir: 1 | -1) {
    if (!entries.length) return;
    let i = active;
    for (let n = 0; n < entries.length; n++) {
      i = (i + dir + entries.length) % entries.length;
      if (!entryDisabled(i)) break;
    }
    setActive(i);
  }

  function commit(index: number) {
    const e = entries[index];
    if (!e) return;
    if (e.kind === "create") {
      onChange(e.label);
    } else {
      if (e.opt.disabled) return;
      onChange(e.opt.value);
    }
    setOpen(false);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      moveActive(1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      moveActive(-1);
    } else if (e.key === "Home") {
      e.preventDefault();
      setActive(0);
    } else if (e.key === "End") {
      e.preventDefault();
      setActive(entries.length - 1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      commit(active);
    } else if (e.key === "Escape") {
      // stopPropagation : ne pas laisser l'Échap fermer aussi la modale parente.
      e.preventDefault();
      e.stopPropagation();
      setOpen(false);
      triggerRef.current?.focus();
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={triggerRef}
        id={id}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        disabled={disabled}
        onClick={() => !disabled && setOpen((o) => !o)}
        className={cn(
          "flex h-9 w-full items-center justify-between gap-2 rounded-[var(--radius)] border border-line bg-white px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-navy/40 disabled:opacity-50",
          className,
        )}
      >
        <span className={cn("line-clamp-1 text-left", hasValue ? "text-ink" : "text-muted")}>
          {triggerLabel || placeholder}
        </span>
        <ChevronDown className="size-4 shrink-0 opacity-60" />
      </button>
      {allowClear && hasValue && !disabled && (
        <button
          type="button"
          aria-label="Effacer la sélection"
          onClick={(e) => {
            e.stopPropagation();
            onChange("");
          }}
          className="absolute right-8 top-1/2 -translate-y-1/2 rounded p-0.5 text-muted hover:text-ink"
        >
          <X className="size-3.5" />
        </button>
      )}

      {open && (
        <div
          className={cn(
            "absolute left-0 right-0 top-full z-50 mt-1 rounded-[var(--radius)] border border-line bg-white p-2 shadow-lg",
            contentClassName,
          )}
        >
          <div className="mb-1 flex items-center gap-2 border-b border-line px-1 pb-2">
            <Search className="size-4 shrink-0 text-muted" />
            <input
              ref={inputRef}
              type="text"
              role="combobox"
              aria-expanded
              aria-autocomplete="list"
              aria-controls={listboxId}
              aria-activedescendant={entries.length ? `${listboxId}-opt-${active}` : undefined}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder={searchPlaceholder}
              className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-muted"
            />
          </div>

          <div
            ref={scrollRef}
            role="listbox"
            id={listboxId}
            onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}
            className="overflow-y-auto overflow-x-hidden"
            style={{ maxHeight: MAX_VISIBLE * ROW_HEIGHT }}
          >
            {entries.length === 0 ? (
            <div className="px-2 py-6 text-center text-sm text-muted">{emptyText}</div>
          ) : (
            <div style={{ height: total, position: "relative" }}>
              <ul
                className="absolute inset-x-0 m-0 list-none p-0"
                style={{ top: startIndex * ROW_HEIGHT }}
              >
                {windowed.map((entry, k) => {
                  const index = startIndex + k;
                  const isActive = index === active;
                  if (entry.kind === "create") {
                    return (
                      <li
                        key="__create__"
                        id={`${listboxId}-opt-${index}`}
                        role="option"
                        aria-selected={false}
                        onMouseEnter={() => setActive(index)}
                        onMouseDown={(ev) => {
                          ev.preventDefault();
                          commit(index);
                        }}
                        style={{ height: ROW_HEIGHT }}
                        className={cn(
                          "flex cursor-pointer select-none items-center gap-2 rounded-sm px-2 text-sm text-navy",
                          isActive ? "bg-bg" : "",
                        )}
                      >
                        <Plus className="size-4 shrink-0" />
                        <span className="truncate">{createLabel(entry.label)}</span>
                      </li>
                    );
                  }
                  const opt = entry.opt;
                  const isSelected = opt.value === value;
                  return (
                    <li
                      key={opt.value}
                      id={`${listboxId}-opt-${index}`}
                      role="option"
                      aria-selected={isSelected}
                      aria-disabled={opt.disabled || undefined}
                      onMouseEnter={() => !opt.disabled && setActive(index)}
                      // mousedown (pas click) : commit avant que l'input ne perde le focus.
                      onMouseDown={(ev) => {
                        ev.preventDefault();
                        commit(index);
                      }}
                      style={{ height: ROW_HEIGHT }}
                      className={cn(
                        "flex select-none items-center gap-2 rounded-sm px-2 text-sm",
                        opt.disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer",
                        isActive && !opt.disabled ? "bg-bg" : "",
                      )}
                    >
                      <span className="flex size-4 shrink-0 items-center justify-center">
                        {isSelected && <Check className="size-4 text-navy" />}
                      </span>
                      <span className="truncate">{opt.label}</span>
                    </li>
                  );
                })}
              </ul>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
