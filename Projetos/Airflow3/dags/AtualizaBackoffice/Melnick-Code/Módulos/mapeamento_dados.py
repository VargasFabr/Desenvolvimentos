# Mapeamento de dados da companhia. Aqui são definidos os nomes padronizados para os campos usados internamente na Melnick.
# Colunas que forem mapeadas para None devem ignoradas nos retornos.

import copy

MONDAY_COLUMN_ID_MAP = {
    "18392682833": {
        "name": "negocios_backoffice_dev",
        "mapping": {
            "name": "nome_processo",
            "state": "status_item_monday",
            "updated_at": "atualizado_em",
            "subtasks_mkv8ynv0": None, # colunas definidas para None são excluídas dos retornos
            "person": None,
            "status": "status_negocio",
            "data": "negocio_criado_em",
            "email_mkv6p1f7": None,
            "file_mkv6fg1e": None,
            "pulse_id_mkv98k75": None,
            "customer_process_id": "id_negocio",
            "unit_id": "id_unidade",
            "nome_empreendimento": "nome_empreendimento",
            "nome_torre": "nome_torre",
            "numero_unidade": "numero_unidade",
            "status_reserva": "status_reserva",
            "posicao_fila_reserva": "posicao_fila",
            "integracao_reserva": "status_integracao_reserva",
            "nome_cliente": "nome_cliente",
            "nome_corretor": "nome_corretor",
            "nome_imobiliaria": "nome_imobiliaria",
            "data_comeco_reserva": "data_comeco_reserva",
            "pulse_updated_mkve9evf": "ultima_atualizacao",
            "status_proposta": "status_proposta",
            "data_proposta": "data_proposta",
            "perda_vpl": "perda_vpl",
            "politica": "desconto_politica",
            "percent_financiado": "percentual_financiado",
            "integracao_proposta": "status_integracao_proposta",
            "emissor": None,
            "valor_bruto": "valor_proposta",
            "valor_comissao": "valor_comissao",
            "valor_liquido": "valor_liquido",
            "board_relation_mkvkgm8z": None,
            "numero_pv_gc": "numero_proposta_gc",
            "link_reserva": "link_reserva",
            "link_proposta": "link_proposta",
            "percentual_comissao": "percentual_comissao",
            "integracao_docusign": "status_integracao_docusign",
            "id_envelope_docusign": "id_envelope",
            "nome_contrato": "nome_contrato",
            "status_emissao": "status_emissao",
            "status_contrato": "status_contrato",
            "pendencias_analise": "pendencias_analise",
            "link_contrato": "link_contrato",
            "cpf_cnpj": "documento_cliente",
            "corretor": "id_corretor", # relação com o quadro de corretores no Monday
            "imobiliaria": "id_imobiliaria", # relação com o quadro de imobiliárias no Monday
            "gerente": "id_gerente", # relação com o quadro de contas no Monday
            "executivo": "id_executivo", # relação com o quadro de contas no Monday
            "data_reserva": "data_reserva",
            "proposta_criada_em": "proposta_criada_em",
            "status_analise_cred": "status_analise_credito",
            "tags": None,
            "pendencias_credito": "pendencias_credito",
            "date_mkx293z7": None,
            "color_mkx2bckm": "status_pasta",
            "vendedor": "id_vendedor", # relação com o quadro de vendedores no Monday
        },
    },
    "18392694351": {
        "name": "contas_backoffice_dev",
        "mapping": {
            "name": "nome",
            "text_mkywmptw": "id_conta",
            "tipo_de_conta": "tipo_de_conta",
            "cpf_cnpj": "documento",
            "creci": "creci",
        },
    },
}

# Board duplicado de negócios (AutoBackoffice 2.0, id 18410571736).
# Presume mesma estrutura de colunas do dev; se o Monday alterar IDs ao duplicar, ajuste.
MONDAY_COLUMN_ID_MAP["18410571736"] = {
    "name": "negocios_backoffice_2_0",
    "mapping": copy.deepcopy(MONDAY_COLUMN_ID_MAP["18392682833"]["mapping"]),
}
# 2.0: não sincroniza relações com o board de contas (só texto na página).
for _col_rel in ("corretor", "imobiliaria", "gerente", "executivo", "vendedor"):
    MONDAY_COLUMN_ID_MAP["18410571736"]["mapping"][_col_rel] = None
# 2.0: coluna texto "Executivos" no board de negócios.
MONDAY_COLUMN_ID_MAP["18410571736"]["mapping"]["text_mm327zen"] = "nome_executivos"

# Board duplicado de negócios (AutoBackoffice 2.0 DEV, id 18411789432).
# Presume mesma estrutura de colunas do dev; se o Monday alterar IDs ao duplicar, ajuste.
MONDAY_COLUMN_ID_MAP["18411789432"] = {
    "name": "negocios_backoffice_2_0_dev",
    "mapping": copy.deepcopy(MONDAY_COLUMN_ID_MAP["18392682833"]["mapping"]),
}
# 2.0: não sincroniza relações com o board de contas (só texto na página).
for _col_rel in ("corretor", "imobiliaria", "gerente", "executivo", "vendedor"):
    MONDAY_COLUMN_ID_MAP["18411789432"]["mapping"][_col_rel] = None
# 2.0: coluna texto "Executivos" no board de negócios.
MONDAY_COLUMN_ID_MAP["18411789432"]["mapping"]["text_mm327zen"] = "nome_executivos"

# Reúne todos os mapeamentos disponíveis em um único dicionário para fácil acesso
MELNICK_MAPPING = {
    "monday": MONDAY_COLUMN_ID_MAP
}

def map_dict_keys(fonte: str, id_mapeamento: str, dict_to_map: dict, invert_mapping: bool = False) -> dict:
    """
    Mapeia os nomes das colunas ou chaves para seus nomes padronizados Melnick.
    Args:
        fonte (str): Fonte dos dados (ex: "monday").
        id_mapeamento (str): ID do mapeamento a ser usado.
        dict_to_map (dict): Dicionário de dados a ser mapeado.
        invert_mapping (bool): Se True, inverte o mapeamento (nomes para IDs).
    Returns:
        dict: Dados do item com IDs de colunas mapeados para nomes padronizados ou vice-versa.
    """
    if fonte not in MELNICK_MAPPING:
        raise ValueError(f"Nenhum mapeamento definido para a fonte {fonte}")
    
    if id_mapeamento not in MELNICK_MAPPING[fonte]:
        raise ValueError(f"Nenhum mapeamento definido para o ID {id_mapeamento} na fonte {fonte}")

    mapping = MELNICK_MAPPING[fonte][id_mapeamento]["mapping"]
    if invert_mapping:
        mapping = {v: k for k, v in mapping.items() if v is not None}

    mapped_data = {}
    for column_id, value in dict_to_map.items():
        if column_id in mapping:
            mapped_key = mapping[column_id]
            if mapped_key is not None:
                mapped_data[mapped_key] = value
                
    return mapped_data