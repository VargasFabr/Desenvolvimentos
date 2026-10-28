import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import Button from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import PageHeader from "../components/ui/PageHeader";

export default function Dashboard() {
  const [q, setQ] = useState("");
  const { data: stats, isLoading: statsLoading } = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });
  const {
    data: busca,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["busca", q],
    queryFn: () => api.busca(q),
    enabled: false,
  });

  const cards = [
    ["Empreendimentos", stats?.empreendimentos ?? "—"],
    ["Torres", stats?.torres ?? "—"],
    ["Fases", stats?.fases ?? "—"],
    ["Unidades", stats?.unidades ?? "—"],
  ] as const;

  const linkFor = (tipo: string, codigo: string, spe?: string) => {
    if (tipo === "torre" && codigo) return `/unidades?codigo_interno=${encodeURIComponent(codigo)}`;
    if (tipo === "empreendimento" && spe) return `/torres?spe=${encodeURIComponent(spe)}`;
    if (codigo) return `/torres?q=${encodeURIComponent(codigo)}`;
    return "#";
  };

  return (
    <div>
      <PageHeader title="Dashboard" />
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map(([label, val]) => (
          <div key={label} className="card p-4">
            <div className="text-sm text-muted-foreground">{label}</div>
            <div className="mt-1 text-3xl font-bold">{statsLoading ? "…" : val}</div>
          </div>
        ))}
      </div>

      <section className="card p-4">
        <h3 className="mb-2 font-medium">Busca rápida</h3>
        <div className="mb-4 flex flex-col gap-2 sm:flex-row">
          <Input
            className="flex-1"
            placeholder="Alias, nome, SPE ou código interno..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && q.length >= 2 && refetch()}
          />
          <Button disabled={q.length < 2 || isFetching} onClick={() => refetch()}>
            {isFetching ? "Buscando…" : "Buscar"}
          </Button>
        </div>
        {busca && (
          <div className="table-scroll">
            {busca.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">Nenhum resultado para &quot;{q}&quot;</p>
            ) : (
              <table className="min-w-max w-full text-sm">
                <thead className="sticky-header">
                  <tr className="border-b border-border text-left">
                    <th scope="col" className="py-2 pr-4">
                      Tipo
                    </th>
                    <th scope="col" className="py-2 pr-4">
                      Nome
                    </th>
                    <th scope="col" className="py-2 pr-4">
                      Alias
                    </th>
                    <th scope="col" className="py-2">
                      Código
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {busca.map((r, i) => {
                    const codigo = String(r.codigo_interno || r.cod_spe || "");
                    const href = linkFor(String(r.tipo), codigo, r.cod_spe ? String(r.cod_spe) : undefined);
                    return (
                      <tr key={i} className="border-b border-slate-100 hover:bg-slate-50/80">
                        <td className="py-2 pr-4 capitalize">{r.tipo}</td>
                        <td className="py-2 pr-4">
                          <Link to={href} className="text-slate-900 underline-offset-2 hover:underline focus-ring">
                            {r.nome}
                          </Link>
                        </td>
                        <td className="py-2 pr-4">{r.alias}</td>
                        <td className="py-2 font-mono text-xs">{codigo}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
