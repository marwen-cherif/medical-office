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
import { MoneySummary } from "@/components/common/MoneySummary";
import { humanizeError } from "@/lib/errors";
import { fmtDevise, isoToFr } from "@/lib/format";
import {
  useGenerate,
  useGenerationForm,
  useGenerationTemplates,
  useSaveDraft,
} from "@/hooks/documents";
import type { DocumentT, GenActeLine } from "@/api/types";
import { ActeCard, acteToPayload, emptyActe, type ActeValue } from "./ActeCard";

type Mode = "note" | "generic";

export function GenerateDialog({
  patientId,
  open,
  mode,
  draft,
  defaultDenture,
  onClose,
}: {
  patientId: number;
  open: boolean;
  mode: Mode;
  draft?: DocumentT | null;
  defaultDenture?: "adulte" | "enfant";
  onClose: () => void;
}) {
  const genMode = draft ? "all" : mode;
  const templates = useGenerationTemplates(genMode, open);
  const saveDraft = useSaveDraft(patientId);
  const generate = useGenerate(patientId);

  const [template, setTemplate] = useState<string>("");
  const [format, setFormat] = useState<string>("jpg");
  const [mono, setMono] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [cards, setCards] = useState<ActeValue[]>([]);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState<string>("");

  const form = useGenerationForm(open ? patientId : null, template || null, draft?.id ?? null);

  // Sélection initiale du modèle à l'ouverture.
  useEffect(() => {
    if (!open) return;
    if (draft?.template) setTemplate(draft.template);
    else if (templates.data && templates.data.length) setTemplate(templates.data[0].name);
    setFormat(draft?.output_format ?? "jpg");
    setError("");
    setProgress("");
  }, [open, templates.data, draft]);

  // Initialise les champs / la sélection quand le formulaire du modèle est chargé.
  useEffect(() => {
    if (!form.data) return;
    if (form.data.is_multiligne) {
      const ids = new Set<number>();
      const collect = (lines: GenActeLine[]) => lines.forEach((l) => l.checked && ids.add(l.id));
      collect(form.data.actes?.isoles ?? []);
      (form.data.actes?.plans ?? []).forEach((g) => collect(g.prestations));
      setSelected(ids);
      setCards([]);
    } else {
      const init: Record<string, string> = {};
      (form.data.fields ?? []).forEach((f) => (init[f.tag] = f.value ?? ""));
      setMono(init);
    }
  }, [form.data]);

  const allLines = useMemo(() => {
    if (!form.data?.is_multiligne) return [] as GenActeLine[];
    return [
      ...(form.data.actes?.isoles ?? []),
      ...(form.data.actes?.plans ?? []).flatMap((g) => g.prestations),
    ];
  }, [form.data]);

  const totals = useMemo(() => {
    let du = 0;
    let regle = 0;
    for (const l of allLines)
      if (selected.has(l.id)) {
        du += l.montant;
        regle += l.montant_regle;
      }
    for (const c of cards) if (c.libelle.trim()) du += Number((c.montant || "0").replace(",", ".")) || 0;
    return { du, regle, reste: du - regle };
  }, [allLines, selected, cards]);

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
      return {
        template,
        output_format: format,
        document_id: draft?.id ?? null,
        is_note: mode === "note",
        selected_prestation_ids: [...selected],
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
    generate.mutate(
      {
        body: buildBody(do_print) as never,
        onEvent: (e) => {
          if (e.type === "progress") setProgress(e.message || "");
        },
      },
      {
        onSuccess: () => {
          toast.success(do_print ? "Document généré et imprimé." : "Document généré.");
          onClose();
        },
        onError: (e) => {
          setProgress("");
          setError(humanizeError(e));
        },
      },
    );
  }

  const title = draft
    ? "Modifier le brouillon"
    : mode === "note"
      ? "Note d'honoraires"
      : "Nouveau document";
  const busy = generate.isPending || saveDraft.isPending;

  const ActeGroup = ({ titre, lines }: { titre: string; lines: GenActeLine[] }) =>
    lines.length ? (
      <div className="space-y-1">
        <div className="text-xs font-semibold text-navy">{titre} ({lines.length})</div>
        {lines.map((l) => (
          <label key={l.id} className="flex items-center gap-2 text-sm text-ink">
            <Checkbox checked={selected.has(l.id)} onCheckedChange={() => toggle(l.id)} />
            <span className="flex-1">
              {l.date_acte ? `${isoToFr(l.date_acte)} · ` : ""}
              {l.libelle} · {fmtDevise(l.montant)}
              {l.reste > 0 && Math.abs(l.reste - l.montant) > 1e-9 ? (
                <span className="text-muted"> (reste {fmtDevise(l.reste)})</span>
              ) : null}
            </span>
          </label>
        ))}
      </div>
    ) : null;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
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
                <ActeGroup titre="Actes isolés" lines={form.data.actes?.isoles ?? []} />
                {(form.data.actes?.plans ?? []).map((g, i) => (
                  <ActeGroup key={i} titre={g.titre} lines={g.prestations} />
                ))}
                {allLines.length === 0 && (
                  <p className="text-xs text-muted">Aucun acte existant pour ce patient.</p>
                )}
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Nouveaux actes</Label>
                  <Button variant="secondary" size="sm" onClick={() => setCards((c) => [...c, emptyActe()])}>
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
                  {f.type === "paragraph" ? (
                    <Textarea rows={3} value={mono[f.tag] ?? ""}
                              onChange={(e) => setMono((m) => ({ ...m, [f.tag]: e.target.value }))} />
                  ) : (
                    <Input
                      type={f.type === "date" ? "date" : f.type === "number" ? "text" : "text"}
                      inputMode={f.type === "number" ? "decimal" : undefined}
                      value={mono[f.tag] ?? ""}
                      onChange={(e) => setMono((m) => ({ ...m, [f.tag]: e.target.value }))}
                    />
                  )}
                </div>
              ))}
            </div>
          )}

          {progress && <p className="text-sm text-navy">{progress}</p>}
          {error && <p className="text-xs text-red">{error}</p>}
        </div>
        <DialogFooter className="flex-wrap gap-2">
          <Button variant="secondary" onClick={onClose} disabled={busy}>Annuler</Button>
          <Button variant="secondary" onClick={onSaveDraft} disabled={busy}>
            <Save className="size-4" /> {draft ? "Enregistrer" : "Brouillon"}
          </Button>
          <Button onClick={() => onGenerate(false)} disabled={busy}>
            <PlayCircle className="size-4" /> Générer
          </Button>
          <Button onClick={() => onGenerate(true)} disabled={busy}>
            <Printer className="size-4" /> Générer et imprimer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
