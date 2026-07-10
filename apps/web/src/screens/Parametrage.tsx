import { FileText, Mail, MessageSquare, Printer, Stethoscope, ToggleLeft } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useFeatureSettings } from '@/hooks/queries';
import { ModelesTab } from './parametrage/ModelesTab';
import { EmailsTab } from './parametrage/EmailsTab';
import { ImprimanteTab } from './parametrage/ImprimanteTab';
import { ActesTab } from './parametrage/ActesTab';
import { WhatsAppTab } from './parametrage/WhatsAppTab';
import { FonctionnalitesTab } from './parametrage/FonctionnalitesTab';

export function Parametrage() {
  const features = useFeatureSettings();
  const isWhatsAppEnabled = !!features.data?.whatsapp_api_enabled;
  const isEmailingEnabled = features.data?.emailing_enabled ?? true;

  return (
    <div className="mx-auto max-w-5xl p-8">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold text-ink">Paramétrage</h1>
        <p className="mt-1 text-sm text-muted">
          {"Gérér les fonctionnalités optionnelles, modèles de documents, emails, imprimantes et catalogue d'actes."}
        </p>
      </header>

      <Tabs defaultValue="modeles">
        <TabsList>
          <TabsTrigger value="modeles">
            <FileText className="size-4" /> Modèles
          </TabsTrigger>
          {isEmailingEnabled && (
            <TabsTrigger value="emails">
              <Mail className="size-4" /> {"Modèles d'email"}
            </TabsTrigger>
          )}
          <TabsTrigger value="imprimante">
            <Printer className="size-4" /> Imprimante
          </TabsTrigger>
          {isWhatsAppEnabled && (
            <TabsTrigger value="whatsapp">
              <MessageSquare className="size-4" /> WhatsApp
            </TabsTrigger>
          )}
          <TabsTrigger value="actes">
            <Stethoscope className="size-4" /> Actes
          </TabsTrigger>
          <TabsTrigger value="features">
            <ToggleLeft className="size-4" /> Fonctionnalités
          </TabsTrigger>
        </TabsList>

        <TabsContent value="modeles">
          <ModelesTab />
        </TabsContent>
        {isEmailingEnabled && (
          <TabsContent value="emails">
            <EmailsTab />
          </TabsContent>
        )}
        <TabsContent value="imprimante">
          <ImprimanteTab />
        </TabsContent>
        {isWhatsAppEnabled && (
          <TabsContent value="whatsapp">
            <WhatsAppTab />
          </TabsContent>
        )}
        <TabsContent value="actes">
          <ActesTab />
        </TabsContent>
        <TabsContent value="features">
          <FonctionnalitesTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
