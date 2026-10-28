import os
import sys
from pathlib import Path


def _ensure_lib_path() -> None:
    """Localiza dados/lib — funciona no host e no container (/dados via PYTHONPATH)."""
    for root in (
        os.environ.get("DADOS_ROOT"),
        *(os.environ.get("PYTHONPATH", "").split(os.pathsep)),
    ):
        if not root:
            continue
        p = Path(root)
        if (p / "lib" / "cad_parsers.py").is_file() and str(p) not in sys.path:
            sys.path.insert(0, str(p))
            return
    for parent in Path(__file__).resolve().parents:
        if (parent / "lib" / "cad_parsers.py").is_file():
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
            return


_ensure_lib_path()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import aliases, empreendimentos, fases, import_export, torres, unidades

app = FastAPI(title="Cadastro Melnick — Visualização", version="0.1.0")

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(empreendimentos.router)
app.include_router(fases.router)
app.include_router(torres.router)
app.include_router(aliases.router_aliases)
app.include_router(aliases.router_ids)
app.include_router(unidades.router)
app.include_router(import_export.router)


@app.get("/api/health")
def health():
    return {"ok": True}
