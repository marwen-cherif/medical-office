import { fmtDevise, fmtMontant } from "@/lib/format";
import { cn } from "@/lib/utils";

type MontantTone = "ink" | "muted" | "green" | "amber" | "red";

const TONE: Record<MontantTone, string> = {
  ink: "text-ink",
  muted: "text-muted",
  green: "text-green",
  amber: "text-amber",
  red: "text-red",
};

/**
 * Affichage standard d'un montant : chiffres alignés (`tabular-nums`) + formatage FR
 * (`fmtDevise`/`fmtMontant`). Composant commun pour *tous* les montants affichés —
 * cellules de tableau, récapitulatifs, lignes de ventilation — afin de centraliser en
 * un seul point le séparateur de milliers, la devise et l'alignement.
 *
 * Pour une chaîne pure (toast, sous-titre construit par `join`), garder `fmtDevise`.
 */
export function Montant({
  value,
  devise = true,
  tone,
  bold,
  className,
}: {
  value: number | null | undefined;
  /** Suffixer le symbole de la devise (`€`/`DT`). Défaut : oui. */
  devise?: boolean;
  tone?: MontantTone;
  bold?: boolean;
  className?: string;
}) {
  return (
    <span className={cn("tabular-nums", tone && TONE[tone], bold && "font-semibold", className)}>
      {devise ? fmtDevise(value) : fmtMontant(value)}
    </span>
  );
}

/**
 * Ligne « libellé · montant » alignée (label à gauche, montant aligné à droite).
 * Mutualise le récapitulatif répété des modales de règlement (Total dû / Déjà réglé /
 * Reste). Le ton par défaut suit le conteneur ; passer `tone` pour colorer le montant.
 */
export function MontantRow({
  label,
  value,
  tone,
  className,
}: {
  label: string;
  value: number | null | undefined;
  tone?: MontantTone;
  className?: string;
}) {
  return (
    <div className={cn("flex justify-between text-sm text-muted", className)}>
      <span>{label}</span>
      <Montant value={value} tone={tone} />
    </div>
  );
}
