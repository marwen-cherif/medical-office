import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { HelpCircle, Loader2, MessageSquare, Save } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { humanizeError } from '@/lib/errors';
import { useWhatsAppSettings, useSetWhatsAppSettings } from '@/hooks/queries';

export function WhatsAppTab() {
  const settings = useWhatsAppSettings();
  const saveSettings = useSetWhatsAppSettings();

  const [phoneId, setPhoneId] = useState('');
  const [token, setToken] = useState('');
  const [templateName, setTemplateName] = useState('envoi_document');
  const [defaultCountry, setDefaultCountry] = useState('+216');

  useEffect(() => {
    if (!settings.data) return;
    setPhoneId(settings.data.whatsapp_phone_number_id || '');
    setToken(settings.data.has_token ? '••••••••' : '');
    setTemplateName(settings.data.whatsapp_template_name || 'envoi_document');
    setDefaultCountry(settings.data.default_country || '+216');
  }, [settings.data]);

  function onSave() {
    if (!phoneId.trim()) {
      toast.error('Le Phone Number ID est requis.');
      return;
    }
    if (!token.trim()) {
      toast.error("Le Token d'accès est requis.");
      return;
    }

    saveSettings.mutate(
      {
        whatsapp_phone_number_id: phoneId.trim(),
        whatsapp_access_token: token,
        whatsapp_template_name: templateName.trim() || 'envoi_document',
        default_country: defaultCountry.trim() || '+216',
      },
      {
        onSuccess: () => toast.success('Réglages WhatsApp enregistrés.'),
        onError: (e) => toast.error(humanizeError(e)),
      }
    );
  }

  const isLoading = settings.isLoading;

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="size-4" /> API Meta WhatsApp Cloud
          </CardTitle>
          <CardDescription>
            Connectez votre compte Meta Business pour envoyer les documents par WhatsApp.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading && <p className="text-sm text-muted">Chargement…</p>}
          {settings.isError && <p className="text-sm text-red">{humanizeError(settings.error)}</p>}

          <div className="space-y-2">
            <Label htmlFor="wa-phone-id">Phone Number ID</Label>
            <Input
              id="wa-phone-id"
              value={phoneId}
              onChange={(e) => setPhoneId(e.target.value)}
              placeholder="ex. 104829302948294"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="wa-token">Token d'accès permanent</Label>
            <Input
              id="wa-token"
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Saisir le token d'accès permanent..."
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="wa-template">Nom du modèle Meta</Label>
              <Input
                id="wa-template"
                value={templateName}
                onChange={(e) => setTemplateName(e.target.value)}
                placeholder="envoi_document"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="wa-country">Indicatif pays</Label>
              <Input
                id="wa-country"
                value={defaultCountry}
                onChange={(e) => setDefaultCountry(e.target.value)}
                placeholder="+216"
              />
            </div>
          </div>

          <Button onClick={onSave} disabled={saveSettings.isPending || isLoading}>
            {saveSettings.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Save className="size-4" />
            )}
            Enregistrer
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HelpCircle className="size-4" /> Format du modèle
          </CardTitle>
          <CardDescription>
            Créez un modèle unique dans Meta Business Manager avec ce format.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-lg border bg-muted/30 p-4 space-y-3">
            <div className="text-sm font-semibold">En-tête (Header)</div>
            <div className="rounded bg-background border p-3 text-sm">
              Type : <span className="font-mono font-semibold">DOCUMENT</span>
              <span className="text-muted ml-2">(le PDF est envoyé automatiquement)</span>
            </div>

            <div className="text-sm font-semibold mt-3">Corps du message (Body)</div>
            <div className="rounded bg-background border p-3 text-sm font-mono leading-relaxed">
              Bonjour <span className="bg-sky-100 text-sky-700 px-1 rounded">{'{{1}}'}</span>{' '}
              <span className="bg-sky-100 text-sky-700 px-1 rounded">{'{{2}}'}</span>,
              <br />
              veuillez trouver ci-joint votre{' '}
              <span className="bg-emerald-100 text-emerald-700 px-1 rounded">{'{{3}}'}</span>.
              <br />
              Cabinet Dr. Votre Nom
            </div>

            <div className="space-y-1.5 text-sm text-muted mt-2">
              <div>
                <span className="bg-sky-100 text-sky-700 px-1 rounded font-mono text-xs">
                  {'{{1}}'}
                </span>{' '}
                = Prénom du patient
              </div>
              <div>
                <span className="bg-sky-100 text-sky-700 px-1 rounded font-mono text-xs">
                  {'{{2}}'}
                </span>{' '}
                = Nom du patient
              </div>
              <div>
                <span className="bg-emerald-100 text-emerald-700 px-1 rounded font-mono text-xs">
                  {'{{3}}'}
                </span>{' '}
                = Type de document (note d'honoraires, devis…)
              </div>
            </div>
          </div>

          <p className="text-xs text-muted">
            Catégorie : Utility · Langue : Français (fr) · Un seul modèle suffit pour tous les types
            de documents.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
