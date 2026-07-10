import { useState } from 'react';
import { toast } from 'sonner';
import {
  ExternalLink,
  FileImage,
  FileText,
  FolderOpen,
  MessageSquare,
  Pencil,
  PlayCircle,
  Printer,
  RefreshCw,
  Send,
  Trash2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Pagination } from '@/components/common/Pagination';
import { RowActions } from '@/components/common/RowActions';
import { Tooltip } from '@/components/common/Tooltip';
import { humanizeError } from '@/lib/errors';
import { useShortcut } from '@/lib/shortcuts';
import { docStatut, fmtDevise, formatWaMeUrl, humanize, isoToFr } from '@/lib/format';
import {
  useCopyDocumentToClipboard,
  useDeleteDocument,
  useOpenDocument,
  usePatientDocuments,
  usePrintDocument,
  useRefreshStatus,
  useRefreshWhatsAppStatus,
  useRenderDocument,
  useSendDocument,
  useSendWhatsApp,
} from '@/hooks/documents';
import { useWhatsAppSettings, useCategories } from '@/hooks/queries';
import type { DocumentT, Patient } from '@/api/types';
import { GenerateDialog } from './GenerateDialog';
import { SendWhatsAppDialog } from '@/components/dialogs/SendWhatsAppDialog';

type GenState =
  { mode: 'note' | 'generic'; draft?: null } | { mode: 'generic'; draft: DocumentT } | null;

