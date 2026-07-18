import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Bell, Pencil } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { MoneySummary } from '@/components/common/MoneySummary';
import { Tooltip } from '@/components/common/Tooltip';
import { PatientFormDialog } from '@/components/dialogs/PatientFormDialog';
import { humanizeError } from '@/lib/errors';
import { isoToFr } from '@/lib/format';
import { useShortcut } from '@/lib/shortcuts';
import { usePatient } from '@/hooks/patients';
import type { Patient, Rappel } from '@/api/types';
import { PlansActesTab } from './patient-detail/PlansActesTab';
import { DocumentsTab } from './patient-detail/DocumentsTab';
import { ReglementsTab } from './patient-detail/ReglementsTab';
import { HistoriqueTab } from './patient-detail/HistoriqueTab';
import { RappelsTab } from './patient-detail/RappelsTab';
import { RappelFormDialog } from './rappels/RappelFormDialog';
import { ClickToCopy } from '@/components/ui/click-to-copy';
import { WhatsAppIcon } from '@/components/icons/WhatsAppIcon';

/** Denture par défaut selon l'âge (enfant si < 13 ans). */
export function dentureFor(dateNaissance: string | null | undefined): 'adulte' | 'enfant' {
  if (!dateNaissance) return 'adulte';
  const d = new Date(dateNaissance);
  if (isNaN(d.getTime())) return 'adulte';
  const age = (Date.now() - d.getTime()) / (365.25 * 24 * 3600 * 1000);
  return age < 13 ? 'enfant' : 'adulte';
}

function IdRow({
  label,
  value,
  multiline,
}: {
  label: string;
  value?: string | null;
  multiline?: boolean;
}) {
  return (
    <div
      className={`flex justify-between gap-3 py-1 text-sm ${multiline ? 'items-start' : 'items-center'}`}
    >
      <span className="text-muted">{label}</span>
      {value ? (
        <ClickToCopy
          text={value}
          multiline={multiline}
          className="text-right text-ink max-w-[180px] lg:max-w-none"
        />
      ) : (
        <span className="text-right text-ink">—</span>
      )}
    </div>
  );
}

export function PatientDetail() {
  const params = useParams();
  const navigate = useNavigate();
  const id = Number(params.id);
  const detail = usePatient(Number.isFinite(id) ? id : null);
  const [edit, setEdit] = useState<Patient | 'new' | null>(null);
  const [rappelTarget, setRappelTarget] = useState<Rappel | 'new' | null>(null);

  // Hook appelé avant les retours anticipés (règles des hooks) ; le handler lit la
  // donnée la plus récente et reste inactif tant que le patient n'est pas chargé.
  useShortcut({
    keys: 'alt+e',
    description: 'Modifier le patient',
    group: 'Fiche patient',
    enabled: !!detail.data,
    handler: () => detail.data && setEdit(detail.data.patient),
  });
  useShortcut({
    keys: 'alt+p',
    description: 'Planifier un rappel',
    group: 'Fiche patient',
    enabled: !!detail.data,
    handler: () => setRappelTarget('new'),
  });

  if (detail.isLoading) return <div className="p-8 text-muted">Chargement…</div>;
  if (detail.isError) return <div className="p-8 text-red">{humanizeError(detail.error)}</div>;
  if (!detail.data) return <div className="p-8 text-muted">Patient introuvable.</div>;

  const { patient, solde } = detail.data;
  const denture = dentureFor(patient.date_naissance);

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="mb-4 flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate('/patients')} title="Retour">
          <ArrowLeft className="size-5" />
        </Button>
        <h1 className="flex-1 text-2xl font-semibold text-ink">{patient.display}</h1>
      </div>

      <div className="flex flex-col gap-6 lg:flex-row">
        <aside className="space-y-4 lg:w-72 lg:shrink-0">
          <div className="rounded-[var(--radius)] border border-line bg-white p-4">
            <IdRow label="Email" value={patient.email} />
            {patient.telephones && patient.telephones.length > 0 ? (
              <div className="my-2 border-t border-b border-line py-2 text-sm space-y-1">
                <div className="text-muted mb-1">Téléphones</div>
                {patient.telephones.map((t, idx) => (
                  <div key={idx} className="flex items-center justify-between gap-2 text-xs py-0.5">
                    <span className="bg-bg text-ink px-1.5 py-0.5 rounded text-[10px] font-medium border border-line select-none">
                      {t.relation}
                    </span>
                    <div className="flex items-center gap-1.5">
                      <ClickToCopy text={t.telephone} className="font-mono text-ink text-right" />
                      {t.is_whatsapp && (
                        <span
                          className="inline-flex items-center shrink-0"
                          title="Compatible WhatsApp"
                        >
                          <WhatsAppIcon className="size-3.5 text-emerald-600" />
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <IdRow label="Téléphone" value={patient.telephone} />
            )}
            <IdRow label="Naissance" value={isoToFr(patient.date_naissance)} />
            <IdRow label="Adresse" value={patient.adresse} multiline />
            {patient.notes && (
              <div className="mt-2 border-t border-line pt-2 text-sm">
                <div className="text-muted mb-1">Notes</div>
                <ClickToCopy text={patient.notes} multiline className="text-ink text-left w-full" />
              </div>
            )}
          </div>
          <MoneySummary
            layout="column"
            items={[
              { label: 'Dû', value: solde.du },
              { label: 'Encaissé', value: solde.encaisse, tone: 'green' },
              { label: 'Reste', value: solde.reste, tone: 'amber' },
            ]}
          />
        </aside>

        <div className="min-w-0 flex-1">
          <Tabs defaultValue="plans">
            <TabsList>
              <TabsTrigger value="plans">Plans &amp; actes</TabsTrigger>
              <TabsTrigger value="documents">Documents</TabsTrigger>
              <TabsTrigger value="reglements">Règlements</TabsTrigger>
              <TabsTrigger value="rappels">Rappels</TabsTrigger>
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
            <TabsContent value="rappels">
              <RappelsTab patientId={id} />
            </TabsContent>
            <TabsContent value="historique">
              <HistoriqueTab patientId={id} />
            </TabsContent>
          </Tabs>
        </div>
      </div>

      <PatientFormDialog target={edit} onClose={() => setEdit(null)} />
      <RappelFormDialog
        target={rappelTarget}
        onClose={() => setRappelTarget(null)}
        defaultPatientId={id}
      />

      {/* Boutons flottants d'action (Modifier + Planifier un rappel).
          Les classes `fixed` vont sur le conteneur du groupe (pas sur les Buttons
          ni sur les Tooltip wrappers) : sinon un bouton fixed sort du span
          `relative` de son Tooltip et l'infobulle se positionne mal.
          Tooltips en `side="left"` pour ne pas déborder du bord droit. */}
      <div className="fixed bottom-6 right-6 z-30 flex flex-col items-center gap-3">
        <Tooltip label="Modifier le patient" shortcut="alt+e" side="left">
          <Button
            variant="secondary"
            size="icon"
            className="size-12 rounded-full border border-line bg-white shadow-lg"
            onClick={() => setEdit(patient)}
          >
            <Pencil className="size-5" />
          </Button>
        </Tooltip>
        <Tooltip label="Planifier un rappel" shortcut="alt+p" side="left">
          <Button
            variant="default"
            size="icon"
            className="size-12 rounded-full shadow-lg"
            onClick={() => setRappelTarget('new')}
          >
            <Bell className="size-5" />
          </Button>
        </Tooltip>
      </div>
    </div>
  );
}
