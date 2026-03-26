import { NavLink } from "react-router-dom";
import clsx from "clsx";

const links = [
  { to: "/",        label: "Today",   emoji: "📰" },
  { to: "/archive", label: "Archive", emoji: "🗂️" },
  { to: "/weekly",  label: "Weekly",  emoji: "📅" },
  { to: "/monthly", label: "Monthly", emoji: "📊" },
];

export default function Navbar() {
  return (
    <nav className="sticky top-0 z-50 border-b border-slate-800 bg-slate-950/80 backdrop-blur-md">
      <div className="max-w-6xl mx-auto px-4 flex items-center gap-6 h-14">
        {/* Logo */}
        <NavLink to="/" className="flex items-center gap-2 shrink-0 mr-4">
          <span className="text-2xl">🤖</span>
          <span className="font-bold text-sm text-slate-100 hidden sm:block">
            AI Research Pipeline
          </span>
        </NavLink>

        {/* Nav links */}
        <div className="flex items-center gap-1">
          {links.map(({ to, label, emoji }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                clsx(
                  "px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                  isActive
                    ? "bg-brand-600/20 text-brand-400 border border-brand-700/40"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
                )
              }
            >
              <span className="mr-1.5">{emoji}</span>
              {label}
            </NavLink>
          ))}
        </div>

        {/* Right side */}
        <div className="ml-auto flex items-center gap-2">
          <a
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-500 hover:text-slate-300 transition-colors text-xs"
            aria-label="View source on GitHub"
          >
            GitHub ↗
          </a>
        </div>
      </div>
    </nav>
  );
}
