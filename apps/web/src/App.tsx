import { Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Shell } from '@/components/Shell';
import { ShortcutsProvider } from '@/lib/shortcuts';
import { ShortcutsHelpDialog } from '@/components/common/ShortcutsHelpDialog';
import { Parametrage } from '@/screens/Parametrage';
import { TableauDeBord } from '@/screens/TableauDeBord';
import { Patients } from '@/screens/Patients';
import { PatientDetail } from '@/screens/PatientDetail';
import { Finances } from '@/screens/Finances';
import { Prestataires } from '@/screens/Prestataires';
import { PrestataireDetail } from '@/screens/PrestataireDetail';
import { Travaux } from '@/screens/Travaux';
import { JobDetail } from '@/screens/JobDetail';
import { Rappels } from '@/screens/Rappels';
import { useRappelsStartup, ignoreRappelIds } from '@/hooks/rappels';

export default function App() {
  const navigate = useNavigate();
  // Filet de sécurité au démarrage : traite les rappels dus + toast résumé si besoin.
  // Le clic sur le toast ignore les rappels (marquer lu/traité) ; « Voir » ouvre la liste.
  useRappelsStartup((count, ids) => {
    const label = `📅 Vous avez ${count} rappel${count > 1 ? 's' : ''} en attente`;
    toast.info(label, {
      description: '« Voir » ouvre la liste, « Ignorer » les marque comme traités.',
      action: {
        label: 'Voir',
        onClick: () => navigate('/rappels'),
      },
      cancel: {
        label: 'Ignorer',
        onClick: async () => {
          const done = await ignoreRappelIds(ids);
          toast.success(`${done} rappel${done > 1 ? 's' : ''} ignoré${done > 1 ? 's' : ''}.`);
          // Le badge sera rafraîchi par le poll / focus listener de la cloche.
        },
      },
      duration: 8000,
    });
  });

  return (
    <ShortcutsProvider>
      <Shell>
        <Routes>
          <Route path="/" element={<Navigate to="/tableau-de-bord" replace />} />
          <Route path="/tableau-de-bord" element={<TableauDeBord />} />
          <Route path="/patients" element={<Patients />} />
          <Route path="/patients/:id" element={<PatientDetail />} />
          <Route path="/finances" element={<Finances />} />
          <Route path="/travaux" element={<Travaux />} />
          <Route path="/travaux/jobs/:id" element={<JobDetail />} />
          <Route path="/prestataires" element={<Prestataires />} />
          <Route path="/prestataires/:id" element={<PrestataireDetail />} />
          <Route path="/parametrage" element={<Parametrage />} />
          <Route path="/rappels" element={<Rappels />} />
          <Route path="*" element={<Navigate to="/tableau-de-bord" replace />} />
        </Routes>
      </Shell>
      <ShortcutsHelpDialog />
    </ShortcutsProvider>
  );
}
