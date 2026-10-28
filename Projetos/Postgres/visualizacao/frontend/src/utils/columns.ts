import { useRef } from "react";
import { ColumnDef } from "../components/DataTable";

export const COLUMN_LABELS: Record<string, string> = {
  id_torre: "ID torre",
  id_empreendimento: "ID empreendimento",
  id_fase: "ID fase",
  id_incorporadora: "ID incorporadora",
  codigo_interno: "Código interno",
  codigo_unidade: "Cód. unidade",
  cod_torre: "Cód. torre",
  nome_torre: "Torre",
  nome_comercial: "Empreendimento",
  cod_spe: "SPE",
  numero_fase: "Fase",
  nome_fase: "Nome fase",
  segmento: "Segmento",
  estagio: "Estágio",
  tipo_empresa: "Empresa",
  principal: "Principal",
  permutante: "Permutante",
  lancamento: "Lançamento",
  entrega: "Entrega",
  inicio_obra: "Início obra",
  vgv_bruto: "VGV bruto",
  vgv_liquido: "VGV líquido",
  unidades_total: "Unidades",
  unidades_permuta: "Unidades permuta",
  id_orulo: "ID Órulo",
  pct_melnick: "% Melnick",
  tags: "Tags",
  endereco_logradouro: "Logradouro",
  endereco_numero: "Número",
  endereco_bairro: "Bairro",
  endereco_cep: "CEP",
  latitude: "Latitude",
  longitude: "Longitude",
  empresa_parceira: "Empresa parceira",
  nome_incorporadora: "Incorporadora",
  cnpj_incorporadora: "CNPJ incorporadora",
  cidade: "Cidade",
  uf: "UF",
  nome_composto: "Nome composto",
  qtd_fases: "Qtd fases",
  qtd_torres: "Qtd torres",
  qtd_torres_principais: "Qtd principais",
  qtd_torres_vaga: "Qtd vagas",
  vgv_bruto_max_torre: "VGV máx torre",
  vgv_bruto_soma_torres: "VGV soma torres",
  torre_principal_codigo: "Torre principal código",
  torre_principal_nome: "Torre principal nome",
  id_unidade: "ID unidade",
  nome: "Unidade",
  andar: "Andar",
  area_privativa: "Área privativa",
  fracao_ideal: "Fração ideal",
  tipo: "Tipo",
  dormitorios: "Dormitórios",
  vagas: "Vagas",
  id_gc: "ID GC",
  vinculado_a: "Vinculado a",
};

const DEFAULT_VISIBLE = new Set([
  "codigo_unidade",
  "codigo_interno",
  "cod_spe",
  "nome_comercial",
  "nome_torre",
  "numero_fase",
  "segmento",
  "principal",
  "cidade",
  "uf",
  "qtd_torres",
  "nome",
  "andar",
  "area_privativa",
]);

const HIDDEN_BY_DEFAULT = /^id_/;

const columnCache = new Map<string, ColumnDef<Record<string, unknown>>[]>();

export function columnsFromRows(
  rows: Record<string, unknown>[],
  extraDefault?: string[],
  cacheKey?: string
): ColumnDef<Record<string, unknown>>[] {
  if (rows.length > 0) {
    const defaults = new Set([...DEFAULT_VISIBLE, ...(extraDefault ?? [])]);
    const cols = Object.keys(rows[0]).map((key) => ({
      key,
      label: COLUMN_LABELS[key] ?? key,
      defaultVisible: defaults.has(key) && !HIDDEN_BY_DEFAULT.test(key),
      truncate: !["codigo_unidade", "codigo_interno", "cod_spe", "nome"].includes(key),
    }));
    if (cacheKey) columnCache.set(cacheKey, cols);
    return cols;
  }
  if (cacheKey && columnCache.has(cacheKey)) return columnCache.get(cacheKey)!;
  return [];
}
