"""JSON Schemas das tools de dações para o Hermes Agent."""

LISTAR_CAMPOS_EDITAVEIS_DACOES = {
    "name": "listar_campos_editaveis_dacoes",
    "description": "Lista os campos editáveis da lista SharePoint Dações.",
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}

BUSCAR_DACOES = {
    "name": "buscar_dacoes",
    "description": (
        "Busca dações por filtros parciais (endereço, imobiliária, cidade, corretor, aval_ia)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sharepoint_id": {"type": "integer"},
            "endereco": {"type": "string"},
            "imobiliaria": {"type": "string"},
            "cidade": {"type": "string"},
            "corretor": {"type": "string"},
            "aval_ia": {"type": "string", "enum": ["pendente", "avaliado"]},
            "limite": {"type": "integer", "default": 20},
        },
        "additionalProperties": False,
    },
}

OBTER_DACAO = {
    "name": "obter_dacao",
    "description": "Obtém uma dação pelo sharepoint_id.",
    "parameters": {
        "type": "object",
        "properties": {
            "sharepoint_id": {"type": "integer"},
        },
        "required": ["sharepoint_id"],
        "additionalProperties": False,
    },
}

EDITAR_DACAO = {
    "name": "editar_dacao",
    "description": (
        "Edita campos de uma dação no SharePoint e sincroniza no Postgres (aval_ia=avaliado)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sharepoint_id": {"type": "integer"},
            "campos": {
                "type": "object",
                "description": "Objeto chave/valor com nomes amigáveis ou normalizados.",
                "additionalProperties": True,
            },
        },
        "required": ["sharepoint_id", "campos"],
        "additionalProperties": False,
    },
}

LISTAR_DACOES_PENDENTES_IA = {
    "name": "listar_dacoes_pendentes_ia",
    "description": "Lista dações com aval_ia = pendente no Postgres.",
    "parameters": {
        "type": "object",
        "properties": {
            "limite": {"type": "integer", "default": 50},
        },
        "additionalProperties": False,
    },
}

ALL_SCHEMAS = (
    LISTAR_CAMPOS_EDITAVEIS_DACOES,
    BUSCAR_DACOES,
    OBTER_DACAO,
    EDITAR_DACAO,
    LISTAR_DACOES_PENDENTES_IA,
)
