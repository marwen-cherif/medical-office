import "react-odontogram/style.css";
import { useMemo } from "react";
import { Odontogram } from "react-odontogram";
import type { ToothConditionGroup, ToothDetail } from "react-odontogram";
import { parseDents } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Clinical, Prestation } from "@/api/types";

/**
 * Odontogramme **clinique en lecture seule** : schéma anatomique (react-odontogram)
 * colorisant les dents du patient selon leur état (réalisé / planifié), dérivé des
 * données `clinical` déjà chargées. Distinct de la grille de saisie (inchangée).
 *
 * react-odontogram ne connaît que les quadrants permanents (1-4) : la denture temporaire
 * s'obtient via `maxTeeth=5` mais reste numérotée en positions 11-45. On convertit donc la
 * FDI de l'application (dents de lait 51-85) vers les identifiants de la librairie, et on
 * réaffiche la vraie FDI dans l'infobulle. Les dents hors de la denture courante (denture
 * mixte, jetons non-FDI) sont listées en texte sous le schéma — rien n'est caché.
 *
 * `highlightFdis` permet de **mettre en évidence** (couleur ambre, prioritaire) les dents
 * d'un acte survolé dans la liste en dessous.
 */

type Denture = "adulte" | "enfant";
type Etat = "realise" | "planifie";

// Couleurs de la palette de l'app (cf. ui/src/index.css).
const COULEUR_REALISE = "#10357f"; // navy
const COULEUR_PLANIFIE_FILL = "#62ebe2"; // teal
const COULEUR_PLANIFIE_OUTLINE = "#0c8b82"; // teal-dark
const COULEUR_SURVOL = "#b45309"; // amber — mise en évidence au survol

const ETAT_LABEL: Record<Etat, string> = { realise: "Réalisé", planifie: "Planifié" };

/**
 * FDI de l'application → identifiant react-odontogram, ou `null` si la dent n'appartient
 * pas à la denture affichée.
 * - Adulte : FDI permanente 11-48 → `teeth-<fdi>` (identité).
 * - Enfant : FDI de lait 51-85 → `teeth-<quadrant-4><position>` (ex. 55 → `teeth-15`).
 */
export function fdiToToothId(fdi: string, denture: Denture): string | null {
  if (denture === "adulte") return /^[1-4][1-8]$/.test(fdi) ? `teeth-${fdi}` : null;
  if (/^[5-8][1-5]$/.test(fdi)) return `teeth-${Number(fdi[0]) - 4}${fdi[1]}`;
  return null;
}

/** Identifiant react-odontogram → FDI réelle, pour l'infobulle (enfant : quadrant +4). */
export function toothIdToFdi(id: string, denture: Denture): string {
  const raw = id.replace("teeth-", "");
  if (denture === "enfant" && /^[1-4][1-5]$/.test(raw)) return `${Number(raw[0]) + 4}${raw[1]}`;
  return raw;
}

type Derived = {
  conditions: ToothConditionGroup[];
  etatParId: Map<string, Etat>;
  horsSchema: Record<Etat, string[]>;
  aDesDents: boolean;
};

/** Projette les actes du patient en groupes de conditions + dents hors-schéma. */
export function deriveOdontogramme(clinical: Clinical, denture: Denture): Derived {
  const prestations: Prestation[] = [
    ...clinical.isoles,
    ...clinical.plans.flatMap((g) => g.prestations),
  ];

  // Une dent est « réalisée » si au moins un acte daté la porte ; sinon « planifiée ».
  const realise = new Set<string>();
  const planifie = new Set<string>();
  for (const p of prestations) {
    for (const d of parseDents(p.dents)) (p.date_acte ? realise : planifie).add(d);
  }
  for (const d of realise) planifie.delete(d); // réalisé prioritaire

  const idsRealise: string[] = [];
  const idsPlanifie: string[] = [];
  const horsSchema: Record<Etat, string[]> = { realise: [], planifie: [] };
  const etatParId = new Map<string, Etat>();

  const classer = (dents: Set<string>, etat: Etat, ids: string[]) => {
    for (const fdi of dents) {
      const id = fdiToToothId(fdi, denture);
      if (id) {
        ids.push(id);
        etatParId.set(id, etat);
      } else {
        horsSchema[etat].push(fdi);
      }
    }
  };
  classer(realise, "realise", idsRealise);
  classer(planifie, "planifie", idsPlanifie);

  const conditions: ToothConditionGroup[] = [];
  if (idsRealise.length)
    conditions.push({
      label: ETAT_LABEL.realise,
      teeth: idsRealise,
      fillColor: COULEUR_REALISE,
      outlineColor: COULEUR_REALISE,
    });
  if (idsPlanifie.length)
    conditions.push({
      label: ETAT_LABEL.planifie,
      teeth: idsPlanifie,
      fillColor: COULEUR_PLANIFIE_FILL,
      outlineColor: COULEUR_PLANIFIE_OUTLINE,
    });

  horsSchema.realise.sort();
  horsSchema.planifie.sort();
  return { conditions, etatParId, horsSchema, aDesDents: realise.size > 0 || planifie.size > 0 };
}

