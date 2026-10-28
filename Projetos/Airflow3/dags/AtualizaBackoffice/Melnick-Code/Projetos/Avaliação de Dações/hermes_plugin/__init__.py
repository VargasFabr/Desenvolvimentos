"""Plugin Hermes — edição de dações SharePoint + sync Postgres."""
from __future__ import annotations

from . import schemas, tools
from .bootstrap import check_dacoes_available

_TOOLSET = "dacoes"

_TOOLS = (
    (schemas.LISTAR_CAMPOS_EDITAVEIS_DACOES, tools.handle_listar_campos_editaveis_dacoes, "📋"),
    (schemas.BUSCAR_DACOES, tools.handle_buscar_dacoes, "🔎"),
    (schemas.OBTER_DACAO, tools.handle_obter_dacao, "🏠"),
    (schemas.EDITAR_DACAO, tools.handle_editar_dacao, "✏️"),
    (schemas.LISTAR_DACOES_PENDENTES_IA, tools.handle_listar_dacoes_pendentes_ia, "⏳"),
)


def register(ctx) -> None:
    for schema, handler, emoji in _TOOLS:
        ctx.register_tool(
            name=schema["name"],
            toolset=_TOOLSET,
            schema=schema,
            handler=handler,
            check_fn=check_dacoes_available,
            requires_env=["DACOES", "DACOES_PASS", "POSTGRES_USER", "POSTGRES_PASS"],
            emoji=emoji,
        )
