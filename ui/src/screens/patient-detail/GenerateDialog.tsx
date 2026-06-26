import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Plus, PlayCircle, Printer, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DatePicker } from "@/components/common/DatePicker";
import { MoneySummary } from "@/components/common/MoneySummary";
import { Odontogramme } from "@/components/common/Odontogramme";
import { humanizeError } from "@/lib/errors";
import { fmtDevise, isoToFr, parseDents } from "@/lib/format";
import { Montant } from "@/components/common/Montant";
import {
  useGenerate,
  useGenerationForm,
  useGenerationTemplates,
  useSaveDraft,
  useTrackJob,
} from "@/hooks/documents";
import type { DocumentT, GenActeLine } from "@/api/types";
import { ActeCard, acteToPayload, emptyActe, type ActeValue } from "./ActeCard";

type Mode = "note" | "generic";

/** Montant de note retenu pour un acte : saisie éditée si présente, sinon le défaut. */
function noteMontantValue(l: GenActeLine, raw: string | undefined): number {
  if (raw == null || raw === "") return l.montant_note ?? l.montant;
  return Number(raw.replace(",", ".")) || 0;
}

/**
 * Groupe de lignes d'actes d'une note multi-lignes (case à cocher + montant de note
 * éditable). Défini au niveau module : s'il était interne à GenerateDialog, il serait
 * recréé à chaque frappe et l'input perdrait le focus (remontage).
 */
function ActeGroup({
  titre,
  lines,
  selected,
  montants,
  onToggle,
  onMontant,
}: {
  titre: string;
  lines: GenActeLine[];
  selected: Set<number>;
  montants: Record<number, string>;
  onToggle: (id: number) => void;
  onMontant: (id: number, value: string) => void;
}) {
  if (!lines.length) return null;
  return (
    <div className="space-y-1">
      <div className="text-xs font-semibold text-navy">
        {titre} ({lines.length})
      </div>
      {lines.map((l) => {
        const isChecked = selected.has(l.id);
        // Écart montant de note ↔ montant de l'acte (l'acte reste la source du dû).
        const differs = isChecked && Math.abs(noteMontantValue(l, montants[l.id]) - l.montant) > 1e-9;
        return (
          <div key={l.id} className="flex items-center gap-2 text-sm text-ink">
            {/* <label> natif : cliquer le texte coche la case Radix (élément « labelable »),
                et la case reste focusable au clavier (Tab + Espace) — pas de span cliquable. */}
            <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-2">
              <Checkbox checked={isChecked} onCheckedChange={() => onToggle(l.id)} />
              <span className="min-w-0 flex-1 truncate">
                {l.date_acte ? `${isoToFr(l.date_acte)} · ` : ""}
                {l.libelle}
                {l.reste > 0 && Math.abs(l.reste - l.montant) > 1e-9 ? (
                  <span className="text-muted"> (reste {fmtDevise(l.reste)})</span>
                ) : null}
              </span>
            </label>
            {isChecked ? (
              <div className="flex shrink-0 items-center gap-1">
                {differs && (
                  <span className="text-[11px] text-muted line-through" title="Montant de l'acte">
                    {fmtDevise(l.montant)}
                  </span>
                )}
                <Input
                  className="h-8 w-24 text-right tabular-nums"
                  inputMode="decimal"
                  aria-label={`Montant de note — ${l.libelle}`}
                  value={montants[l.id] ?? ""}
                  placeholder={String(l.montant)}
                  onChange={(e) => onMontant(l.id, e.target.value)}
                />
              </div>
            ) : (
              <Montant value={l.montant} tone="muted" className="shrink-0" />
            )}
          </div>
        );
      })}
    </div>
  );
}

