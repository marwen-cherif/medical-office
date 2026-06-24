import { Navigate, Route, Routes } from "react-router-dom";
import { Shell } from "@/components/Shell";
import { Parametrage } from "@/screens/Parametrage";

function Placeholder({ title }: { title: string }) {
  return (
    <div className="p-8">
      <h1 className="text-xl font-semibold text-ink">{title}</h1>
      <p className="mt-2 text-sm text-muted">
        Écran porté dans un incrément ultérieur de la migration React.
      </p>
    </div>
  );
}

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Navigate to="/parametrage" replace />} />
        <Route path="/parametrage" element={<Parametrage />} />
        <Route path="/tableau-de-bord" element={<Placeholder title="Tableau de bord" />} />
        <Route path="/patients" element={<Placeholder title="Patients" />} />
        <Route path="/finances" element={<Placeholder title="Finances" />} />
        <Route path="/travaux" element={<Placeholder title="Travaux" />} />
        <Route path="/prestataires" element={<Placeholder title="Prestataires" />} />
        <Route path="*" element={<Navigate to="/parametrage" replace />} />
      </Routes>
    </Shell>
  );
}