function Pastille({ color }: { color: string }) {
  return <span className="size-2.5 rounded-full" style={{ backgroundColor: color }} />;
}

export function OdontogrammeClinique({
  clinical,
  denture,
  highlightFdis,
}: {
  clinical: Clinical;
  denture: Denture;
  /** Dents (FDI de l'app) à mettre en évidence — ex. acte survolé dans la liste. */
  highlightFdis?: string[];
}) {
  const { conditions, etatParId, horsSchema, aDesDents } = useMemo(
    () => deriveOdontogramme(clinical, denture),
    [clinical, denture],
  );

  // Groupe de mise en évidence (prioritaire : ajouté en dernier ⇒ écrase la couleur d'état).
  const highlightIds = useMemo(
    () => (highlightFdis ?? []).map((f) => fdiToToothId(f, denture)).filter((x): x is string => !!x),
    [highlightFdis, denture],
  );
  const conditionsAffichees = useMemo(
    () =>
      highlightIds.length
        ? [
            ...conditions,
            { label: "Survolé", teeth: highlightIds, fillColor: COULEUR_SURVOL, outlineColor: COULEUR_SURVOL },
          ]
        : conditions,
    [conditions, highlightIds],
  );

  const maxTeeth = denture === "enfant" ? 5 : 8;
  const aHorsSchema = horsSchema.realise.length > 0 || horsSchema.planifie.length > 0;
  const highlightSet = useMemo(() => new Set(highlightFdis ?? []), [highlightFdis]);

  const renderTooltip = (tooth?: ToothDetail) => {
    if (!tooth) return null;
    const fdi = toothIdToFdi(tooth.id, denture);
    const etat = etatParId.get(tooth.id);
    return etat ? `Dent ${fdi} · ${ETAT_LABEL[etat]}` : `Dent ${fdi}`;
  };

  return (
    <section className="space-y-2 rounded-[var(--radius)] border border-line bg-white p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-navy">Schéma dentaire</h3>
        <span className="text-xs text-muted">
          {denture === "enfant" ? "Denture temporaire" : "Denture permanente"}
        </span>
      </div>
      <div className="mx-auto w-full max-w-sm overflow-x-auto">
        <Odontogram
          readOnly
          notation="FDI"
          maxTeeth={maxTeeth}
          teethConditions={conditionsAffichees}
          showLabels={false}
          layout="square"
          tooltip={{ content: renderTooltip }}
        />
      </div>
      {aDesDents && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
          <span className="inline-flex items-center gap-1.5">
            <Pastille color={COULEUR_REALISE} /> Réalisé
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Pastille color={COULEUR_PLANIFIE_FILL} /> Planifié
          </span>
          {highlightIds.length > 0 && (
            <span className="inline-flex items-center gap-1.5">
              <Pastille color={COULEUR_SURVOL} /> Acte survolé
            </span>
          )}
        </div>
      )}
      {aHorsSchema && (
        <div className="space-y-1 border-t border-line pt-2 text-xs">
          <div className="font-medium text-muted">
            {denture === "enfant" ? "Dents permanentes / autres" : "Dents de lait / autres"}
          </div>
          {(["realise", "planifie"] as const).map((etat) =>
            horsSchema[etat].length ? (
              <div key={etat} className="flex flex-wrap items-center gap-1">
                <span className="text-muted">{ETAT_LABEL[etat]} :</span>
                {horsSchema[etat].map((d) => (
                  <span
                    key={d}
                    className={cn(
                      "rounded px-1.5 py-0.5 font-medium tabular-nums",
                      highlightSet.has(d) ? "bg-amber text-white" : "bg-bg text-ink",
                    )}
                  >
                    {d}
                  </span>
                ))}
              </div>
            ) : null,
          )}
        </div>
      )}
    </section>
  );
}
