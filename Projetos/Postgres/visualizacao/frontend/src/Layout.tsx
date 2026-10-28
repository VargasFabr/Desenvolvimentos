import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import Button from "./components/ui/Button";

const nav = [
  { to: "/", label: "Dashboard" },
  { to: "/empreendimentos", label: "Empreendimentos" },
  { to: "/torres", label: "Torres" },
  { to: "/unidades", label: "Unidades" },
  { to: "/importar", label: "Importar Excel" },
];

const apiDocsUrl = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL.replace(/\/$/, "")}/docs`
  : "http://localhost:8090/docs";

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <>
      {nav.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === "/"}
          onClick={onNavigate}
          className={({ isActive }) =>
            `block rounded-md px-3 py-2 text-sm focus-ring ${
              isActive ? "bg-slate-700 font-medium text-white" : "text-slate-300 hover:bg-slate-800 hover:text-white"
            }`
          }
        >
          {item.label}
        </NavLink>
      ))}
    </>
  );
}

export default function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-56 shrink-0 flex-col bg-slate-900 p-4 text-white lg:flex">
        <h1 className="mb-6 text-lg font-semibold">Cadastro Melnick</h1>
        <nav className="flex flex-col gap-1">
          <NavItems />
        </nav>
        <p className="mt-auto pt-8 text-xs text-slate-400">
          <a href={apiDocsUrl} className="underline focus-ring" target="_blank" rel="noreferrer">
            API docs
          </a>
        </p>
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="presentation">
          <button
            type="button"
            className="absolute inset-0 bg-black/40"
            aria-label="Fechar menu"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="relative flex h-full w-64 flex-col bg-slate-900 p-4 text-white shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h1 className="text-lg font-semibold">Menu</h1>
              <Button variant="ghost" size="sm" className="text-white" aria-label="Fechar" onClick={() => setMobileOpen(false)}>
                ✕
              </Button>
            </div>
            <nav className="flex flex-col gap-1">
              <NavItems onNavigate={() => setMobileOpen(false)} />
            </nav>
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-border bg-white px-4 py-3 lg:hidden">
          <Button variant="secondary" size="sm" aria-label="Abrir menu" onClick={() => setMobileOpen(true)}>
            ☰
          </Button>
          <span className="font-semibold text-slate-900">Cadastro Melnick</span>
        </header>
        <main className="min-w-0 flex-1 overflow-auto p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
