import { useEffect, useMemo, useRef, useState } from "react";
import { useClickOutside } from "../hooks/useClickOutside";
import { useEscape } from "../hooks/useEscape";
import { countActiveFilters, formatFilterOption } from "../utils/filters";
import Button from "./ui/Button";

export type ColumnDef<T> = {
  key: string;
  label: string;
  defaultVisible?: boolean;
  sticky?: boolean;
  truncate?: boolean;
  render?: (row: T) => React.ReactNode;
};

type Props<T extends Record<string, unknown>> = {
  storageKey: string;
  columns: ColumnDef<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  onEdit?: (row: T) => void;
  extraActions?: (row: T) => React.ReactNode;
  loading?: boolean;
  pageSize?: number;
  stickyKey?: string;
  filterOpcoes?: Record<string, string[]>;
  filters?: Record<string, string>;
  onFilterChange?: (key: string, value: string) => void;
  onClearFilters?: () => void;
};

const ID_KEYS = ["codigo_unidade", "codigo_interno", "nome", "cod_spe"];

function fmt(val: unknown): string {
  if (val == null || val === "") return "—";
  if (typeof val === "boolean") return val ? "Sim" : "Não";
  if (typeof val === "object") return JSON.stringify(val);
  return String(val);
}

function pickStickyKey(cols: ColumnDef<Record<string, unknown>>[], override?: string) {
  if (override && cols.some((c) => c.key === override)) return override;
  for (const k of ID_KEYS) {
    if (cols.some((c) => c.key === k)) return k;
  }
  return cols[0]?.key;
}

function syncScroll(from: HTMLDivElement, to: HTMLDivElement) {
  if (to.scrollLeft !== from.scrollLeft) to.scrollLeft = from.scrollLeft;
}

