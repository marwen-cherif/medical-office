import * as React from "react";
import { createPortal } from "react-dom";
import { CalendarDays } from "lucide-react";
import { Calendar } from "@/components/ui/calendar";
import { cn } from "@/lib/utils";
import { dateToIso, frToIso, isoToDate, isoToFr, maskDateFr } from "@/lib/format";

export type DatePickerProps = {
  /** Date sélectionnée au format ISO `YYYY-MM-DD` (chaîne vide = aucune). */
  value: string;
  /** Appelé avec la nouvelle date ISO (chaîne vide si effacée). */
  onChange: (iso: string) => void;
  id?: string;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  /** Alignement horizontal du calendrier sous le champ (défaut : `start`). */
  align?: "start" | "center" | "end";
  /** Menus déroulants mois/année (utile pour une date de naissance). */
  dropdown?: boolean;
  /** Bornes d'années quand `dropdown` est actif (défaut : 1920 → année courante). */
  fromYear?: number;
  toYear?: number;
};

/** Largeur/hauteur approximatives du calendrier avant 1ère mesure (positionnement initial). */
const APPROX_W = 264;
const APPROX_H = 330;
const GAP = 6; // écart vertical champ ↔ calendrier
const MARGIN = 8; // marge mini avec les bords de l'écran

/**
 * Sélecteur de date unique : un champ texte **saisissable au clavier** (tapez
 * `27101990` → `27/10/1990`, les `/` s'insèrent tout seuls) doublé d'un bouton
 * calendrier. Renvoie/consomme des dates ISO `YYYY-MM-DD`. Remplaçant direct des
 * `<input type="date">` natifs, réutilisé dans toute l'application.
 *
 * **Le calendrier est rendu dans un portail auto-géré** (`createPortal` → `document.body`,
 * positionné en `fixed` d'après le champ), pour deux raisons, l'une excluant l'autre :
 *
 * - **Pas inline (`absolute` dans la modale)** : un panneau inline allonge la zone
 *   scrollable d'une modale `overflow-y-auto` (la modale se met à scroller / sauter) et
 *   peut être rogné. En `fixed` portalisé, il flotte hors du conteneur scrollable : aucun
 *   impact sur le scroll, jamais rogné.
 * - **Pas un `Popover` Radix portalisé** : dans une modale Radix (piège à focus), cliquer
 *   un jour déplace le focus, la modale rapatrie le focus, et le popover détecte un « focus
 *   outside » → il se ferme AVANT que le `click` du jour n'aboutisse (sélection perdue).
 *   Un portail maison n'est pas une couche Radix : rien ne le ferme sur le `pointerdown`,
 *   donc le `click` sélectionne bien (les événements React passent à travers `createPortal`).
 *
 * Fermeture (clic-extérieur, Échap) gérée ici, en capture sur `window` pour passer AVANT
 * les écouteurs de la modale Radix (posés sur `document` en capture) : Échap et le clic dans
 * le calendrier ne ferment donc que le calendrier, pas la modale.
 */
