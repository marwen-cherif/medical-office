import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

// Tauri sert l'UI buildée (dist/) ; en dev, Vite tourne sur 1420 et le frontend
// parle au sidecar FastAPI découvert au lancement (cf. src/lib/bridge.ts).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  // Tauri attend un port fixe ; loopback only.
  server: { host: "127.0.0.1", port: 1420, strictPort: true },
  // Chemins relatifs : indispensable quand Tauri charge l'app depuis le système
  // de fichiers (protocole tauri://) plutôt qu'un serveur HTTP.
  base: "./",
  build: { outDir: "dist", emptyOutDir: true, target: "es2022" },
});
