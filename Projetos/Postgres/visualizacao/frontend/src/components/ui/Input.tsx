import { InputHTMLAttributes, SelectHTMLAttributes } from "react";

type InputProps = InputHTMLAttributes<HTMLInputElement> & { label?: string; hint?: string };

export function Input({ label, hint, className = "", id, ...props }: InputProps) {
  const inputId = id ?? label?.toLowerCase().replace(/\s+/g, "-");
  if (!label) {
    return <input id={inputId} className={`input ${className}`} {...props} />;
  }
  return (
    <label className="label" htmlFor={inputId}>
      {label && <span className={hint ? "label-hint" : "mb-1 block"}>{label}</span>}
      {hint && !label && <span className="label-hint">{hint}</span>}
      <input id={inputId} className={`input mt-1 ${className}`} {...props} />
    </label>
  );
}

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & { label?: string };

export function Select({ label, className = "", id, children, ...props }: SelectProps) {
  const selectId = id ?? label?.toLowerCase().replace(/\s+/g, "-");
  return (
    <label className="label" htmlFor={selectId}>
      {label && <span className="mb-1 block text-xs font-normal text-muted-foreground">{label}</span>}
      <select id={selectId} className={`select mt-1 ${className}`} {...props}>
        {children}
      </select>
    </label>
  );
}
