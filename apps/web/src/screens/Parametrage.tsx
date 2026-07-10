import { FileText, Mail, MessageSquare, Printer, Stethoscope } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ModelesTab } from './parametrage/ModelesTab';
import { EmailsTab } from './parametrage/EmailsTab';
import { ImprimanteTab } from './parametrage/ImprimanteTab';
import { ActesTab } from './parametrage/ActesTab';
import { WhatsAppTab } from './parametrage/WhatsAppTab';

export function Parametrage() {
  return (
    <div className="mx-auto max-w-5xl p-8">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold text-ink">Paramétrage</h1>
        <p className="mt-1 text-sm text-muted">
          Modèles de documents, modèles d'email, imprimante, WhatsApp et catalogue d'actes.
        </p>
      </header>

      <Tabs defaultValue="modeles">
        <TabsList>
          <TabsTrigger value="modeles">
            <FileText className="size-4" /> Modèles
          </TabsTrigger>
          <TabsTrigger value="emails">
            <Mail className="size-4" /> Modèles d'email
          </TabsTrigger>
          <TabsTrigger value="imprimante">
            <Printer className="size-4" /> Imprimante
          </TabsTrigger>
          <TabsTrigger value="whatsapp">
            <MessageSquare className="size-4" /> WhatsApp
          </TabsTrigger>
          <TabsTrigger value="actes">
            <Stethoscope className="size-4" /> Actes
          </TabsTrigger>
        </TabsList>

        <TabsContent value="modeles">
          <ModelesTab />
        </TabsContent>
        <TabsContent value="emails">
          <EmailsTab />
        </TabsContent>
        <TabsContent value="imprimante">
          <ImprimanteTab />
        </TabsContent>
        <TabsContent value="whatsapp">
          <WhatsAppTab />
        </TabsContent>
        <TabsContent value="actes">
          <ActesTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
