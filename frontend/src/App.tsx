import { Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import HomePage    from "./pages/HomePage";
import ArchivePage from "./pages/ArchivePage";
import WeeklyPage  from "./pages/WeeklyPage";
import MonthlyPage from "./pages/MonthlyPage";

export default function App() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Subtle grid background */}
      <div
        className="fixed inset-0 pointer-events-none opacity-[0.03]"
        style={{
          backgroundImage:
            "linear-gradient(#94a3b8 1px,transparent 1px),linear-gradient(to right,#94a3b8 1px,transparent 1px)",
          backgroundSize: "64px 64px",
        }}
      />

      {/* Top glow */}
      <div className="fixed top-0 left-1/2 -translate-x-1/2 w-[600px] h-[200px] bg-brand-600/10 blur-[120px] pointer-events-none" />

      <Navbar />

      <main className="relative max-w-6xl mx-auto px-4 py-8">
        <Routes>
          <Route path="/"        element={<HomePage />} />
          <Route path="/archive" element={<ArchivePage />} />
          <Route path="/weekly"  element={<WeeklyPage />} />
          <Route path="/monthly" element={<MonthlyPage />} />
        </Routes>
      </main>

      {/* Footer */}
      <footer className="relative border-t border-slate-800 mt-16 py-6">
        <div className="max-w-6xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-slate-600">
          <span>AI Research Pipeline — Zero cost · Fully automated</span>
          <span>Powered by Gemini 1.5 Flash · GitHub Actions · Vercel</span>
        </div>
      </footer>
    </div>
  );
}
