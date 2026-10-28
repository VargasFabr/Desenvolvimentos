from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import Response, JSONResponse
from PIL import Image
from pydantic import BaseModel

import reset_password

app = FastAPI()


class ResetPasswordRequest(BaseModel):
    email: str

@app.get("/health")
def health():
    return {"ok": True}

def _normalize_to_rgb(img: Image.Image) -> Image.Image:
    # Converte qualquer modo com alpha para RGB em fundo branco,
    # evitando erros em PNG/WEBP transparentes ao salvar em JPEG.
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    return img.convert("RGB")

def _safe_filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name or "imagem"
    base = name.rsplit(".", 1)[0] if "." in name else name
    return f"{base}.jpg"

def _convert_bytes_to_jpeg(content: bytes, quality: int, frame: int, max_side: int, max_bytes: int) -> bytes:
    img = Image.open(BytesIO(content))

    # Para GIF/WEBP animado, usa um frame específico (default: 0).
    if getattr(img, "is_animated", False):
        total_frames = getattr(img, "n_frames", 1)
        safe_frame = max(0, min(frame, total_frames - 1))
        img.seek(safe_frame)

    img = _normalize_to_rgb(img)

    # Reduz resolução para controlar tamanho final do arquivo.
    safe_max_side = max(320, min(max_side, 4096))
    if max(img.size) > safe_max_side:
        img.thumbnail((safe_max_side, safe_max_side), Image.Resampling.LANCZOS)

    # Tenta atingir limite de bytes com degradação progressiva de qualidade.
    target_bytes = max(200_000, min(max_bytes, 12_000_000))
    quality_candidates = [
        max(1, min(100, quality)),
        82, 76, 70, 64, 58, 52, 46, 40,
    ]

    tried = set()
    for q in quality_candidates:
        if q in tried:
            continue
        tried.add(q)
        out = BytesIO()
        img.save(out, format="JPEG", quality=q, optimize=True, progressive=True)
        data = out.getvalue()
        if len(data) <= target_bytes:
            return data

    # Fallback final: retorna o mais comprimido tentado.
    out = BytesIO()
    img.save(out, format="JPEG", quality=35, optimize=True, progressive=True)
    return out.getvalue()

def _download_image_from_url(url: str) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="URL invalida: use http/https")

    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (n8n-image-converter)",
            "Accept": "image/*,*/*;q=0.8",
        },
    )
    with urlopen(req, timeout=25) as resp:
        content_type = (resp.headers.get("Content-Type") or "").lower()
        data = resp.read()

    if not data:
        raise HTTPException(status_code=400, detail="Nao foi possivel baixar a imagem (vazio)")
    # Nao confia cegamente no Content-Type; alguns CDNs retornam header incorreto.
    # A validacao real acontece no Pillow em _convert_bytes_to_jpeg.
    return data


@app.post("/reset-password")
def reset_password_endpoint(req: ResetPasswordRequest):
    # OTTO_ADMIN_* vem do ambiente do container (docker-compose + .env).
    # OTTO_TARGET_EMAIL é passado via request JSON.
    res = reset_password.main(target_email=req.email)
    return res

@app.post("/convert/jpeg")
async def convert_jpeg(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    quality: int = 86,
    frame: int = 0,
    max_side: int = 1600,
    max_bytes: int = 4_800_000,
):
    try:
        if file is None and not url:
            raise HTTPException(status_code=400, detail="Envie arquivo (file) ou URL (url)")

        if file is not None:
            content = await file.read()
            if not content:
                raise HTTPException(status_code=400, detail="Arquivo vazio")
            filename = (file.filename or "imagem").rsplit(".", 1)[0] + ".jpg"
        else:
            content = _download_image_from_url(str(url))
            filename = _safe_filename_from_url(str(url))

        jpeg_bytes = _convert_bytes_to_jpeg(content, quality, frame, max_side, max_bytes)
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

        return Response(
            content=jpeg_bytes,
            media_type="image/jpeg",
            headers=headers,
        )
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "error": str(e),
                "hint": "Formato nao suportado pelo Pillow ou arquivo invalido/corrompido.",
            },
        )