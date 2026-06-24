import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, Printer, Save, TestTube2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { client, unwrap, type JobEvent } from "@/lib/api";
import { humanizeError, messageForCode } from "@/lib/errors";
import {
  usePrintConfig,
  usePrinters,
  useSetPrinter,
  useSetPrintConfig,
  useTestPrinter,
} from "@/hooks/queries";

const PAPERS = [
  { value: "__default__", label: "Défaut imprimante" },
  { value: "A4", label: "A4" },
  { value: "A5", label: "A5" },
];
const COLORS = [
  { value: "__default__", label: "Défaut imprimante" },
  { value: "color", label: "Couleur" },
  { value: "mono", label: "Noir & blanc" },
];

export function ImprimanteTab() {
  const printers = usePrinters();
  const setPrinter = useSetPrinter();
  const testPrinter = useTestPrinter();
  const setPrintConfig = useSetPrintConfig();

  const [selected, setSelected] = useState<string | null>(null);
  const [docType, setDocType] = useState<string | null>(null);
  const [paper, setPaper] = useState<string>("__default__");
  const [color, setColor] = useState<string>("__default__");
  const [progress, setProgress] = useState<{ value: number; message: string } | null>(null);

  const current = selected ?? printers.data?.selected ?? printers.data?.default ?? "";

  const printTypes = useQuery({
    queryKey: ["settings", "print-types"],
    queryFn: async () => unwrap(await client.GET("/api/settings/print-types")),
  });
  const config = usePrintConfig(docType);

  function onSelectType(t: string) {
    setDocType(t);
  }

  // Charge la config enregistrée du type dans les selects quand elle arrive.
  useEffect(() => {
    if (!config.data) return;
    setPaper(config.data.paper ?? "__default__");
    setColor(config.data.color ?? "__default__");
  }, [config.data]);

  function onSavePrinter() {
    if (!current) return;
    setPrinter.mutate(current, {
      onSuccess: () => toast.success("Imprimante enregistrée."),
      onError: (e) => toast.error(humanizeError(e)),
    });
  }

  function onSaveConfig() {
    if (!docType) return;
    setPrintConfig.mutate(
      {
        docType,
        paper: paper === "__default__" ? null : paper,
        color: color === "__default__" ? null : color,
      },
      {
        onSuccess: () => toast.success("Réglage du type enregistré."),
        onError: (e) => toast.error(humanizeError(e)),
      },
    );
  }

  function onTest() {
    if (!current) {
      toast.error("Sélectionnez une imprimante.");
      return;
    }
    setProgress({ value: 0, message: "Démarrage…" });
    testPrinter.mutate(
      {
        printerName: current,
        onEvent: (e: JobEvent) => {
          if (e.type === "progress") setProgress({ value: e.value, message: e.message });
        },
      },
      {
        onSuccess: () => {
          setProgress(null);
          toast.success("Page de test envoyée.");
        },
        onError: (e: unknown) => {
          setProgress(null);
          const body = e as { error?: { code?: string; message?: string } };
          toast.error(
            body.error?.code
              ? messageForCode(body.error.code, body.error.message)
              : humanizeError(e),
          );
        },
      },
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Printer className="size-4" /> Imprimante cible
          </CardTitle>
          <CardDescription>
            Imprimante utilisée pour l'impression directe des documents.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {printers.isLoading && <p className="text-sm text-muted">Chargement…</p>}
          {printers.isError && <p className="text-sm text-red">{humanizeError(printers.error)}</p>}
          <div className="space-y-2">
            <Label>Imprimante</Label>
            <Select value={current} onValueChange={setSelected}>
              <SelectTrigger><SelectValue placeholder="Choisir…" /></SelectTrigger>
              <SelectContent>
                {(printers.data?.printers ?? []).map((p) => (
                  <SelectItem key={p} value={p}>{p}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {printers.data?.default && (
              <p className="text-xs text-muted">Par défaut Windows : {printers.data.default}</p>
            )}
          </div>
          <div className="flex gap-2">
            <Button onClick={onSavePrinter} disabled={setPrinter.isPending || !current}>
              <Save className="size-4" /> Enregistrer
            </Button>
            <Button variant="secondary" onClick={onTest} disabled={testPrinter.isPending || !current}>
              {testPrinter.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <TestTube2 className="size-4" />
              )}
              Test d'impression
            </Button>
          </div>
          {progress && (
            <div className="space-y-1">
              <div className="h-2 w-full overflow-hidden rounded-full bg-bg">
                <div
                  className="h-full bg-navy transition-all"
                  style={{ width: `${Math.round(progress.value * 100)}%` }}
                />
              </div>
              <p className="text-xs text-muted">{progress.message}</p>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Format & couleur par type</CardTitle>
          <CardDescription>
            Format papier et couleur appliqués silencieusement à l'impression d'un type de document.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Type de document</Label>
            <Select value={docType ?? ""} onValueChange={onSelectType}>
              <SelectTrigger><SelectValue placeholder="Choisir un type…" /></SelectTrigger>
              <SelectContent>
                {(printTypes.data?.types ?? []).map((t: string) => (
                  <SelectItem key={t} value={t}>{t}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>Format</Label>
              <Select value={paper} onValueChange={setPaper} disabled={!docType}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {PAPERS.map((p) => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Couleur</Label>
              <Select value={color} onValueChange={setColor} disabled={!docType}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {COLORS.map((c) => <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <Button onClick={onSaveConfig} disabled={!docType || setPrintConfig.isPending}>
            <Save className="size-4" /> Enregistrer le réglage
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
