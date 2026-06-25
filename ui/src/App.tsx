import { Navigate, Route, Routes } from "react-router-dom";
import { Shell } from "@/components/Shell";
import { ShortcutsProvider } from "@/lib/shortcuts";
import { ShortcutsHelpDialog } from "@/components/common/ShortcutsHelpDialog";
import { Parametrage } from "@/screens/Parametrage";
import { TableauDeBord } from "@/screens/TableauDeBord";
import { Patients } from "@/screens/Patients";
import { PatientDetail } from "@/screens/PatientDetail";
import { Finances } from "@/screens/Finances";
import { Prestataires } from "@/screens/Prestataires";
import { PrestataireDetail } from "@/screens/PrestataireDetail";
import { Travaux } from "@/screens/Travaux";
import { JobDetail } from "@/screens/JobDetail";

export default function App() {
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
        <Route path="*" element={<Navigate to="/tableau-de-bord" replace />} />
        </Routes>
      </Shell>
      <ShortcutsHelpDialog />
    </ShortcutsProvider>
  );
}
