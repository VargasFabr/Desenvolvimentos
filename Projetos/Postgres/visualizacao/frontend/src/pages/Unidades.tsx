import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import DataTable from "../components/DataTable";
import EditDrawer from "../components/EditDrawer";
import Button from "../components/ui/Button";
import Dialog from "../components/ui/Dialog";
import { Input } from "../components/ui/Input";
import PageHeader from "../components/ui/PageHeader";
import { useColumnFilters } from "../hooks/useColumnFilters";
import { columnsFromRows } from "../utils/columns";

const EDIT_FIELDS = [
  { key: "codigo_unidade", label: "Cód. unidade", readOnly: true },
  { key: "codigo_interno", label: "Torre", readOnly: true },
  { key: "cod_spe", label: "SPE", readOnly: true },
  { key: "nome", label: "Unidade" },
  { key: "andar", label: "Andar" },
  { key: "area_privativa", label: "Área privativa", type: "number" as const },
  { key: "fracao_ideal", label: "Fração ideal", type: "number" as const },
  { key: "tipo", label: "Tipo" },
  { key: "dormitorios", label: "Dormitórios", type: "number" as const },
  { key: "vagas", label: "Vagas", type: "number" as const },
  { key: "id_gc", label: "ID GC" },
];

const CREATE_LABELS: Record<string, string> = {
  codigo_interno: "Código interno da torre",
  nome: "Unidade",
  andar: "Andar",
  area_privativa: "Área privativa",
  tipo: "Tipo",
  dormitorios: "Dormitórios",
  vagas: "Vagas",
  id_gc: "ID GC",
};