export function GenerateDialog({
  patientId,
  open,
  mode,
  draft,
  defaultDenture,
  initialSelection,
  onClose,
}: {
  patientId: number;
  open: boolean;
  mode: Mode;
  draft?: DocumentT | null;
  defaultDenture?: "adulte" | "enfant";
  /** Actes pré-cochés à l'ouverture (depuis la page Actes/Plans). Ignoré en mode brouillon. */
  initialSelection?: number[];
  onClose: () => void;
}) {
  const genMode = draft ? "all" : mode;
  const templates = useGenerationTemplates(genMode, open);
  const saveDraft = useSaveDraft(patientId);
  const generate = useGenerate(patientId);
  const trackJob = useTrackJob();

  const [template, setTemplate] = useState<string>("");
  const [format, setFormat] = useState<string>("jpg");
  const [mono, setMono] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState<Set<number>>(new Set());
  // Montant de note édité par acte (prestation_id → saisie). Affichage seul : ne
  // modifie ni l'acte ni la dette (défaut = montant de l'acte / montant édité du brouillon).
  const [montants, setMontants] = useState<Record<number, string>>({});
  const [cards, setCards] = useState<ActeValue[]>([]);
  const [error, setError] = useState("");

  // Note depuis UN seul acte : on pré-remplit un modèle mono-valeur avec les données
  // de cet acte (le backend mappe ACTE/MONTANT/DATE/…). Plusieurs actes => multi-lignes.
  const singleActeId =
    !draft && initialSelection && initialSelection.length === 1 ? initialSelection[0] : null;
  const form = useGenerationForm(
    open ? patientId : null,
    template || null,
    draft?.id ?? null,
    singleActeId,
  );

  // Sélection initiale du modèle à l'ouverture.
  useEffect(() => {
    if (!open) return;
    const tpls = templates.data ?? [];
    if (draft?.template) {
      setTemplate(draft.template);
    } else if (initialSelection && initialSelection.length >= 2) {
      // Plusieurs actes : un modèle multi-lignes est requis pour tous les rendre.
      const ml = tpls.find((t) => t.is_multiligne) ?? tpls[0];
      setTemplate(ml?.name ?? "");
    } else if (initialSelection) {
      // Depuis Actes/Plans avec 0 ou 1 acte : modèle mono-valeur (note sans acte, ou
      // note pré-remplie depuis l'acte unique).
      const monoT = tpls.find((t) => !t.is_multiligne) ?? tpls[0];
      setTemplate(monoT?.name ?? "");
    } else if (tpls.length) {
      setTemplate(tpls[0].name);
    }
    setFormat(draft?.output_format ?? "jpg");
    setError("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, templates.data, draft]);

  // Initialise les champs / la sélection quand le formulaire du modèle est chargé.
  // Dépend aussi de `open` : à la réouverture, le form est servi depuis le cache
  // react-query (même référence) ; sans `open` l'effet ne se relancerait pas et la
  // pré-sélection ne serait pas réappliquée.
  useEffect(() => {
    if (!open || !form.data) return;
    if (form.data.is_multiligne) {
      const lines = [
        ...(form.data.actes?.isoles ?? []),
        ...(form.data.actes?.plans ?? []).flatMap((g) => g.prestations),
      ];
      const ids = new Set<number>();
      if (initialSelection && !draft) {
        // Pré-sélection venue de la page Actes/Plans (acte unique ou multi-sélection).
        const avail = new Set(lines.map((l) => l.id));
        initialSelection.forEach((id) => avail.has(id) && ids.add(id));
      } else {
        lines.forEach((l) => l.checked && ids.add(l.id));
      }
      setSelected(ids);
      // Montant de note par défaut = montant_note (acte, ou montant édité d'un brouillon).
      const initM: Record<number, string> = {};
      lines.forEach((l) => (initM[l.id] = String(l.montant_note ?? l.montant)));
      setMontants(initM);
      setCards([]);
    } else {
      const init: Record<string, string> = {};
      (form.data.fields ?? []).forEach((f) => (init[f.tag] = f.value ?? ""));
      setMono(init);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, form.data]);

  const allLines = useMemo(() => {
    if (!form.data?.is_multiligne) return [] as GenActeLine[];
    return [
      ...(form.data.actes?.isoles ?? []),
      ...(form.data.actes?.plans ?? []).flatMap((g) => g.prestations),
    ];
  }, [form.data]);

  // Montant de note retenu pour un acte : saisie éditée si présente, sinon le défaut.
  const lineMontant = (l: GenActeLine) => noteMontantValue(l, montants[l.id]);

  const totals = useMemo(() => {
    let du = 0;
    let regle = 0;
    for (const l of allLines)
      if (selected.has(l.id)) {
        du += lineMontant(l);
        regle += l.montant_regle;
      }
    for (const c of cards) if (c.libelle.trim()) du += Number((c.montant || "0").replace(",", ".")) || 0;
    return { du, regle, reste: du - regle };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allLines, selected, cards, montants]);

  function toggle(id: number) {
    setSelected((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  }

  function buildBody(do_print = false) {
    if (form.data?.is_multiligne) {
      // Montant de note par acte retenu (affichage seul, n'altère pas l'acte côté backend).
      const montants_notes: Record<number, number> = {};
      for (const l of allLines) if (selected.has(l.id)) montants_notes[l.id] = lineMontant(l);
      return {
        template,
        output_format: format,
        document_id: draft?.id ?? null,
        is_note: mode === "note",
        selected_prestation_ids: [...selected],
        montants_notes,
        new_actes: cards.filter((c) => c.libelle.trim()).map(acteToPayload),
        ...(do_print ? { do_print: true } : {}),
      };
    }
    return {
      template,
      output_format: format,
      document_id: draft?.id ?? null,
      is_note: mode === "note",
      variables: mono,
      // Note mono-valeur générée depuis un acte : on transmet l'acte source pour que
      // le backend la considère adossée (pas de créance ; l'acte porte le dû).
      selected_prestation_ids: singleActeId != null ? [singleActeId] : [],
      ...(do_print ? { do_print: true } : {}),
    };
  }

  function onSaveDraft() {
    if (!template) return setError("Sélectionnez un modèle.");
    saveDraft.mutate(buildBody() as never, {
      onSuccess: () => {
        toast.success(draft ? "Brouillon mis à jour." : "Brouillon enregistré.");
        onClose();
      },
      onError: (e) => setError(humanizeError(e)),
    });
  }

  function onGenerate(do_print: boolean) {
    if (!template) return setError("Sélectionnez un modèle.");
    setError("");
    // Le POST est rapide : il valide (ex. imprimante pour « Générer et imprimer »)
    // puis renvoie le job_id. On suit le rendu Word en arrière-plan via un toast et on
    // ferme le dialogue tout de suite, pour libérer l'interface — l'utilisateur peut
    // continuer à travailler pendant la génération. Une erreur synchrone (validation)
    // garde le dialogue ouvert avec le message.
    generate.mutate(buildBody(do_print) as never, {
      onSuccess: (jobId) => {
        trackJob(jobId, {
          loading: do_print ? "Génération et impression en cours…" : "Génération en cours…",
          success: do_print ? "Document généré et imprimé." : "Document généré.",
          patientId,
        });
        onClose();
      },
      onError: (e) => setError(humanizeError(e)),
    });
  }

  const title = draft
    ? "Modifier le brouillon"
    : mode === "note"
      ? "Note d'honoraires"
      : "Nouveau document";
  const busy = generate.isPending || saveDraft.isPending;
  const onMontant = (id: number, value: string) => setMontants((m) => ({ ...m, [id]: value }));

  return (
    <Dialog open={open} onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        {/* Entrée dans un champ déclenche l'action principale « Générer » (do_print=false).
            Les autres actions (Brouillon, Générer et imprimer, Annuler) sont type="button". */}
        <form className="grid gap-4 [&>*]:min-w-0" onSubmit={(e) => { e.preventDefault(); if (!busy) onGenerate(false); }}>
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="grid grid-cols-[1fr_8rem] gap-3">
              <div className="space-y-2">
                <Label>Modèle / type de document</Label>
                <Select value={template} onValueChange={setTemplate} disabled={!!draft}>
                  <SelectTrigger>
                    <SelectValue placeholder="Choisir un modèle…" />
                  </SelectTrigger>
                  <SelectContent>
                    {(templates.data ?? []).map((t) => (
                      <SelectItem key={t.name} value={t.name}>{t.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Format</Label>
                <Select value={format} onValueChange={setFormat}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="jpg">JPG</SelectItem>
                    <SelectItem value="pdf">PDF</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {templates.data && templates.data.length === 0 && (
              <p className="text-sm text-amber">
                {mode === "note"
                  ? "Aucun modèle dans la catégorie des notes d'honoraires. Configurez-en un dans Paramétrage › Modèles."
                  : "Aucun modèle disponible. Créez-en un dans Paramétrage › Modèles."}
              </p>
            )}

            {form.isLoading && <p className="text-sm text-muted">Chargement du modèle…</p>}

            {/* Modèle multi-lignes : sélection d'actes + nouveaux actes */}
            {form.data?.is_multiligne && (
              <div className="space-y-3">
                <div className="space-y-2 rounded-[var(--radius)] border border-line bg-bg/40 p-3">
                  <div className="text-sm font-semibold text-ink">Actes à facturer</div>
                  <ActeGroup
                    titre="Actes isolés"
                    lines={form.data.actes?.isoles ?? []}
                    selected={selected}
                    montants={montants}
                    onToggle={toggle}
                    onMontant={onMontant}
                  />
                  {(form.data.actes?.plans ?? []).map((g, i) => (
                    <ActeGroup
                      key={i}
                      titre={g.titre}
                      lines={g.prestations}
                      selected={selected}
                      montants={montants}
                      onToggle={toggle}
                      onMontant={onMontant}
                    />
                  ))}
                  {allLines.length === 0 && (
                    <p className="text-xs text-muted">Aucun acte existant pour ce patient.</p>
                  )}
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>Nouveaux actes</Label>
                    <Button type="button" variant="secondary" size="sm" onClick={() => setCards((c) => [...c, emptyActe()])}>
                      <Plus className="size-4" /> Ajouter un acte
                    </Button>
                  </div>
                  <p className="text-xs text-muted">
                    Créés comme actes isolés (suivis dans la dette, visibles dans l'onglet Plans &amp; actes).
                  </p>
                  {cards.map((c, i) => (
                    <ActeCard
                      key={i}
                      value={c}
                      defaultDenture={defaultDenture}
                      onChange={(v) => setCards((arr) => arr.map((x, j) => (j === i ? v : x)))}
                      onRemove={() => setCards((arr) => arr.filter((_, j) => j !== i))}
                    />
                  ))}
                </div>
                <MoneySummary
                  items={[
                    { label: "Total dû", value: totals.du },
                    { label: "Réglé", value: totals.regle, tone: "green" },
                    { label: "Reste à payer", value: totals.reste, tone: "amber" },
                  ]}
                />
              </div>
            )}

            {/* Modèle mono-valeur : champs dynamiques */}
            {form.data && !form.data.is_multiligne && (
              <div className="space-y-3">
                {(form.data.fields ?? []).length === 0 && (
                  <p className="text-sm text-muted">Aucune variable à saisir pour ce modèle.</p>
                )}
                {(form.data.fields ?? []).map((f) => (
                  <div key={f.tag} className="space-y-2">
                    <Label>{f.label || f.tag}</Label>
                    {f.tag.toUpperCase() === "DENTS" ? (
                      // Bloc de selection FDI (alimente <DENTS>/<NB_DENTS>/<ODONTOGRAMME>) :
                      // utile notamment pour une note autonome (sans acte rattache).
                      <Odontogramme
                        value={parseDents(mono[f.tag] ?? "")}
                        onChange={(dents) =>
                          setMono((m) => ({ ...m, [f.tag]: dents.join(", ") }))
                        }
                        defaultDenture={defaultDenture}
                      />
                    ) : f.type === "paragraph" ? (
                      <Textarea rows={3} value={mono[f.tag] ?? ""}
                                onChange={(e) => setMono((m) => ({ ...m, [f.tag]: e.target.value }))} />
                    ) : f.type === "date" ? (
                      <DatePicker
                        value={mono[f.tag] ?? ""}
                        onChange={(iso) => setMono((m) => ({ ...m, [f.tag]: iso }))}
                      />
                    ) : (
                      <Input
                        type="text"
                        inputMode={f.type === "number" ? "decimal" : undefined}
                        value={mono[f.tag] ?? ""}
                        onChange={(e) => setMono((m) => ({ ...m, [f.tag]: e.target.value }))}
                      />
                    )}
                  </div>
                ))}
              </div>
            )}

            {error && <p className="text-xs text-red">{error}</p>}
          </div>
          <DialogFooter className="flex-wrap gap-2">
            <Button type="button" variant="secondary" onClick={onClose} disabled={busy}>Annuler</Button>
            <Button type="button" variant="secondary" onClick={onSaveDraft} disabled={busy}>
              <Save className="size-4" /> {draft ? "Enregistrer" : "Brouillon"}
            </Button>
            <Button type="submit" disabled={busy}>
              <PlayCircle className="size-4" /> Générer
            </Button>
            <Button type="button" onClick={() => onGenerate(true)} disabled={busy}>
              <Printer className="size-4" /> Générer et imprimer
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
