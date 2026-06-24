import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { MoneySummary } from "@/components/common/MoneySummary";
import { PatientFormDialog } from "@/components/dialogs/PatientFormDialog";
import { humanizeError } from "@/lib/errors";
import { isoToFr } from "@/lib/format";
import { usePatient } from "@/hooks/patients";
import type { Patient } from "@/api/types";
import { PlansActesTab } from "./patient-detail/PlansActesTab";
import { DocumentsTab } from "./patient-detail/DocumentsTab";
import { ReglementsTab } from "./patient-detail/ReglementsTab";
import { HistoriqueTab } from "./patient-detail/HistoriqueTab";

/** Denture par défaut selon l'âge (enfant si < 13 ans). */
export function dentureFor(dateNaissance: string | null | undefined): "adulte" | "enfant" {
  if (!dateNaissance) return "adulte";
  const d = new Date(dateNaissance);
  if (isNaN(d.getTime())) return "adulte";
  const age = (Date.now() - d.getTime()) / (365.25 * 24 * 3600 * 1000);
  return age < 13 ? "enfant" : "adulte";
}

function IdRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="flex justify-between gap-3 py-1 text-sm">
      <span className="text-muted">{label}</span>
      <span className="text-right text-ink">{value || "—"}</span>
    </div>
  );
}

export function PatientDetail() {
  const params = useParams();
  const navigate = useNavigate();
  const id = Number(params.id);
  const detail = usePatient(Number.isFinite(id) ? id : null);
  const [edit, setEdit] = useState<Patient | "new" | null>(null);

  if (detail.isLoading) return <div className="p-8 text-muted">Chargement…</div>;
  if (detail.isError) return <div className="p-8 text-red">{humanizeError(detail.error)}</div>;
  if (!detail.data) return <div className="p-8 text-muted">Patient introuvable.</div>;

  const { patient, solde } = detail.data;
  const denture = dentureFor(patient.date_naissance);

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="mb-4 flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate("/patients")} title="Retour">
          <ArrowLeft className="size-5" />
        </Button>
        <h1 className="flex-1 text-2xl font-semibold text-ink">{patient.display}</h1>
        <Button variant="secondary" onClick={() => setEdit(patient)}>
          <Pencil className="size-4" /> Modifier
        </Button>
      </div>

      <div className="flex flex-col gap-6 lg:flex-row">
        <aside className="space-y-4 lg:w-72 lg:shrink-0">
          <div className="rounded-[var(--radius)] border border-line bg-white p-4">
            <IdRow label="Email" value={patient.email} />
            <IdRow label="Téléphone" value={patient.telephone} />
            <IdRow label="Naissance" value={isoToFr(patient.date_naissance)} />
            <IdRow label="Adresse" value={patient.adresse} />
            {patient.notes && (
              <div className="mt-2 border-t border-line pt-2 text-sm">
                <div className="text-muted">Notes</div>
                <div className="whitespace-pre-wrap text-ink">{patient.notes}</div>
              </div>
            )}
          </div>
          <MoneySummary
            layout="column"
            items={[
              { label: "Dû", value: solde.du },
              { label: "Encaissé", value: solde.encaisse, tone: "green" },
              { label: "Reste", value: solde.reste, tone: "amber" },
            ]}
          />
        </aside>

        <div className="min-w-0 flex-1">
          <Tabs defaultValue="plans">
            <TabsList>
              <TabsTrigger value="plans">Plans &amp; actes</TabsTrigger>
              <TabsTrigger value="documents">Documents</TabsTrigger>
              <TabsTrigger value="reglements">Règlements</TabsTrigger>
              <TabsTrigger value="historique">Historique</TabsTrigger>
            </TabsList>
            <TabsContent value="plans">
              <PlansActesTab patientId={id} denture={denture} />
            </TabsContent>
            <TabsContent value="documents">
              <DocumentsTab patient={patient} denture={denture} />
            </TabsContent>
            <TabsContent value="reglements">
              <ReglementsTab patientId={id} />
            </TabsContent>
            <TabsContent value="historique">
              <HistoriqueTab patientId={id} />
            </TabsContent>
          </Tabs>
        </div>
      </div>

      <PatientFormDialog target={edit} onClose={() => setEdit(null)} />
    </div>
  );
}