export default function Unidades() {
  const [searchParams, setSearchParams] = useSearchParams();
  const qc = useQueryClient();
  const codigoFromUrl = searchParams.get("codigo_interno") ?? "";

  const { data: opcoes } = useQuery({ queryKey: ["unidades-opcoes"], queryFn: api.unidadesOpcoes });
  const { filters, setFilters, params, clear } = useColumnFilters(
    opcoes,
    codigoFromUrl ? { codigo_interno: codigoFromUrl } : {},
    50000
  );

  // Menu Unidades (sem query) limpa filtro da torre; link Torre → Unidades aplica.
  useEffect(() => {
    setFilters((prev) => {
      if ((prev.codigo_interno ?? "") === codigoFromUrl) return prev;
      return { ...prev, codigo_interno: codigoFromUrl };
    });
  }, [codigoFromUrl, setFilters]);

  const setFilter = (k: string, v: string) => {
    const next = { ...filters, [k]: v };
    setFilters(next);
    if (k === "codigo_interno") {
      if (v) setSearchParams({ codigo_interno: v }, { replace: true });
      else setSearchParams({}, { replace: true });
    }
  };

  const clearFilters = () => {
    clear();
    setSearchParams({}, { replace: true });
  };

  const [open, setOpen] = useState(false);
  const [editRow, setEditRow] = useState<Record<string, unknown> | null>(null);
  const [form, setForm] = useState({
    codigo_interno: codigoFromUrl,
    nome: "",
    andar: "",
    area_privativa: "",
    tipo: "",
    dormitorios: "",
    vagas: "",
    id_gc: "",
  });

  const [ottoPreview, setOttoPreview] = useState<{
    total_otto: number;
    mapeadas: number;
    sem_torre_cad: number;
    parse_erro: number;
  } | null>(null);
  const [ottoMsg, setOttoMsg] = useState("");

  const ottoPreviewMut = useMutation({
    mutationFn: () => api.ottoUnidadesPreview(),
    onSuccess: setOttoPreview,
  });

  const ottoSyncMut = useMutation({
    mutationFn: () => api.ottoUnidadesSync(),
    onSuccess: (res) => {
      setOttoMsg(`Importados ${res.importados} de ${res.total_otto} unidades Otto.`);
      qc.invalidateQueries({ queryKey: ["unidades"] });
      qc.invalidateQueries({ queryKey: ["unidades-opcoes"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      setOttoPreview(null);
    },
  });

  const { data = [], isLoading } = useQuery({
    queryKey: ["unidades", params],
    queryFn: () => api.unidades(params),
  });

  const columns = useMemo(
    () => columnsFromRows(data, ["codigo_unidade", "codigo_interno", "nome", "andar", "area_privativa"], "unidades"),
    [data]
  );

  const create = useMutation({
    mutationFn: () =>
      api.createUnidade({
        codigo_interno: form.codigo_interno,
        nome: form.nome,
        andar: form.andar || undefined,
        area_privativa: form.area_privativa ? Number(form.area_privativa) : undefined,
        tipo: form.tipo || undefined,
        dormitorios: form.dormitorios ? Number(form.dormitorios) : undefined,
        vagas: form.vagas ? Number(form.vagas) : undefined,
        id_gc: form.id_gc || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["unidades"] });
      qc.invalidateQueries({ queryKey: ["unidades-opcoes"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      setOpen(false);
    },
  });

  const update = useMutation({
    mutationFn: () => {
      if (!editRow) throw new Error("Sem linha");
      const body: Record<string, unknown> = {};
      for (const f of EDIT_FIELDS) {
        if (f.readOnly) continue;
        const v = editRow[f.key];
        if (v !== undefined && v !== "") body[f.key] = v;
      }
      return api.updateUnidade(String(editRow.id_unidade), body);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["unidades"] });
      qc.invalidateQueries({ queryKey: ["unidades-opcoes"] });
      setEditRow(null);
    },
  });

  return (
    <div>
      <PageHeader
        title="Unidades"
        actions={
          <>
            <Button variant="secondary" size="sm" disabled={ottoPreviewMut.isPending} onClick={() => ottoPreviewMut.mutate()}>
              Preview Otto
            </Button>
            <Button
              variant="accent"
              size="sm"
              disabled={!ottoPreview || ottoSyncMut.isPending || ottoPreview.mapeadas === 0}
              onClick={() => ottoSyncMut.mutate()}
            >
              Sincronizar Otto
            </Button>
            <Button onClick={() => setOpen(true)}>Nova unidade</Button>
          </>
        }
      />

      <p className="mb-3 text-xs text-muted-foreground">
        Use a setinha no cabeçalho para filtrar (SPE, empreendimento, torre…). Preview/Sincronizar Otto
        importa todas as unidades mapeáveis do Otto (não usa o filtro da tabela).
      </p>

      {(ottoPreview || ottoMsg) && (
        <div className="card mb-4 p-4 text-sm">
          {ottoPreview && (
            <p>
              Otto: {ottoPreview.total_otto} unidades · {ottoPreview.mapeadas} mapeadas
              {ottoPreview.sem_torre_cad > 0 && ` · ${ottoPreview.sem_torre_cad} sem torre no cad`}
            </p>
          )}
          {ottoMsg && <p className="mt-1 font-medium text-emerald-800">{ottoMsg}</p>}
          {(ottoPreviewMut.isError || ottoSyncMut.isError) && (
            <p className="mt-1 text-red-600">{String(ottoPreviewMut.error || ottoSyncMut.error)}</p>
          )}
        </div>
      )}

      <DataTable
        storageKey="cols-unidades"
        columns={columns}
        rows={data}
        rowKey={(r) => String(r.id_unidade)}
        onEdit={setEditRow}
        loading={isLoading}
        stickyKey="codigo_unidade"
        filterOpcoes={opcoes}
        filters={filters}
        onFilterChange={setFilter}
        onClearFilters={clearFilters}
      />

      <EditDrawer
        title="Editar unidade"
        open={!!editRow}
        fields={EDIT_FIELDS}
        values={editRow ?? {}}
        onChange={(k, v) => setEditRow((r) => (r ? { ...r, [k]: v } : r))}
        onClose={() => setEditRow(null)}
        onSave={() => update.mutate()}
        saving={update.isPending}
        error={update.isError ? String(update.error) : null}
      />

      <Dialog
        open={open}
        title="Nova unidade"
        onClose={() => setOpen(false)}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button disabled={!form.codigo_interno || !form.nome || create.isPending} onClick={() => create.mutate()}>
              Salvar
            </Button>
          </div>
        }
      >
        <div className="space-y-3">
          <Input
            label={CREATE_LABELS.codigo_interno}
            className="font-mono text-sm"
            value={form.codigo_interno}
            placeholder="8190-001-F1"
            onChange={(e) => setForm({ ...form, codigo_interno: e.target.value })}
          />
          {(["nome", "andar", "area_privativa", "tipo", "dormitorios", "vagas", "id_gc"] as const).map((k) => (
            <Input
              key={k}
              label={CREATE_LABELS[k] ?? k}
              value={form[k]}
              onChange={(e) => setForm({ ...form, [k]: e.target.value })}
            />
          ))}
          {create.isError && <p className="text-sm text-red-600">{String(create.error)}</p>}
        </div>
      </Dialog>
    </div>
  );
}
