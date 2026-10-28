import { ReactNode, useEffect, useId, useRef } from "react";
import { useEscape } from "../../hooks/useEscape";
import Button from "./Button";

type Props = {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg";
};

const SIZE = { sm: "max-w-md", md: "max-w-lg", lg: "max-w-2xl" };

export default function Dialog({ open, title, onClose, children, footer, size = "md" }: Props) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);

  useEscape(onClose, open);

  useEffect(() => {
    if (!open) return;
    const first = panelRef.current?.querySelector<HTMLElement>("input:not([readonly]), select, textarea");
    first?.focus();
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4" role="presentation">
      <button
        type="button"
        className="absolute inset-0 bg-black/40"
        aria-label="Fechar diálogo"
        onClick={onClose}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={`relative w-full ${SIZE[size]} rounded-lg bg-white shadow-xl`}
      >
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h3 id={titleId} className="text-lg font-semibold">
            {title}
          </h3>
          <Button variant="ghost" size="sm" aria-label="Fechar" onClick={onClose}>
            ✕
          </Button>
        </div>
        <div className="px-6 py-4">{children}</div>
        {footer && <div className="border-t border-border px-6 py-4">{footer}</div>}
      </div>
    </div>
  );
}
