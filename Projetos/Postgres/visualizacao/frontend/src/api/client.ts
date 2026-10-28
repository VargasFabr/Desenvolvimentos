const BASE = import.meta.env.VITE_API_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === "string" ? err.detail : JSON.stringify(err));
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

function qs(params?: Record<string, string | number | boolean | undefined>) {
  if (!params) return "";
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

export const api = {
  dashboard: () =>
    request<{ empreendimentos: number; torres: number; fases: number; unidades: number }>("/api/dashboard"),
  busca: (q: string) => request<Array<Record<string, string>>>("/api/busca?q=" + encodeURIComponent(q)),

  empreendimentos: (params?: Record<string, string | number>) =>
    request<Array<Record<string, unknown>>>("/api/empreendimentos" + qs(params)),
  empreendimentosOpcoes: () => request<Record<string, string[]>>("/api/empreendimentos/filtros/opcoes"),
  createEmpreendimento: (body: Record<string, unknown>) =>
    request("/api/empreendimentos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  updateEmpreendimento: (id: string, body: Record<string, unknown>) =>
    request(`/api/empreendimentos/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  torres: (params?: Record<string, string | number | boolean>) =>
    request<Array<Record<string, unknown>>>("/api/torres" + qs(params)),
  torresOpcoes: () => request<Record<string, string[]>>("/api/torres/filtros/opcoes"),
  createTorre: (body: Record<string, unknown>) =>
    request("/api/torres", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  updateTorre: (id: string, body: Record<string, unknown>) =>
    request(`/api/torres/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  unidades: (params?: Record<string, string | number>) =>
    request<Array<Record<string, unknown>>>("/api/unidades" + qs(params)),
  unidadesOpcoes: () => request<Record<string, string[]>>("/api/unidades/filtros/opcoes"),
  createUnidade: (body: Record<string, unknown>) =>
    request("/api/unidades", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  updateUnidade: (id: string, body: Record<string, unknown>) =>
    request(`/api/unidades/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  ottoUnidadesPreview: (spe?: string) =>
    request<{ total_otto: number; mapeadas: number; sem_torre_cad: number; parse_erro: number }>(
      "/api/unidades/sync/otto/preview" + (spe ? "?spe=" + encodeURIComponent(spe) : "")
    ),
  ottoUnidadesSync: (spe?: string) =>
    request<{ total_otto: number; importados: number; sem_torre_cad: number; parse_erro: number }>(
      "/api/unidades/sync/otto" + (spe ? "?spe=" + encodeURIComponent(spe) : ""),
      { method: "POST" }
    ),

  importPreview: async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`${BASE}/api/import/preview`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
  importUnidadesPreview: async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`${BASE}/api/import/unidades/preview`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
  importConfirm: (rows: Record<string, unknown>[]) =>
    request("/api/import/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rows }),
    }),
  importUnidadesConfirm: (rows: Record<string, unknown>[]) =>
    request("/api/import/unidades/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rows }),
    }),
  templateUrl: () => `${BASE}/api/import/template.xlsx`,
  unidadesTemplateUrl: () => `${BASE}/api/import/unidades/template.xlsx`,
  exportUrl: () => `${BASE}/api/export/torres.xlsx`,
};

export type ImportPreview = {
  total: number;
  validos: number;
  erros: Array<{ linha: number; campo?: string; mensagem: string }>;
  avisos: Array<{ linha: number; mensagem: string }>;
  rows: Array<Record<string, unknown>>;
  payload?: Array<Record<string, unknown>>;
};
