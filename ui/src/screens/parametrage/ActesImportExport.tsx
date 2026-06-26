import { useRef, useState, type ChangeEvent } from "react";
import { toast } from "sonner";
import { Download, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { humanizeError } from "@/lib/errors";
import { useExportActes, useImportActes } from "@/hooks/queries";
import type { ActeImport } from "@/api/types";

/**
 * Boutons « Exporter / Importer » du référentiel d'actes (.xlsx) + compte-rendu
 * d'import. Flux aller-retour : on exporte (le classeur porte une colonne ID,
 * clé de rapprochement), on édite/ajoute des lignes, on réimporte. L'export suit
 * le filtre « inclure les inactifs » courant (`includeInactive`).
 */
export function ActesImportExport({ includeInactive }: { includeInactive: boolean }) {
  const exportActes = useExportActes();
  const importActes = useImportActes();
  const fileRef = useRef<HTMLInputElement>(null);
  const [report, setReport] = useState<ActeImport | null>(null);

  function onExport() {
    exportActes.mutate(includeInactive, {
      onSuccess: (r) =>
        toast.success(
          `Référentiel exporté (${r.count} acte(s)). Le fichier s'ouvre dans Excel.`,
          { description: r.path },
        ),
      onError: (e) => toast.error(humanizeError(e)),
    });
  }

  function onFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // permet de réimporter le même fichier de suite
    if (!file) return;
    importActes.mutate(file, {
      onSuccess: (r) => {
        setReport(r);
        toast.success(
          `Import terminé : ${r.created} créé(s), ${r.updated} mis à jour` +
            (r.skipped ? `, ${r.skipped} ignoré(s)` : "") +
            ".",
        );
      },
      onError: (err) => toast.error(humanizeError(err)),
    });
  }

  return (
    <>
      <input
        ref={fileRef}
        type="file"
        accept=".xlsx"
        className="hidden"
        onChange={onFile}
      />
      <Button variant="secondary" onClick={onExport} disabled={exportActes.isPending}>
        <Download className="size-4" /> Exporter
      </Button>
      <Button
        variant="secondary"
        onClick={() => fileRef.current?.click()}
        disabled={importActes.isPending}
      >
        <Upload className="size-4" /> Importer
      </Button>

      <Dialog open={!!report} onOpenChange={(o) => !o && setReport(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Compte-rendu de l'import</DialogTitle>
          </DialogHeader>
          {report && (
            <div className="space-y-3 py-2 text-sm">
              <ul className="space-y-1 text-ink">
                <li>
                  Actes créés : <strong>{report.created}</strong>
                </li>
                <li>
                  Actes mis à jour : <strong>{report.updated}</strong>
                </li>
                <li>
                  Lignes ignorées : <strong>{report.skipped}</strong>
                </li>
              </ul>
              {report.errors.length > 0 && (
                <div className="space-y-1">
                  <p className="font-medium text-red">Lignes non importées :</p>
                  <ul className="max-h-48 space-y-1 overflow-auto rounded-[var(--radius)] border border-line bg-white p-2 text-xs text-muted">
                    {report.errors.map((msg, i) => (
                      <li key={i}>{msg}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button onClick={() => setReport(null)}>Fermer</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
