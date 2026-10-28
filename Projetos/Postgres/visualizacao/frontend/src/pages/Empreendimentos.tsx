import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
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
  { key: "cod_spe", label: "SPE", readOnly: true },
  { key: "nome_comercial", label: "Nome comercial" },
  { key: "endereco_logradouro", label: "Logradouro" },
  { key: "endereco_numero", label: "Número" },
  { key: "endereco_bairro", label: "Bairro" },
  { key: "endereco_cep", label: "CEP" },
  { key: "cidade", label: "Cidade" },
  { key: "latitude", label: "Latitude", type: "number" as const },
  { key: "longitude", label: "Longitude", type: "number" as const },
];

const CREATE_FIELDS = [
  { key: "cod_spe", label: "SPE" },
  { key: "nome_comercial", label: "Nome comercial" },
  { key: "cidade", label: "Cidade" },
] as const;

export default function Empreendimentos() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editRow, setEditRow] = useState<Record<string, unknown> | null>(null);
  const [form, setForm] = useState({ cod_spe: "", nome_comercial: "", cidade: "" });

  const { data: opcoes } = useQuery({ queryKey: ["emps-opcoes"], queryFn: api.empreendimentosOpcoes });
  const { filters, setFilters, params, clear } = useColumnFilters(opcoes);

  const { data = [], isLoading } = useQuery({
    queryKey: ["empreendimentos", params],
    queryFn: () => api.empreendimentos(params),
  });

  const columns = useMemo(() => columnsFromRows(data, ["cod_spe", "nome_comercial", "cidade", "qtd_torres"], "emps"), [data]);

  const create = useMutation({
    mutationFn: () => api.createEmpreendimento(form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["empreendimentos"] });
      qc.invalidateQueries({ queryKey: ["emps-opcoes"] });
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
      return api.updateEmpreendimento(String(editRow.id_empreendimento), body);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["empreendimentos"] });
      qc.invalidateQueries({ queryKey: ["emps-opcoes"] });
      setEditRow(null);
    },
  });

  return (
    <div>
      <PageHeader title="Empreendimentos" actions={<Button onClick={() => setOpen(true)}>Novo SPE</Button>} />
      <DataTable
        storageKey="cols-emps"
        columns={columns}
        rows={data}
        rowKey={(r) => String(r.id_empreendimento)}
        onEdit={setEditRow}
        loading={isLoading}
        stickyKey="cod_spe"
        filterOpcoes={opcoes}
        filters={filters}
        onFilterChange={(k, v) => setFilters({ ...filters, [k]: v })}
        onClearFilters={clear}
      />

      <EditDrawer
        title="Editar empreendimento"
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
        title="Novo empreendimento"
        onClose={() => setOpen(false)}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button disabled={!form.cod_spe || !form.nome_comercial || create.isPending} onClick={() => create.mutate()}>
              Salvar
            </Button>
          </div>
        }
      >
        <div className="space-y-3">
          {CREATE_FIELDS.map((f) => (
            <Input
              key={f.key}
              label={f.label}
              value={form[f.key]}
              onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
            />
          ))}
        </div>
      </Dialog>
    </div>
  );
}
