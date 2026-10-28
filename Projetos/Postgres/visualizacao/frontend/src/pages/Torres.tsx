import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
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
  { key: "codigo_interno", label: "Código interno", readOnly: true },
  { key: "cod_spe", label: "SPE", readOnly: true },
  { key: "nome_torre", label: "Nome torre" },
  { key: "segmento", label: "Segmento" },
  { key: "estagio", label: "Estágio" },
  { key: "tipo_empresa", label: "Tipo empresa" },
  { key: "principal", label: "Principal", type: "checkbox" as const },
  { key: "permutante", label: "Permutante", type: "checkbox" as const },
  { key: "lancamento", label: "Lançamento", type: "date" as const },
  { key: "entrega", label: "Entrega", type: "date" as const },
  { key: "vgv_bruto", label: "VGV bruto", type: "number" as const },
  { key: "vgv_liquido", label: "VGV líquido", type: "number" as const },
  { key: "unidades_total", label: "Unidades total", type: "number" as const },
  { key: "id_orulo", label: "ID Órulo" },
];

const CREATE_LABELS: Record<string, string> = {
  cod_spe: "SPE",
  nome_comercial: "Nome comercial",
  cod_torre: "Cód. torre",
  nome_torre: "Nome torre",
  segmento: "Segmento",
};

export default function Torres() {
  const qc = useQueryClient();
  const [openCreate, setOpenCreate] = useState(false);
  const [editRow, setEditRow] = useState<Record<string, unknown> | null>(null);
  const [form, setForm] = useState({
    cod_spe: "",
    nome_comercial: "",
    cod_torre: "",
    numero_fase: 1,
    nome_torre: "",
    segmento: "",
    principal: false,
  });

  const { data: opcoes } = useQuery({ queryKey: ["torres-opcoes"], queryFn: api.torresOpcoes });
  const { filters, setFilters, params, clear } = useColumnFilters(opcoes);

  const { data = [], isLoading } = useQuery({
    queryKey: ["torres", params],
    queryFn: () => api.torres(params),
  });

  const columns = useMemo(
    () => columnsFromRows(data, ["codigo_interno", "cod_spe", "nome_torre", "segmento"], "torres"),
    [data]
  );

  const create = useMutation({
    mutationFn: () => api.createTorre(form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["torres"] });
      qc.invalidateQueries({ queryKey: ["torres-opcoes"] });
      setOpenCreate(false);
    },
  });

  const update = useMutation({
    mutationFn: () => {
      if (!editRow) throw new Error("Sem linha");
      const body: Record<string, unknown> = {};
      for (const f of EDIT_FIELDS) {
        if (f.readOnly || f.key === "codigo_interno" || f.key === "cod_spe") continue;
        const v = editRow[f.key];
        if (v !== undefined && v !== "") body[f.key] = v;
      }
      return api.updateTorre(String(editRow.id_torre), body);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["torres"] });
      qc.invalidateQueries({ queryKey: ["torres-opcoes"] });
      setEditRow(null);
    },
  });

  return (
    <div>
      <PageHeader
        title="Torres"
        actions={
          <>
            <a href={api.exportUrl()} className="btn-secondary btn-sm">
              Exportar Excel
            </a>
            <Button onClick={() => setOpenCreate(true)}>Nova torre</Button>
          </>
        }
      />
      <DataTable
        storageKey="cols-torres"
        columns={columns}
        rows={data}
        rowKey={(r) => String(r.id_torre)}
        onEdit={setEditRow}
        loading={isLoading}
        stickyKey="codigo_interno"
        filterOpcoes={opcoes}
        filters={filters}
        onFilterChange={(k, v) => setFilters({ ...filters, [k]: v })}
        onClearFilters={clear}
        extraActions={(r) => (
          <Link to={`/unidades?codigo_interno=${r.codigo_interno}`} className="btn-secondary btn-sm inline-flex">
            Unidades
          </Link>
        )}
      />

      <EditDrawer
        title="Editar torre"
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
        open={openCreate}
        title="Nova torre"
        size="lg"
        onClose={() => setOpenCreate(false)}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setOpenCreate(false)}>
              Cancelar
            </Button>
            <Button disabled={!form.cod_spe || !form.cod_torre || create.isPending} onClick={() => create.mutate()}>
              Salvar
            </Button>
          </div>
        }
      >
        <div className="grid gap-3 sm:grid-cols-2">
          {(["cod_spe", "nome_comercial", "cod_torre", "nome_torre", "segmento"] as const).map((k) => (
            <Input
              key={k}
              label={CREATE_LABELS[k] ?? k}
              value={String(form[k] ?? "")}
              onChange={(e) => setForm({ ...form, [k]: e.target.value })}
            />
          ))}
        </div>
      </Dialog>
    </div>
  );
}
