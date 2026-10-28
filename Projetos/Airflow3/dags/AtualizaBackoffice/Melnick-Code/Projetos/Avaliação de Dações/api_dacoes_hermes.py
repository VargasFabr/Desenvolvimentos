#!/usr/bin/env python3
"""API HTTP das tools Hermes para edição de dações."""
from __future__ import annotations

import os
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from dacoes_pipeline_utils import ensure_sys_path, load_project_env
from dacoes_hermes_tools import executar_tool, listar_tools

ensure_sys_path()
load_project_env()

app = FastAPI(
    title="Dações Hermes API",
    description="Tools para o Hermes Agent editar a lista SharePoint Dações.",
    version="1.0.0",
)


class ToolRequest(BaseModel):
    argumentos: dict[str, Any] = Field(default_factory=dict)


def _verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    expected = (os.getenv("DACOES_HERMES_API_KEY") or "").strip()
    if not expected:
        raise HTTPException(
            status_code=500,
            detail="DACOES_HERMES_API_KEY não configurada no ambiente.",
        )
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="API key inválida.")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/tools")
def get_tools(_: None = Depends(_verify_api_key)) -> list[dict[str, Any]]:
    return listar_tools()


@app.post("/tools/{tool_name}")
def run_tool(
    tool_name: str,
    body: ToolRequest,
    _: None = Depends(_verify_api_key),
) -> dict[str, Any]:
    result = executar_tool(tool_name, body.argumentos)
    if result.get("status") != "ok":
        raise HTTPException(status_code=400, detail=result)
    return result


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("DACOES_HERMES_HOST", "0.0.0.0")
    port = int(os.getenv("DACOES_HERMES_PORT", "8095"))
    uvicorn.run(app, host=host, port=port, reload=False)
