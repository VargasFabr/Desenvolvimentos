#!/usr/bin/env python3
"""Apply npm overrides pins for Hermes Agent and verify installed versions."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
PINS_PATH = HERE / "pins.json"
EXCEPTIONS_PATH = HERE / "exceptions.json"


def log(msg: str) -> None:
    print(msg, flush=True)


def _npm_noise(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    low = s.lower()
    if low.startswith("npm notice"):
        return True
    if "browser tools ready" in low:
        return True
    if s.startswith(">") and ("postinstall" in low or "echo " in low or "node " in low):
        return True
    if s.startswith("npm warn ebadengine"):
        return True
    return False


def merge_overrides(existing: dict[str, Any] | None, pins: dict[str, Any]) -> dict[str, Any]:
    """Merge pin overrides into existing overrides without dropping unrelated keys."""
    out: dict[str, Any] = dict(existing or {})
    for key, value in pins.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            nested = dict(out[key])
            nested.update(value)
            out[key] = nested
        else:
            out[key] = value
    return out


def _self_check() -> None:
    got = merge_overrides({"lodash": "4.18.1", "ws": "8.0.0"}, {"ws": "8.21.1", "tar": "7.5.21"})
    assert got["lodash"] == "4.18.1", got
    assert got["ws"] == "8.21.1", got
    assert got["tar"] == "7.5.21", got
    nested = merge_overrides(
        {"webpack-dev-server": {"other": "1"}},
        {"webpack-dev-server": {"ws": "8.21.1"}},
    )
    assert nested["webpack-dev-server"]["other"] == "1", nested
    assert nested["webpack-dev-server"]["ws"] == "8.21.1", nested


def load_json(path: Path) -> dict[str, Any]:
    # utf-8-sig: Windows-edited package.json may carry a BOM
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def write_package_overrides(pkg_json: Path, overrides: dict[str, Any]) -> bool:
    data = load_json(pkg_json)
    before = json.dumps(data.get("overrides") or {}, sort_keys=True)
    data["overrides"] = merge_overrides(data.get("overrides"), overrides)
    after = json.dumps(data["overrides"], sort_keys=True)
    if before == after:
        return False
    with pkg_json.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return True


def run_npm_install(project_dir: Path, extra_args: list[str]) -> str:
    """Run npm install; return a one-line status summary. Raises on failure."""
    cmd = ["npm", "install", "--no-fund", "--no-audit", *extra_args]
    env = os.environ.copy()
    env.setdefault("npm_config_engine_strict", "false")
    proc = subprocess.run(
        cmd,
        cwd=str(project_dir),
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    combined = (proc.stdout or "") + (proc.stderr or "")
    useful = [ln for ln in combined.splitlines() if not _npm_noise(ln)]
    summary = next(
        (ln.strip() for ln in reversed(useful) if "in " in ln.lower() and ("up to date" in ln.lower() or "added" in ln.lower() or "removed" in ln.lower() or "changed" in ln.lower())),
        useful[-1].strip() if useful else "(sem saída)",
    )
    if proc.returncode != 0:
        for ln in useful[-20:]:
            log(f"  npm: {ln}")
        raise subprocess.CalledProcessError(proc.returncode, cmd, output=proc.stdout, stderr=proc.stderr)
    return summary


def read_pkg_version(pkg_dir: Path) -> str | None:
    pj = pkg_dir / "package.json"
    if not pj.is_file():
        return None
    try:
        meta = load_json(pj)
    except (OSError, json.JSONDecodeError):
        return None
    return str(meta.get("version") or "") or None


def find_package_versions(project_dir: Path, name: str) -> list[tuple[str, str]]:
    """Check top-level and a few nested paths only — no full tree walk (slow on Win mounts)."""
    hits: list[tuple[str, str]] = []
    candidates = [
        project_dir / "node_modules" / name,
        project_dir / "node_modules" / "webpack-dev-server" / "node_modules" / name,
        project_dir / "node_modules" / "@whiskeysockets" / "baileys" / "node_modules" / name,
        project_dir / "node_modules" / "libsignal" / "node_modules" / name,
        project_dir / "node_modules" / "jsdom" / "node_modules" / name,
    ]
    seen: set[str] = set()
    for pkg_dir in candidates:
        ver = read_pkg_version(pkg_dir)
        if ver is None:
            continue
        rel = str(pkg_dir.relative_to(project_dir)).replace("\\", "/")
        if rel in seen:
            continue
        seen.add(rel)
        hits.append((rel, ver))
    return hits


def version_ok(installed: str, expected: str) -> bool:
    """Accept exact match or installed >= expected for simple dotted semver (no prerelease)."""
    if installed == expected:
        return True
    try:
        inst = tuple(int(x) for x in installed.split("."))
        exp = tuple(int(x) for x in expected.split("."))
        n = max(len(inst), len(exp))
        inst = inst + (0,) * (n - len(inst))
        exp = exp + (0,) * (n - len(exp))
        return inst >= exp
    except ValueError:
        return False


def main() -> int:
    _self_check()

    hermes_root = Path(os.environ.get("HERMES_ROOT", "/opt/hermes")).resolve()
    report_dir = Path(os.environ.get("HERMES_REPORT_DIR", "/opt/airflow/data/hermes"))
    report_dir.mkdir(parents=True, exist_ok=True)

    if not hermes_root.is_dir():
        print(f"ERROR: HERMES_ROOT not found: {hermes_root}", file=sys.stderr, flush=True)
        return 1

    pins = load_json(PINS_PATH)
    exceptions = load_json(EXCEPTIONS_PATH)
    exception_keys = {(e["name"], e["version"]) for e in exceptions.get("allow", [])}
    projects = pins.get("projects") or {}

    log("=== Hermes deps guard ===")
    log(f"Raiz: {hermes_root}")
    log(f"Projetos: {len(projects)} | pins em {PINS_PATH.name} | exceptions em {EXCEPTIONS_PATH.name}")
    log("Fluxo por projeto: (1) merge overrides no package.json  (2) npm install  (3) conferir versões pinadas")

    report: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "hermes_root": str(hermes_root),
        "projects": {},
        "failures": [],
        "warnings": [],
    }

    for idx, (rel, cfg) in enumerate(projects.items(), start=1):
        project_dir = hermes_root if rel in (".", "") else hermes_root / rel
        label = "raiz (hermes-agent)" if rel in (".", "") else rel
        proj_report: dict[str, Any] = {"path": str(project_dir), "changed": False, "installed": {}}
        log(f"\n[{idx}/{len(projects)}] {label}")
        log(f"  path: {project_dir}")

        if not project_dir.is_dir():
            msg = f"projeto ausente: {project_dir}"
            log(f"  AVISO: {msg}")
            report["warnings"].append(msg)
            report["projects"][rel] = proj_report
            continue

        pkg_json = project_dir / "package.json"
        if not pkg_json.is_file():
            msg = f"package.json ausente: {pkg_json}"
            log(f"  AVISO: {msg}")
            report["warnings"].append(msg)
            report["projects"][rel] = proj_report
            continue

        changed = write_package_overrides(pkg_json, cfg.get("overrides") or {})
        proj_report["changed"] = changed
        n_pins = len(cfg.get("overrides") or {})
        if changed:
            log(f"  overrides: atualizados ({n_pins} pin(s) mesclados no package.json)")
        else:
            log(f"  overrides: já aplicados ({n_pins} pin(s) — sem alteração)")

        log("  npm install: aplicando lock/overrides…")
        try:
            summary = run_npm_install(project_dir, list(cfg.get("npm_args") or []))
            log(f"  npm install: ok — {summary}")
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            msg = f"npm install falhou em {project_dir}: {exc}"
            print(f"ERROR: {msg}", file=sys.stderr, flush=True)
            report["failures"].append(msg)
            report["projects"][rel] = proj_report
            continue

        expect = cfg.get("expect") or {}
        if expect:
            log(f"  verificação: {len(expect)} pacote(s) pinado(s)…")
        ok_count = 0
        for name, expected in expect.items():
            hits = find_package_versions(project_dir, name)
            top = [h for h in hits if h[0] == f"node_modules/{name}"]
            check = top or hits
            proj_report["installed"][name] = [{"path": p, "version": v} for p, v in check]
            if not check:
                msg = f"{rel}: {name} não instalado (esperado {expected})"
                log(f"  ERRO: {msg}")
                report["failures"].append(msg)
                continue
            if top:
                bad = [(p, v) for p, v in top if not version_ok(v, expected)]
                ok_any = not bad
            else:
                ok_any = any(version_ok(v, expected) for _, v in check)
                bad = [(p, v) for p, v in check if not version_ok(v, expected)]
            if not ok_any or bad:
                for p, v in bad or check:
                    key = (name, v)
                    detail = f"{rel}: {name}@{v} em {p} (quer >= {expected})"
                    if key in exception_keys:
                        log(f"  AVISO (exception TI): {detail}")
                        report["warnings"].append(detail)
                    else:
                        log(f"  ERRO: {detail}")
                        report["failures"].append(detail)
            else:
                ok_count += 1
                ver = check[0][1]
                log(f"  ok: {name}@{ver} (>= {expected})")

        if expect:
            log(f"  verificação: {ok_count}/{len(expect)} pin(s) ok")

        # Note exceptions present at top-level only (cheap)
        for name, ver in exception_keys:
            top_ver = read_pkg_version(project_dir / "node_modules" / name)
            if top_ver == ver:
                msg = f"exception presente: {name}@{ver} em {rel}/node_modules/{name}"
                report["warnings"].append(msg)
                log(f"  AVISO: {msg} (aceito em exceptions.json)")

        report["projects"][rel] = proj_report

    out = report_dir / "last_report.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")

    n_fail = len(report["failures"])
    n_warn = len(report["warnings"])
    log("\n=== Resumo ===")
    log(f"Relatório: {out}")
    log(f"Falhas: {n_fail} | Avisos (exceptions/ausências): {n_warn}")
    if n_fail:
        log("Resultado: FALHA — há pacotes fora do pin sem exception.")
        for msg in report["failures"]:
            log(f"  - {msg}")
        return 1
    log("Resultado: OK — pins aplicados/verificados; avisos são exceptions conhecidas.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-check":
        _self_check()
        print("self-check ok", flush=True)
        raise SystemExit(0)
    raise SystemExit(main())
