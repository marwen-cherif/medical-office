import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { DatePicker } from '@/components/common/DatePicker';

import { COUNTRIES, parsePhoneNumber, formatE164 } from '@/lib/format';
import { PhoneInput } from 'react-international-phone';
import 'react-international-phone/style.css';
import { WhatsAppIcon } from '@/components/icons/WhatsAppIcon';
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { humanizeError } from '@/lib/errors';
import { useCreatePatient, useUpdatePatient } from '@/hooks/patients';
import type { Patient } from '@/api/types';

export function PatientFormDialog({
  target,
  onClose,
  onCreated,
}: {
  target: Patient | 'new' | null;
  onClose: () => void;
  onCreated?: (p: Patient) => void;
}) {
  const create = useCreatePatient();
  const update = useUpdatePatient();
  const isEdit = target && target !== 'new';

  const [form, setForm] = useState({
    nom: '',
    prenom: '',
    date_naissance: '',
    email: '',
    telephone: '',
    adresse: '',
    notes: '',
  });
  const [telephones, setTelephones] = useState<{ id?: number | null; prefix: string; local: string; relation: string; is_whatsapp: boolean }[]>([]);
  const [error, setError] = useState('');
  const [confirmDup, setConfirmDup] = useState(false);

  useEffect(() => {
    if (target === 'new') {
      setForm({
        nom: '',
        prenom: '',
        date_naissance: '',
        email: '',
        telephone: '',
        adresse: '',
        notes: '',
      });
      setTelephones([
        { prefix: '+216', local: '', relation: 'Lui-même', is_whatsapp: true }
      ]);
    } else if (target) {
      setForm({
        nom: target.nom,
        prenom: target.prenom,
        date_naissance: target.date_naissance ?? '',
        email: target.email ?? '',
        telephone: target.telephone ?? '',
        adresse: target.adresse ?? '',
        notes: target.notes ?? '',
      });

      if (target.telephones && target.telephones.length > 0) {
        const list = target.telephones.map((t) => {
          const { prefix, local } = parsePhoneNumber(t.telephone);
          return { id: t.id, prefix, local, relation: t.relation, is_whatsapp: t.is_whatsapp };
        });
        setTelephones(list);
      } else if (target.telephone) {
        const { prefix, local } = parsePhoneNumber(target.telephone);
        setTelephones([
          { prefix, local, relation: 'Lui-même', is_whatsapp: true }
        ]);
      } else {
        setTelephones([
          { prefix: '+216', local: '', relation: 'Lui-même', is_whatsapp: true }
        ]);
      }
    }
    setError('');
    setConfirmDup(false);
  }, [target]);

  const updatePhone = (index: number, fields: Partial<typeof telephones[0]>) => {
    setTelephones((prev) =>
      prev.map((t, i) => (i === index ? { ...t, ...fields } : t))
    );
  };


  const set = (k: keyof typeof form) => (v: string) => setForm((f) => ({ ...f, [k]: v }));

  function submit() {
    if (!form.nom.trim() || !form.prenom.trim())
      return setError('Le nom et le prénom sont obligatoires.');
      
    const phonesPayload = telephones
      .filter((t) => t.local.trim() !== '')
      .map((t) => ({
        id: t.id,
        telephone: formatE164(t.prefix, t.local),
        relation: t.relation.trim() || 'Lui-même',
        is_whatsapp: t.is_whatsapp,
      }));

    let primaryTel = null;
    const primary = phonesPayload.find(p => p.relation.toLowerCase() === 'lui-même') || phonesPayload[0];
    if (primary) {
      primaryTel = primary.telephone;
    }

    const body = {
      nom: form.nom.trim(),
      prenom: form.prenom.trim(),
      date_naissance: form.date_naissance || null,
      email: form.email.trim() || null,
      telephone: primaryTel,
      adresse: form.adresse.trim() || null,
      notes: form.notes.trim() || null,
      force: confirmDup,
      telephones: phonesPayload,
    };
    const done = {
      onSuccess: (p: Patient) => {
        toast.success(isEdit ? 'Patient mis à jour.' : 'Patient créé.');
        onCreated?.(p);
        onClose();
      },
      onError: (e: unknown) => {
        const code = (e as { error?: { code?: string } })?.error?.code;
        if (code === 'DUPLICATE_PATIENT') {
          setConfirmDup(true);
          setError(humanizeError(e) + ' Cliquez à nouveau pour créer quand même.');
        } else {
          setError(humanizeError(e));
        }
      },
    };
    if (isEdit) update.mutate({ id: target.id, body }, done);
    else create.mutate(body, done);
  }

  return (
    <Sheet open={!!target} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="sm:max-w-[560px]">
        <form
          className="flex h-full flex-col"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <SheetHeader>
            <SheetTitle>{isEdit ? 'Modifier le patient' : 'Nouveau patient'}</SheetTitle>
          </SheetHeader>
          <SheetBody className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="pt-nom">Nom</Label>
                <Input
                  id="pt-nom"
                  autoFocus
                  value={form.nom}
                  onChange={(e) => set('nom')(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="pt-prenom">Prénom</Label>
                <Input
                  id="pt-prenom"
                  value={form.prenom}
                  onChange={(e) => set('prenom')(e.target.value)}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="pt-ddn">Date de naissance</Label>
                <DatePicker
                  id="pt-ddn"
                  dropdown
                  value={form.date_naissance}
                  onChange={set('date_naissance')}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="pt-email">Email</Label>
                <Input
                  id="pt-email"
                  value={form.email}
                  onChange={(e) => set('email')(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-3 border-t border-line pt-3">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-semibold">Numéros de téléphone</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    setTelephones([
                      ...telephones,
                      { prefix: '+216', local: '', relation: '', is_whatsapp: false },
                    ])
                  }
                >
                  + Ajouter
                </Button>
              </div>

              <div className="space-y-3">
                {telephones.map((t, index) => (
                  <div key={index} className="flex items-center gap-2">
                    <div className="w-[120px] shrink-0">
                      <Input
                        value={t.relation}
                        onChange={(e) => updatePhone(index, { relation: e.target.value })}
                        list="relations-list"
                        placeholder="Relation"
                        className="h-9 text-xs"
                      />
                    </div>
                    <div className="flex-1 min-w-0 phone-input-wrapper">
                      <PhoneInput
                        defaultCountry={(() => {
                          const code = COUNTRIES.find((c) => c.prefix === t.prefix)?.code.toLowerCase();
                          return code || 'tn';
                        })()}
                        value={formatE164(t.prefix, t.local)}
                        onChange={(phone) => {
                          const parsed = parsePhoneNumber(phone, t.prefix);
                          updatePhone(index, { prefix: parsed.prefix, local: parsed.local });
                        }}
                      />
                    </div>
                    <div
                      className="flex items-center gap-1.5 shrink-0 bg-bg px-2 py-1.5 rounded-[var(--radius)] h-9 border border-line"
                      title="Numéro lié à WhatsApp"
                    >
                      <Switch
                        checked={t.is_whatsapp}
                        onCheckedChange={(checked) => updatePhone(index, { is_whatsapp: checked })}
                      />
                      <WhatsAppIcon
                        className={`size-4 transition-colors ${
                          t.is_whatsapp ? 'text-emerald-600' : 'text-muted opacity-50'
                        }`}
                      />
                    </div>
                    {telephones.length > 1 && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="size-9 text-red hover:bg-red/10 shrink-0"
                        onClick={() => setTelephones(telephones.filter((_, i) => i !== index))}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="pt-adresse">Adresse</Label>
              <Textarea
                id="pt-adresse"
                rows={2}
                value={form.adresse}
                onChange={(e) => set('adresse')(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="pt-notes">Notes</Label>
              <Textarea
                id="pt-notes"
                rows={2}
                value={form.notes}
                onChange={(e) => set('notes')(e.target.value)}
              />
            </div>
            {error && <p className="text-xs text-red">{error}</p>}
          </SheetBody>
          <SheetFooter>
            <Button type="button" variant="secondary" onClick={onClose}>
              Annuler
            </Button>
            <Button type="submit" disabled={create.isPending || update.isPending}>
              Enregistrer
            </Button>
          </SheetFooter>
        </form>

        <datalist id="relations-list">
          <option value="Lui-même" />
          <option value="Le conjoint" />
          <option value="Père" />
          <option value="Mère" />
          <option value="L'enfant" />
          <option value="Autres" />
        </datalist>
      </SheetContent>
    </Sheet>
  );
}
