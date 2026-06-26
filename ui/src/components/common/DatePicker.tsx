import * as React from "react";
import { CalendarDays } from "lucide-react";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
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
  /** Alignement du calendrier sous le champ. */
  align?: "start" | "center" | "end";
  /** Menus déroulants mois/année (utile pour une date de naissance). */
  dropdown?: boolean;
  /** Bornes d'années quand `dropdown` est actif (défaut : 1920 → année courante). */
  fromYear?: number;
  toYear?: number;
  /**
   * Mode modal du popover. Indispensable (et activé par défaut) quand le sélecteur
   * vit dans un `Dialog` : sans lui, le piège à focus du Dialog reprend la main et
   * referme le calendrier aussitôt ouvert.
   */
  modal?: boolean;
};

/**
 * Sélecteur de date unique : un champ texte **saisissable au clavier** (tapez
 * `27101990` → `27/10/1990`, les `/` s'insèrent tout seuls) doublé d'un bouton
 * calendrier (popover). Renvoie/consomme des dates ISO `YYYY-MM-DD`. Remplaçant
 * direct des `<input type="date">` natifs, réutilisé dans toute l'application.
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
  modal = true,
}: DatePickerProps) {
  const [open, setOpen] = React.useState(false);
  // Texte affiché dans le champ (`JJ/MM/AAAA`). On le pilote nous-mêmes pour
  // permettre la saisie de dates partielles ; il n'est resynchronisé sur `value`
  // que lorsque le champ n'a pas le focus (sélection au calendrier, reset, …).
  const [text, setText] = React.useState(() => isoToFr(value));
  const focused = React.useRef(false);
  const selected = isoToDate(value);
  const endYear = toYear ?? new Date().getFullYear();

  React.useEffect(() => {
    if (!focused.current) setText(isoToFr(value));
  }, [value]);

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
      className={cn(
        "flex h-9 w-full items-center gap-2 rounded-[var(--radius)] border border-line bg-white px-3 py-1 text-sm shadow-sm transition-colors focus-within:ring-2 focus-within:ring-navy/40",
        disabled && "cursor-not-allowed opacity-50",
        className,
      )}
    >
      <input
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
        onChange={handleInput}
        onBlur={handleBlur}
        className="min-w-0 flex-1 bg-transparent text-ink outline-none placeholder:text-muted disabled:cursor-not-allowed"
      />
      <Popover open={open} onOpenChange={setOpen} modal={modal}>
        <PopoverTrigger asChild>
          <button
            type="button"
            disabled={disabled}
            aria-label="Ouvrir le calendrier"
            className="-mr-1 flex size-6 shrink-0 items-center justify-center rounded text-muted transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy/40 disabled:cursor-not-allowed"
          >
            <CalendarDays className="size-4" />
          </button>
        </PopoverTrigger>
        <PopoverContent align={align} className="w-auto">
          <Calendar
            mode="single"
            autoFocus
            selected={selected}
            defaultMonth={selected}
            captionLayout={dropdown ? "dropdown" : "label"}
            startMonth={dropdown ? new Date(fromYear, 0) : undefined}
            endMonth={dropdown ? new Date(endYear, 11) : undefined}
            onSelect={(day) => {
              onChange(day ? dateToIso(day) : "");
              setOpen(false);
            }}
          />
        </PopoverContent>
      </Popover>
    </div>
  );
}