export function DatePicker({
  value,
  onChange,
  id,
  placeholder = "JJ/MM/AAAA",
  disabled,
  className,
  align = "start",
  dropdown,
  fromYear = 1920,
  toYear,
}: DatePickerProps) {
  const [open, setOpen] = React.useState(false);
  // Texte affiché dans le champ (`JJ/MM/AAAA`). On le pilote nous-mêmes pour
  // permettre la saisie de dates partielles ; il n'est resynchronisé sur `value`
  // que lorsque le champ n'a pas le focus (sélection au calendrier, reset, …).
  const [text, setText] = React.useState(() => isoToFr(value));
  const focused = React.useRef(false);
  const fieldRef = React.useRef<HTMLDivElement>(null);
  const panelRef = React.useRef<HTMLDivElement>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const selected = isoToDate(value);
  const endYear = toYear ?? new Date().getFullYear();

  const [pos, setPos] = React.useState<{ top: number; left: number }>({ top: 0, left: 0 });

  React.useEffect(() => {
    if (!focused.current) setText(isoToFr(value));
  }, [value]);

  // Calcule la position `fixed` du calendrier d'après le rectangle du champ :
  // sous le champ par défaut, au-dessus s'il manque de place en bas ; bornée aux
  // bords de l'écran (anti-collision, qu'on perd sans Radix).
  const reposition = React.useCallback(() => {
    const field = fieldRef.current;
    if (!field) return;
    const fr = field.getBoundingClientRect();
    const pw = panelRef.current?.offsetWidth || APPROX_W;
    const ph = panelRef.current?.offsetHeight || APPROX_H;
    const spaceBelow = window.innerHeight - fr.bottom;
    const openUp = spaceBelow < ph + GAP + MARGIN && fr.top > spaceBelow;
    let left =
      align === "end" ? fr.right - pw : align === "center" ? fr.left + fr.width / 2 - pw / 2 : fr.left;
    left = Math.max(MARGIN, Math.min(left, window.innerWidth - pw - MARGIN));
    const top = openUp ? fr.top - ph - GAP : fr.bottom + GAP;
    setPos({ top, left });
  }, [align]);

  // Positionne avant la peinture (anti-clignotement), puis suit le scroll/redimension
  // (le champ bouge avec la modale, le calendrier `fixed` doit le suivre).
  React.useLayoutEffect(() => {
    if (open) reposition();
  }, [open, reposition]);

  React.useEffect(() => {
    if (!open) return;
    reposition(); // re-mesure une fois le panneau monté (taille réelle)
    const onMove = () => reposition();
    window.addEventListener("scroll", onMove, true);
    window.addEventListener("resize", onMove);
    return () => {
      window.removeEventListener("scroll", onMove, true);
      window.removeEventListener("resize", onMove);
    };
  }, [open, reposition]);

  // Clic en dehors → ferme le calendrier. En capture sur `window` : un clic DANS le
  // calendrier (portalisé hors du DOM de la modale) stoppe la propagation pour que la
  // modale Radix ne se ferme pas (elle nous prendrait pour un clic « extérieur »).
  React.useEffect(() => {
    if (!open) return;
    function onPointerDown(e: PointerEvent) {
      const t = e.target as HTMLElement | null;
      // Détection par marqueur DOM (`closest`) plutôt que `ref.contains` : on teste
      // l'ascendance réelle depuis la cible, robuste au portail.
      if (t?.closest?.("[data-datepicker-panel]")) {
        e.stopPropagation();
        return;
      }
      if (fieldRef.current?.contains(t)) return; // clic sur le champ : géré par ses handlers
      setOpen(false);
    }
    window.addEventListener("pointerdown", onPointerDown, true);
    return () => window.removeEventListener("pointerdown", onPointerDown, true);
  }, [open]);

  // Échap ferme le calendrier — et SEULEMENT lui. La modale Radix pose son écouteur
  // Échap sur `document` en capture (dès son montage) ; on écoute sur `window`, atteint
  // en premier dans la descente de capture, et on stoppe la propagation.
  React.useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== "Escape") return;
      e.preventDefault();
      e.stopPropagation();
      setOpen(false);
      inputRef.current?.focus();
    }
    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, [open]);

  function handleInput(e: React.ChangeEvent<HTMLInputElement>) {
    const masked = maskDateFr(e.target.value);
    // Garde le DOM aligné même quand le masque ne change pas l'état (frappe d'un
    // 9ᵉ chiffre alors que la date est déjà complète) : sinon le caractère en trop
    // resterait visible faute de re-rendu.
    e.target.value = masked;
    setText(masked);
    const iso = frToIso(masked);
    if (iso) onChange(iso);
    else if (masked === "") onChange("");
  }

  function handleBlur() {
    focused.current = false;
    // Normalise à la sortie : date complète → forme canonique ; champ vidé → "" ;
    // saisie partielle/invalide → on revient à la dernière valeur connue.
    const iso = frToIso(text);
    if (iso) setText(isoToFr(iso));
    else if (text.trim() === "") {
      setText("");
      onChange("");
    } else setText(isoToFr(value));
  }

  return (
    <div
      ref={fieldRef}
      className={cn(
        "flex h-9 w-full items-center gap-2 rounded-[var(--radius)] border border-line bg-white px-3 py-1 text-sm shadow-sm transition-colors focus-within:ring-2 focus-within:ring-navy/40",
        disabled && "cursor-not-allowed opacity-50",
        className,
      )}
    >
      <input
        ref={inputRef}
        id={id}
        type="text"
        inputMode="numeric"
        autoComplete="off"
        disabled={disabled}
        placeholder={placeholder}
        maxLength={10}
        value={text}
        onFocus={() => {
          focused.current = true;
        }}
        // Cliquer dans le champ ouvre le calendrier (comme un input date natif), sans
        // passer par l'icône. Le focus reste sur l'input : on peut continuer à taper.
        onClick={() => {
          if (!disabled) setOpen(true);
        }}
        onChange={handleInput}
        onBlur={handleBlur}
        className="min-w-0 flex-1 bg-transparent text-ink outline-none placeholder:text-muted disabled:cursor-not-allowed"
      />
      <button
        type="button"
        disabled={disabled}
        aria-label="Ouvrir le calendrier"
        aria-expanded={open}
        // mousedown (pas click) : bascule avant le clic-extérieur, et preventDefault
        // garde le focus sur le champ texte.
        onMouseDown={(e) => {
          if (disabled) return;
          e.preventDefault();
          setOpen((o) => !o);
        }}
        onKeyDown={(e) => {
          if (disabled) return;
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setOpen((o) => !o);
          }
        }}
        className="-mr-1 flex size-6 shrink-0 items-center justify-center rounded text-muted transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy/40 disabled:cursor-not-allowed"
      >
        <CalendarDays className="size-4" />
      </button>

      {open &&
        !disabled &&
        createPortal(
          <div
            ref={panelRef}
            data-datepicker-panel=""
            // `pointerEvents: auto` est INDISPENSABLE : une modale Radix `modal` pose
            // `pointer-events: none` sur le <body> (elle ne réactive que son propre
            // contenu). Notre calendrier portalisé dans <body>, hors de la modale,
            // hérite donc de `none` et deviendrait non cliquable sans ça.
            style={{ position: "fixed", top: pos.top, left: pos.left, zIndex: 60, pointerEvents: "auto" }}
            className="w-auto rounded-[var(--radius)] border border-line bg-white p-3 text-ink shadow-lg"
            // Empêche le calendrier de voler le focus au clic (le champ texte le garde) :
            // évite le va-et-vient de focus avec le piège à focus de la modale. Les
            // `<select>` mois/année (mode `dropdown`) sont exclus pour rester ouvrables.
            onMouseDown={(e) => {
              if (!(e.target as HTMLElement).closest("select")) e.preventDefault();
            }}
          >
            <Calendar
              mode="single"
              selected={selected}
              defaultMonth={selected}
              captionLayout={dropdown ? "dropdown" : "label"}
              startMonth={dropdown ? new Date(fromYear, 0) : undefined}
              endMonth={dropdown ? new Date(endYear, 11) : undefined}
              onSelect={(day) => {
                const iso = day ? dateToIso(day) : "";
                onChange(iso);
                // Resynchronise le texte tout de suite : le champ garde le focus, donc
                // l'effet de resynchro (gardé sur `!focused`) ne se déclencherait pas.
                setText(isoToFr(iso));
                setOpen(false);
              }}
            />
          </div>,
          document.body,
        )}
    </div>
  );
}
