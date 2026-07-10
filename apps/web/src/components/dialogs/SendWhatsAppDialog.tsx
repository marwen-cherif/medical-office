import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import type { Patient } from '@/api/types';
import { WhatsAppIcon } from '@/components/icons/WhatsAppIcon';

export function SendWhatsAppDialog({
  patient,
  isOpen,
  onClose,
  onConfirm,
}: {
  patient: Patient | null;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (phone: string) => void;
}) {
  const [selectedPhone, setSelectedPhone] = useState('');

  const phones = patient?.telephones || [];
  const hasWaCompatible = phones.some((t) => t.is_whatsapp);

  useEffect(() => {
    if (isOpen && phones.length > 0) {
      const waCompat = phones.find((t) => t.is_whatsapp);
      if (waCompat) {
        setSelectedPhone(waCompat.telephone);
      } else {
        setSelectedPhone(phones[0].telephone);
      }
    }
  }, [isOpen, patient]);

  if (!patient) return null;

  return (
    <Dialog open={isOpen} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle>Sélectionner le numéro destinataire</DialogTitle>
        </DialogHeader>

        <div className="space-y-3 py-2">
          <p className="text-sm text-muted">
            Le patient <strong>{patient.display}</strong> possède plusieurs numéros de téléphone. Choisissez la ligne cible pour l'envoi WhatsApp :
          </p>

          {!hasWaCompatible && phones.length > 0 && (
            <div className="rounded-[var(--radius)] border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
              ⚠️ Aucun numéro n'est déclaré compatible avec WhatsApp pour ce patient. Vous pouvez toutefois tenter l'envoi sur l'un d'eux.
            </div>
          )}

          <div className="space-y-2 max-h-[200px] overflow-y-auto border border-line rounded-[var(--radius)] p-2 bg-bg/20">
            {phones.map((t, idx) => (
              <label
                key={idx}
                className={`flex items-center justify-between gap-3 p-2.5 rounded-[var(--radius)] border cursor-pointer transition-colors ${
                  selectedPhone === t.telephone
                    ? 'border-navy bg-navy/5 text-ink'
                    : 'border-line bg-white text-ink hover:bg-bg/50'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <input
                    type="radio"
                    name="wa-target-phone"
                    value={t.telephone}
                    checked={selectedPhone === t.telephone}
                    onChange={() => setSelectedPhone(t.telephone)}
                    className="size-4 text-navy border-line"
                  />
                  <span className="bg-bg text-ink px-1.5 py-0.5 rounded text-[10px] font-medium border border-line">
                    {t.relation}
                  </span>
                  <span className="font-mono text-xs">{t.telephone}</span>
                </div>
                {t.is_whatsapp && (
                  <span className="inline-flex items-center gap-1 text-[9px] bg-emerald-50 text-emerald-600 px-1.5 py-0.5 rounded font-bold border border-emerald-200 shrink-0">
                    <WhatsAppIcon className="size-3 text-emerald-600" />
                    <span>WhatsApp</span>
                  </span>
                )}
              </label>
            ))}
          </div>
        </div>

        <DialogFooter>
          <Button variant="secondary" onClick={onClose}>
            Annuler
          </Button>
          <Button onClick={() => onConfirm(selectedPhone)} disabled={!selectedPhone}>
            Envoyer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