export function DocumentsTab({
  patient,
  denture,
}: {
  patient: Patient;
  denture: 'adulte' | 'enfant';
}) {
  const [page, setPage] = useState(0);
  const list = usePatientDocuments(patient.id, page);
  const render = useRenderDocument();
  const print = usePrintDocument();
  const send = useSendDocument();
  const open = useOpenDocument();
  const copyToClipboard = useCopyDocumentToClipboard();
  const refresh = useRefreshStatus();
  const sendWhatsApp = useSendWhatsApp();
  const refreshWhatsApp = useRefreshWhatsAppStatus();
  const del = useDeleteDocument();
  const waSettings = useWhatsAppSettings();
  const categories = useCategories();
  const [gen, setGen] = useState<GenState>(null);
  const [waSelectDoc, setWaSelectDoc] = useState<DocumentT | null>(null);

  function handleSendWhatsAppClick(d: DocumentT) {
    const phones = patient.telephones || [];
    if (phones.length > 1) {
      setWaSelectDoc(d);
    } else {
      const targetPhone = phones[0]?.telephone || patient.telephone;
      if (targetPhone) {
        withToast(sendWhatsApp.mutateAsync({ id: d.id, telephone: targetPhone }), 'Document envoyé par WhatsApp.');
      } else {
        toast.error("Le patient n'a pas de numéro de téléphone.");
      }
    }
  }

  useShortcut([
    {
      keys: 'alt+n',
      description: "Note d'honoraires",
      group: 'Documents',
      handler: () => setGen({ mode: 'note' }),
    },
    {
      keys: 'alt+d',
      description: 'Générer un document',
      group: 'Documents',
      handler: () => setGen({ mode: 'generic' }),
    },
  ]);

  function withToast(p: Promise<unknown>, msg: string) {
    p.then(() => toast.success(msg)).catch((e) => toast.error(humanizeError(e)));
  }

  function actions(d: DocumentT) {
    const isDraft = d.statut === 'brouillon';
    const isError = d.statut === 'erreur';
    const canSend = !!d.email && (d.statut === 'en_attente_envoi' || d.statut === 'erreur_envoi');
    const hasPhone = !!patient.telephone || (patient.telephones && patient.telephones.length > 0);
    const canSendWhatsApp = hasPhone && d.has_file && d.statut !== 'brouillon';
    const canRefreshWhatsApp = !!d.whatsapp_message_id;
    return (
      <RowActions
        actions={[
          (isDraft || isError) && {
            key: 'render',
            label: 'Générer',
            icon: PlayCircle,
            onClick: () => withToast(render.mutateAsync({ id: d.id }), 'Document généré.'),
          },
          isDraft && {
            key: 'edit',
            label: 'Modifier le brouillon',
            icon: Pencil,
            onClick: () => setGen({ mode: 'generic', draft: d }),
          },
          d.has_file && {
            key: 'open',
            label: 'Ouvrir le fichier',
            icon: FolderOpen,
            onClick: () => withToast(open.mutateAsync(d.id), 'Fichier ouvert.'),
          },
          d.has_file && {
            key: 'print',
            label: 'Imprimer',
            icon: Printer,
            onClick: () => withToast(print.mutateAsync({ id: d.id }), "Envoyé à l'imprimante."),
          },
          canSend && {
            key: 'send',
            label: 'Envoyer par email',
            icon: Send,
            onClick: () => withToast(send.mutateAsync({ id: d.id, body: {} }), 'Email envoyé.'),
          },
          (canSendWhatsApp && waSettings.data?.whatsapp_api_enabled) && {
            key: 'send-whatsapp',
            label: 'Envoyer par WhatsApp (Meta)',
            icon: MessageSquare,
            onClick: () => handleSendWhatsAppClick(d),
          },
          canSendWhatsApp && {
            key: 'open-wa-me',
            label: 'Ouvrir dans WhatsApp (wa.me)',
            icon: ExternalLink,
            onClick: async () => {
              try {
                await copyToClipboard.mutateAsync(d.id);
                toast.success('Document copié dans le presse-papiers.');
              } catch (e) {
                toast.error(humanizeError(e));
              }

              const defaultCountry = waSettings.data?.default_country || '+216';
              const docCatName = d.categorie || '';
              const categoryObj = categories.data?.find(c => c.nom === docCatName);
              const rawTemplate = categoryObj?.whatsapp_message || waSettings.data?.fallback_message || "Bonjour <PRENOM> <NOM>, voici votre <DOCUMENT>.";
              
              const docLabel = humanize(d.type).toLowerCase();
              const text = rawTemplate
                .replace(/<PRENOM>/g, patient.prenom || '')
                .replace(/<NOM>/g, patient.nom || '')
                .replace(/<DOCUMENT>/g, docLabel);

              const targetPhone = (patient.telephones && patient.telephones.length > 0)
                ? (patient.telephones.find(t => t.is_whatsapp)?.telephone || patient.telephones[0].telephone)
                : patient.telephone;
              const url = formatWaMeUrl(targetPhone || '', defaultCountry, text);
              window.open(url, '_blank');
            },
          },
          d.statut === 'envoye' && {
            key: 'refresh',
            label: 'Rafraîchir le statut',
            icon: RefreshCw,
            onClick: () => withToast(refresh.mutateAsync({ id: d.id }), 'Statut mis à jour.'),
          },
          canRefreshWhatsApp && {
            key: 'refresh-whatsapp',
            label: 'Rafraîchir statut WhatsApp',
            icon: RefreshCw,
            onClick: () => withToast(refreshWhatsApp.mutateAsync({ id: d.id }), 'Statut WhatsApp mis à jour.'),
          },
          (isDraft || isError) && {
            key: 'delete',
            label: 'Supprimer',
            icon: Trash2,
            tone: 'danger',
            separatorBefore: true,
            onClick: () => {
              if (confirm('Supprimer ce document ?'))
                withToast(del.mutateAsync(d.id), 'Document supprimé.');
            },
          },
        ]}
      />
    );
  }

  // Regroupement par catégorie (null → « Sans catégorie »).
  const groups = new Map<string, DocumentT[]>();
  for (const d of list.data?.items ?? []) {
    const key = d.categorie || 'Sans catégorie';
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(d);
  }

  return (
    <div className="space-y-4 pt-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="flex-1 text-lg font-semibold text-ink">Documents</h2>
        <Tooltip label="Note d'honoraires" shortcut="alt+n">
          <Button variant="secondary" onClick={() => setGen({ mode: 'note' })}>
            <FileText className="size-4" /> Note d&apos;honoraires
          </Button>
        </Tooltip>
        <Tooltip label="Générer un document" shortcut="alt+d">
          <Button onClick={() => setGen({ mode: 'generic' })}>
            <FileText className="size-4" /> Générer un document
          </Button>
        </Tooltip>
      </div>

      {list.isLoading && <p className="text-sm text-muted">Chargement…</p>}
      {list.isError && <p className="text-sm text-red">{humanizeError(list.error)}</p>}

      {[...groups.entries()].map(([cat, docs]) => (
        <section key={cat} className="rounded-[var(--radius)] border border-line bg-white p-4">
          <h3 className="mb-2 text-sm font-semibold text-navy">
            {cat} <span className="text-muted">({docs.length})</span>
          </h3>
          {docs.map((d) => {
            const st = docStatut(d.statut);
            return (
              <div
                key={d.id}
                className="flex items-start gap-3 border-t border-line py-2 first:border-t-0"
              >
                {d.output_format === 'pdf' ? (
                  <FileText className="mt-0.5 size-5 shrink-0 text-muted" />
                ) : (
                  <FileImage className="mt-0.5 size-5 shrink-0 text-muted" />
                )}
                <div className="min-w-0 flex-1">
                  <div className="font-medium text-ink">
                    {humanize(d.type)}
                    {d.montant != null ? ` — ${fmtDevise(d.montant)}` : ''}
                  </div>
                  <div className="text-xs text-muted">
                    {(() => {
                      const mailInfo = (d.mailjet_status || d.mailjet_opened_at || d.mailjet_clicked_at)
                        ? `Email : ${d.mailjet_status || 'envoyé'}${d.mailjet_opened_at ? ' · ouvert' : ''}${d.mailjet_clicked_at ? ' · cliqué' : ''}`
                        : '';
                      const waStatusText = d.whatsapp_status === 'read'
                        ? 'lu'
                        : d.whatsapp_status === 'delivered'
                        ? 'remis'
                        : d.whatsapp_status === 'sent'
                        ? 'envoyé'
                        : d.whatsapp_status || 'envoyé';
                      const waInfo = d.whatsapp_message_id
                        ? `WhatsApp : ${waStatusText}`
                        : '';
                      const deliveryInfo = [mailInfo, waInfo].filter(Boolean).join(' | ');
                      if (deliveryInfo) return `Livraison : ${deliveryInfo}`;
                      return isoToFr(d.date_generation) || 'Brouillon';
                    })()}
                    {d.message_erreur ? ` · ${d.message_erreur}` : ''}
                  </div>
                </div>
                <Badge variant={st.variant}>{st.label}</Badge>
                {actions(d)}
              </div>
            );
          })}
        </section>
      ))}
      {list.data && list.data.items.length === 0 && (
        <div className="rounded-[var(--radius)] border border-line bg-white py-10 text-center text-muted">
          Aucun document.
        </div>
      )}

      <Pagination total={list.data?.total ?? 0} page={page} onPage={setPage} />

      <GenerateDialog
        patientId={patient.id}
        open={!!gen}
        mode={gen?.mode ?? 'generic'}
        draft={gen && 'draft' in gen ? gen.draft : null}
        defaultDenture={denture}
        onClose={() => setGen(null)}
      />

      <SendWhatsAppDialog
        patient={patient}
        isOpen={!!waSelectDoc}
        onClose={() => setWaSelectDoc(null)}
        onConfirm={(phone) => {
          if (waSelectDoc) {
            withToast(
              sendWhatsApp.mutateAsync({ id: waSelectDoc.id, telephone: phone }),
              'Document envoyé par WhatsApp.'
            );
          }
          setWaSelectDoc(null);
        }}
      />
    </div>
  );
}
