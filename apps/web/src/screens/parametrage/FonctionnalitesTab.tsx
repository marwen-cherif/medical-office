import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Loader2, Save, ToggleLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { humanizeError } from '@/lib/errors';
import { useWhatsAppSettings, useSetWhatsAppSettings } from '@/hooks/queries';

export function FonctionnalitesTab() {
  const settings = useWhatsAppSettings();
  const saveSettings = useSetWhatsAppSettings();

  const [whatsappApiEnabled, setWhatsappApiEnabled] = useState(false);

  useEffect(() => {
    if (!settings.data) return;
    setWhatsappApiEnabled(settings.data.whatsapp_api_enabled || false);
  }, [settings.data]);

  function onSave() {
    saveSettings.mutate(
      {
        whatsapp_phone_number_id: settings.data?.whatsapp_phone_number_id || '',
        whatsapp_access_token: settings.data?.has_token ? '••••••••' : '',
        whatsapp_template_name: settings.data?.whatsapp_template_name || 'envoi_document',
        default_country: settings.data?.default_country || '+216',
        whatsapp_api_enabled: whatsappApiEnabled,
      },
      {
        onSuccess: () => toast.success('Fonctionnalités mises à jour.'),
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
            <ToggleLeft className="size-4" /> Activation des Fonctionnalités
          </CardTitle>
          <CardDescription>
            Activez ou désactivez les modules optionnels du cabinet.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {isLoading && <p className="text-sm text-muted">Chargement…</p>}
          {settings.isError && (
            <p className="text-sm text-red">{humanizeError(settings.error)}</p>
          )}

          <div className="flex items-start space-x-3 p-4 rounded-lg border bg-muted/20">
            <Checkbox
              id="feature-whatsapp-api"
              checked={whatsappApiEnabled}
              onCheckedChange={(c) => setWhatsappApiEnabled(!!c)}
            />
            <div className="grid gap-1.5 leading-none">
              <Label htmlFor="feature-whatsapp-api" className="font-semibold cursor-pointer">
                API Meta WhatsApp Cloud
              </Label>
              <p className="text-sm text-muted-foreground leading-relaxed mt-1">
                Permet d'envoyer des documents (notes d'honoraires, devis...) automatiquement aux patients par WhatsApp en utilisant l'API officielle de Meta.
              </p>
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
    </div>
  );
}
