import { useMutation } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { api, ImportPreview } from "../api/client";
import Button from "../components/ui/Button";
import PageHeader from "../components/ui/PageHeader";

type Tab = "torres" | "unidades";

export default function ImportExcel() {
  const [tab, setTab] = useState<Tab>("torres");
  const [step, setStep] = useState(1);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [msg, setMsg] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const reset = () => {
    setStep(1);
    setPreview(null);
    setMsg("");
  };

  const upload = useMutation({
    mutationFn: async (f: File) => {
      const data =
        tab === "torres" ? await api.importPreview(f) : await api.importUnidadesPreview(f);
      setPreview(data as ImportPreview);
      setStep(2);
    },
  });

  const confirm = useMutation({
    mutationFn: async () => {
      if (!preview?.payload?.length) throw new Error("Nenhuma linha válida");
      return tab === "torres"
        ? api.importConfirm(preview.payload)
        : api.importUnidadesConfirm(preview.payload);
    },
    onSuccess: (res) => {
      setMsg(`Importados: ${(res as { importados: number }).importados} registros`);
      setStep(3);
    },
  });

  const handleFile = (f: File | undefined) => {
    if (f) upload.mutate(f);
  };

  const templateUrl = tab === "torres" ? api.templateUrl() : api.unidadesTemplateUrl();
  const steps = ["Baixar modelo", "Upload + preview", "Confirmar"];

  return (
    <div>
      <PageHeader title="Importar Excel" />
      <div className="mb-4 flex flex-wrap gap-2">
        {(["torres", "unidades"] as Tab[]).map((t) => (
          <Button key={t} variant={tab === t ? "primary" : "secondary"} size="sm" onClick={() => { setTab(t); reset(); }}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </Button>
        ))}
      </div>

      <ol className="mb-6 flex flex-wrap gap-2 text-sm" aria-label="Progresso da importação">
        {steps.map((label, i) => (
          <li
            key={label}
            aria-current={step === i + 1 ? "step" : undefined}
            className={`rounded-full px-3 py-1 ${step === i + 1 ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}
          >
            {i + 1}. {label}
          </li>
        ))}
      </ol>

      {step === 1 && (
        <section className="card p-6">
          <p className="mb-4 text-slate-600">
            {tab === "torres"
              ? "Importe empreendimentos/torres (mesmo layout do CSV Controladoria)."
              : "Importe unidades vinculadas a torres existentes (SPE + Cód. Torre + Fase)."}
          </p>
          <div className="flex flex-wrap gap-2">
            <a href={templateUrl} className="btn-primary">
              Baixar template
            </a>
            <Button variant="secondary" onClick={() => setStep(2)}>
              Já tenho o arquivo →
            </Button>
          </div>
        </section>
      )}

      {step >= 2 && step < 3 && (
        <section className="card mb-4 p-6">
          <div
            className={`mb-4 rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
              dragOver ? "border-primary bg-slate-50" : "border-border"
            }`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              handleFile(e.dataTransfer.files?.[0]);
            }}
          >
            <p className="mb-2 text-sm text-slate-600">Arraste um arquivo .xlsx ou .csv aqui</p>
            <Button variant="secondary" size="sm" onClick={() => fileRef.current?.click()}>
              Escolher arquivo
            </Button>
            <input
              ref={fileRef}
              type="file"
              accept=".xlsx,.csv"
              className="sr-only"
              onChange={(e) => handleFile(e.target.files?.[0])}
            />
          </div>
          {upload.isPending && <p aria-live="polite">Analisando arquivo…</p>}
          {upload.isError && <p className="text-red-600">{String(upload.error)}</p>}
          {preview && (
            <>
              <div className="mb-4 flex flex-wrap gap-4 text-sm">
                <span>Total: {preview.total}</span>
                <span className="text-emerald-700">Válidos: {preview.validos}</span>
                <span className="text-red-700">Erros: {preview.erros.length}</span>
              </div>
              {preview.erros.length > 0 && (
                <ul className="mb-4 list-disc pl-5 text-sm text-red-600">
                  {preview.erros.map((e, i) => (
                    <li key={i}>
                      Linha {e.linha}: {e.mensagem}
                    </li>
                  ))}
                </ul>
              )}
              <div className="table-scroll max-h-96">
                <table className="min-w-max w-full border text-sm">
                  <thead className="sticky-header">
                    <tr>
                      <th scope="col" className="p-2 text-left">
                        Linha
                      </th>
                      <th scope="col" className="p-2 text-left">
                        Código / SPE
                      </th>
                      <th scope="col" className="p-2 text-left">
                        Detalhe
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.map((r, i) => (
                      <tr key={i} className="border-t">
                        <td className="p-2">{String(r.linha)}</td>
                        <td className="p-2 font-mono">{String(r.codigo_interno ?? r.spe)}</td>
                        <td className="p-2">{String(r.empreendimento || r.torre || r.cod_torre || "")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Button
                className="mt-4"
                variant="accent"
                disabled={preview.validos === 0 || preview.erros.length > 0 || confirm.isPending}
                onClick={() => confirm.mutate()}
              >
                Confirmar importação
              </Button>
              {confirm.isError && <p className="mt-2 text-red-600">{String(confirm.error)}</p>}
            </>
          )}
        </section>
      )}

      {step === 3 && (
        <section className="rounded-lg border border-emerald-200 bg-emerald-50 p-6">
          <p className="font-medium text-emerald-800">{msg}</p>
          <button type="button" className="mt-4 text-sm underline focus-ring" onClick={reset}>
            Nova importação
          </button>
        </section>
      )}
    </div>
  );
}