function HeaderFilter({
  colKey,
  label,
  options,
  value,
  isOpen,
  onToggle,
  onSelect,
  sticky,
}: {
  colKey: string;
  label: string;
  options: string[];
  value: string;
  isOpen: boolean;
  onToggle: () => void;
  onSelect: (v: string) => void;
  sticky?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const active = Boolean(value);

  useClickOutside(ref, () => isOpen && onToggle(), isOpen);
  useEscape(onToggle, isOpen);

  useEffect(() => {
    if (!isOpen) {
      setQuery("");
      return;
    }
    searchRef.current?.focus();
  }, [isOpen]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((opt) => formatFilterOption(colKey, opt).toLowerCase().includes(q));
  }, [options, query, colKey]);

  return (
    <div ref={ref} className={`relative min-w-[5rem] ${sticky ? "sticky-col-left" : ""}`}>
      <div
        className={`flex items-center gap-0.5 border-b-2 px-2 py-1.5 ${
          active ? "border-primary bg-slate-100" : "border-transparent"
        }`}
      >
        <span className="min-w-0 flex-1 truncate text-xs font-medium" title={label}>
          {label}
        </span>
        {options.length > 0 && (
          <button
            type="button"
            className={`col-filter-btn focus-ring ${active ? "col-filter-btn-active" : ""}`}
            aria-label={`Filtrar ${label}`}
            aria-expanded={isOpen}
            onClick={(e) => {
              e.stopPropagation();
              onToggle();
            }}
          >
            ▾
          </button>
        )}
      </div>
      {isOpen && (
        <div className="absolute left-0 top-full z-50 mt-0 flex max-h-72 min-w-[14rem] flex-col rounded border border-border bg-white shadow-lg">
          <div className="sticky top-0 border-b border-border bg-white p-1.5">
            <input
              ref={searchRef}
              type="search"
              className="input py-1 text-xs"
              placeholder="Pesquisar…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onClick={(e) => e.stopPropagation()}
              onKeyDown={(e) => e.stopPropagation()}
            />
          </div>
          <div className="overflow-y-auto py-1">
            <button
              type="button"
              className={`block w-full px-3 py-1.5 text-left text-xs hover:bg-slate-100 ${!value ? "bg-slate-50 font-medium" : ""}`}
              onClick={() => onSelect("")}
            >
              (Todos)
            </button>
            {filtered.length === 0 ? (
              <p className="px-3 py-2 text-xs text-muted-foreground">Nenhuma opção</p>
            ) : (
              filtered.map((opt) => (
                <button
                  key={opt}
                  type="button"
                  className={`block w-full px-3 py-1.5 text-left text-xs hover:bg-slate-100 ${
                    value === opt ? "bg-slate-50 font-medium" : ""
                  }`}
                  onClick={() => onSelect(opt)}
                >
                  {formatFilterOption(colKey, opt)}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function DataTable<T extends Record<string, unknown>>({
  storageKey,
  columns,
  rows,
  rowKey,
  onEdit,
  extraActions,
  loading,
  pageSize: initialPageSize = 50,
  stickyKey,
  filterOpcoes = {},
  filters = {},
  onFilterChange,
  onClearFilters,
}: Props<T>) {
  const allKeys = useMemo(() => columns.map((c) => c.key), [columns]);
  const defaultVisible = useMemo(
    () => columns.filter((c) => c.defaultVisible !== false).map((c) => c.key),
    [columns]
  );

  const [visible, setVisible] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) return JSON.parse(saved) as string[];
    } catch {
      /* ignore */
    }
    return defaultVisible;
  });
  const [openCols, setOpenCols] = useState(false);
  const [openFilter, setOpenFilter] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(initialPageSize);
  const [canScrollRight, setCanScrollRight] = useState(false);
  const [scrollWidth, setScrollWidth] = useState(0);
  const pickerRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const hScrollRef = useRef<HTMLDivElement>(null);
  const syncing = useRef(false);
  const pickerId = `${storageKey}-cols`;
  const activeFilterCount = countActiveFilters(filters);

  useClickOutside(pickerRef, () => setOpenCols(false), openCols);
  useEscape(() => {
    setOpenCols(false);
    setOpenFilter(null);
  }, openCols || openFilter !== null);

  useEffect(() => {
    localStorage.setItem(storageKey, JSON.stringify(visible));
  }, [storageKey, visible]);

  useEffect(() => setPage(0), [rows.length, pageSize]);

  const activeCols = columns.filter((c) => visible.includes(c.key));
  const stickyColKey = pickStickyKey(activeCols as ColumnDef<Record<string, unknown>>[], stickyKey);
  const hasActions = Boolean(onEdit || extraActions);
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  const pageRows = rows.slice(page * pageSize, page * pageSize + pageSize);
  const allVisible = visible.length === columns.length;

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const check = () => {
      const overflow = el.scrollWidth > el.clientWidth + 1;
      setCanScrollRight(overflow && el.scrollLeft + el.clientWidth < el.scrollWidth - 1);
      setScrollWidth(el.scrollWidth);
      if (hScrollRef.current) {
        hScrollRef.current.style.display = overflow ? "block" : "none";
      }
    };
    check();
    el.addEventListener("scroll", check);
    window.addEventListener("resize", check);
    const ro = new ResizeObserver(check);
    ro.observe(el);
    return () => {
      el.removeEventListener("scroll", check);
      window.removeEventListener("resize", check);
      ro.disconnect();
    };
  }, [activeCols.length, pageRows.length, loading]);

  const onMainScroll = () => {
    if (syncing.current || !scrollRef.current || !hScrollRef.current) return;
    syncing.current = true;
    syncScroll(scrollRef.current, hScrollRef.current);
    syncing.current = false;
    if (scrollRef.current) {
      setCanScrollRight(
        scrollRef.current.scrollWidth > scrollRef.current.clientWidth &&
          scrollRef.current.scrollLeft + scrollRef.current.clientWidth < scrollRef.current.scrollWidth - 1
      );
    }
  };

  const onBarScroll = () => {
    if (syncing.current || !scrollRef.current || !hScrollRef.current) return;
    syncing.current = true;
    syncScroll(hScrollRef.current, scrollRef.current);
    syncing.current = false;
  };

  const cellClass = (key: string, col: ColumnDef<T>) => {
    const base = "p-2 whitespace-nowrap";
    if (key === stickyColKey) return `${base} sticky-col-left font-mono text-xs`;
    if (col.truncate !== false && !ID_KEYS.includes(key)) return `${base} max-w-[14rem] truncate`;
    return base;
  };

  const handleFilterSelect = (key: string, value: string) => {
    onFilterChange?.(key, value);
    setOpenFilter(null);
  };

  return (
    <div className="card relative overflow-hidden">
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
        <span className="text-xs text-muted-foreground">
          {loading ? "Carregando…" : `${rows.length} registro(s)`}
          {activeFilterCount > 0 && (
            <>
              {" · "}
              <button type="button" className="underline focus-ring" onClick={onClearFilters}>
                {activeFilterCount} filtro(s) — limpar
              </button>
            </>
          )}
          {canScrollRight && !loading && " · role para ver mais colunas →"}
        </span>
        <div className="relative" ref={pickerRef}>
          <Button
            variant="secondary"
            size="sm"
            aria-expanded={openCols}
            aria-controls={pickerId}
            onClick={() => setOpenCols(!openCols)}
          >
            Colunas ({activeCols.length}/{columns.length})
          </Button>
          {openCols && (
            <div
              id={pickerId}
              className="absolute right-0 top-full z-30 mt-1 max-h-72 w-64 overflow-y-auto rounded-md border border-border bg-white p-3 shadow-lg"
              role="group"
              aria-label="Selecionar colunas"
            >
              <div className="mb-2 flex flex-wrap gap-2 border-b border-border pb-2 text-xs">
                <button type="button" className="text-slate-700 underline focus-ring" onClick={() => setVisible(allKeys)}>
                  Marcar todas
                </button>
                <button type="button" className="text-slate-700 underline focus-ring" onClick={() => setVisible([])}>
                  Desmarcar todas
                </button>
                <button
                  type="button"
                  className="text-slate-600 underline focus-ring"
                  onClick={() => setVisible(defaultVisible)}
                >
                  Restaurar padrão
                </button>
              </div>
              <label className="mb-1 flex cursor-pointer items-center gap-2 border-b border-border pb-2 text-sm font-medium">
                <input
                  type="checkbox"
                  checked={allVisible}
                  onChange={(e) => setVisible(e.target.checked ? allKeys : [])}
                />
                Marcar todas ({columns.length})
              </label>
              {columns.map((c) => (
                <label key={c.key} className="flex cursor-pointer items-center gap-2 py-1 text-sm">
                  <input
                    type="checkbox"
                    checked={visible.includes(c.key)}
                    onChange={(e) => {
                      setVisible((v) => (e.target.checked ? [...v, c.key] : v.filter((k) => k !== c.key)));
                    }}
                  />
                  {c.label}
                </label>
              ))}
            </div>
          )}
        </div>
      </div>

      {canScrollRight && (
        <div className="pointer-events-none absolute right-0 top-10 z-[5] h-[calc(100%-3rem)] w-8 bg-gradient-to-l from-white to-transparent" />
      )}

      <div
        ref={scrollRef}
        className="table-scroll max-h-[calc(100vh-16rem)]"
        aria-busy={loading}
        onScroll={onMainScroll}
      >
        {loading ? (
          <div className="space-y-2 p-4" aria-live="polite">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="skeleton h-8 w-full" />
            ))}
          </div>
        ) : rows.length === 0 ? (
          <div
            className="flex flex-col items-center justify-center py-16 text-sm text-muted-foreground"
            aria-live="polite"
          >
            <p className="font-medium text-slate-600">Nenhum registro encontrado</p>
            <p className="mt-1 text-xs">Use a setinha no cabeçalho da coluna para filtrar.</p>
          </div>
        ) : (
          <table className="min-w-max w-full text-sm">
            <thead className="sticky-header align-top">
              <tr>
                {activeCols.map((c) => {
                  const opts = filterOpcoes[c.key] ?? [];
                  const hasFilter = opts.length > 0 && onFilterChange;
                  if (hasFilter) {
                    return (
                      <th key={c.key} scope="col" className="p-0 text-left">
                        <HeaderFilter
                          colKey={c.key}
                          label={c.label}
                          options={opts}
                          value={filters[c.key] ?? ""}
                          isOpen={openFilter === c.key}
                          onToggle={() => setOpenFilter((k) => (k === c.key ? null : c.key))}
                          onSelect={(v) => handleFilterSelect(c.key, v)}
                          sticky={c.key === stickyColKey}
                        />
                      </th>
                    );
                  }
                  return (
                    <th
                      key={c.key}
                      scope="col"
                      className={
                        c.key === stickyColKey
                          ? "sticky-col-left p-2 text-left text-xs font-medium"
                          : "p-2 text-left text-xs font-medium"
                      }
                    >
                      {c.label}
                    </th>
                  );
                })}
                {hasActions && (
                  <th scope="col" className="sticky-col-right w-28 p-2 text-left text-xs font-medium">
                    Ações
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {pageRows.map((row) => (
                <tr key={rowKey(row)} className="border-t border-slate-100 hover:bg-slate-50/80">
                  {activeCols.map((c) => {
                    const raw = c.render ? null : row[c.key];
                    const text = c.render ? null : fmt(raw);
                    return (
                      <td key={c.key} className={cellClass(c.key, c)} title={text ?? undefined}>
                        {c.render ? c.render(row) : text}
                      </td>
                    );
                  })}
                  {hasActions && (
                    <td className="sticky-col-right space-x-1 p-2">
                      {onEdit && (
                        <Button variant="secondary" size="sm" onClick={() => onEdit(row)}>
                          Editar
                        </Button>
                      )}
                      {extraActions?.(row)}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div
        ref={hScrollRef}
        className="table-scroll-h border-t border-border bg-slate-50"
        onScroll={onBarScroll}
        aria-hidden={scrollWidth <= 0}
      >
        <div style={{ width: scrollWidth, height: 1 }} />
      </div>

      {!loading && rows.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border px-3 py-2 text-xs text-muted-foreground">
          <span>
            Mostrando {page * pageSize + 1}–{Math.min((page + 1) * pageSize, rows.length)} de {rows.length}
          </span>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1">
              Por página
              <select
                className="select w-auto py-1 text-xs"
                value={pageSize}
                onChange={(e) => setPageSize(Number(e.target.value))}
              >
                {[50, 100, 200].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <Button variant="secondary" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
              Anterior
            </Button>
            <span>
              {page + 1}/{totalPages}
            </span>
            <Button
              variant="secondary"
              size="sm"
              disabled={page >= totalPages - 1}
              onClick={() => setPage((p) => p + 1)}
            >
              Próxima
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
