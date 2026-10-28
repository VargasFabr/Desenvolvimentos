import { COLUMN_LABELS } from "./columns";

const BOOL_LABELS: Record<string, string> = { true: "Sim", false: "Não" };
const BOOL_KEYS = new Set(["principal", "permutante"]);

export function emptyFilters(keys: string[]): Record<string, string> {
  return Object.fromEntries(keys.map((k) => [k, ""]));
}

export function formatFilterOption(key: string, value: string): string {
  if (BOOL_KEYS.has(key)) return BOOL_LABELS[value] ?? value;
  return value;
}

export function countActiveFilters(filters: Record<string, string>): number {
  return Object.values(filters).filter(Boolean).length;
}

export function paramsFromFilters(filters: Record<string, string>, limit = 500): Record<string, string | number> {
  const p: Record<string, string | number> = { limit };
  for (const [k, v] of Object.entries(filters)) {
    if (v) p[k] = v;
  }
  return p;
}

export function mergeFilters(
  base: Record<string, string>,
  patch: Record<string, string>
): Record<string, string> {
  return { ...base, ...patch };
}
