import { fmtDevise } from "@/lib/format";
import { Montant } from "@/components/common/Montant";

/** Parse un montant saisi (virgule ou point décimal) ; 0 si vide/illisible. */
export function parseMontant(raw: string | null | undefined): number {
  return Number((raw ?? "").replace(",", ".")) || 0;
}

/**
 * Aperçu « à la volée » du reste après le montant saisi, partagé par les modales de
 * règlement (acte/plan, note, dépense). Recalculé à chaque frappe et borné à 0 ;
 * au-delà du dû, signale le surplus non imputable (le bouton reste de toute façon
 * bloqué côté modale).
 */
export function ResteApresReglement({
  reste,
  saisi,
  label = "Reste après règlement",
}: {
  reste: number;
  saisi: number;
  label?: string;
}) {
  const projete = Math.max(0, reste - saisi);
  const surplus = Math.max(0, saisi - reste);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm font-semibold text-amber">
        <span>{label}</span>
        <Montant value={projete} />
      </div>
      {surplus > 1e-6 && (
        <p className="text-xs text-red">
          Le montant dépasse le reste dû de {fmtDevise(surplus)}.
        </p>
      )}
    </div>
  );
}
