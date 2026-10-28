import Button from "./ui/Button";
import Sheet from "./ui/Sheet";

type Field = {
  key: string;
  label: string;
  type?: "text" | "number" | "date" | "checkbox";
  readOnly?: boolean;
};

type Props = {
  title: string;
  open: boolean;
  fields: Field[];
  values: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
  onClose: () => void;
  onSave: () => void;
  saving?: boolean;
  error?: string | null;
};

export default function EditDrawer({
  title,
  open,
  fields,
  values,
  onChange,
  onClose,
  onSave,
  saving,
  error,
}: Props) {
  return (
    <Sheet
      open={open}
      title={title}
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button disabled={saving} onClick={onSave}>
            {saving ? "Salvando…" : "Salvar"}
          </Button>
        </div>
      }
    >
      <div className="space-y-3 text-sm">
        {fields.map((f) => (
          <label key={f.key} className="label">
            <span className="label-hint">{f.label}</span>
            {f.type === "checkbox" ? (
              <input
                type="checkbox"
                className="mt-2 h-4 w-4 focus-ring"
                checked={Boolean(values[f.key])}
                disabled={f.readOnly}
                onChange={(e) => onChange(f.key, e.target.checked)}
              />
            ) : (
              <input
                type={f.type ?? "text"}
                className="input mt-1 disabled:bg-slate-100"
                value={String(values[f.key] ?? "")}
                readOnly={f.readOnly}
                onChange={(e) =>
                  onChange(
                    f.key,
                    f.type === "number" ? (e.target.value ? Number(e.target.value) : "") : e.target.value
                  )
                }
              />
            )}
          </label>
        ))}
      </div>
      {error && (
        <p className="mt-3 text-sm text-red-600" role="alert">
          {error}
        </p>
      )}
    </Sheet>
  );
}
