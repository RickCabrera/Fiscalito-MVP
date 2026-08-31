#!/usr/bin/env python3
"""
Hook PreToolUse para Fiscalito (adaptado del hook de Pulso).

Qué hace:
  Auto-aprueba comandos SEGUROS (solo lectura + verificación: pytest, ruff check,
  mypy, tsc --noEmit) para que el agente no pregunte por ellos, incluso dirigiendo
  el trabajo desde el celular. Cualquier cosa que NO sea claramente segura cae al
  flujo normal (pregunta). Es "fail-safe": ante la duda, NO aprueba.

Qué NO auto-aprueba (a propósito):
  - python -c "..." (código arbitrario)
  - escrituras (>, rm, mv, set-content...), git push, sudo, secretos
  - npm run build / npm install (escriben; los cubre el allow del settings.json,
    que sí muestra su regla — este hook solo rescata lo compuesto y lo obvio)
  - PowerShell con control de flujo (if/else, { }).
  NO puede sobreescribir las reglas 'deny'/'ask' del settings.json.
"""
import json
import re
import sys

# Binarios / cmdlets de SOLO LECTURA.
SAFE = {
    "ls", "cat", "find", "grep", "rg", "head", "tail", "wc", "sort", "uniq",
    "pwd", "which", "where", "tree", "file", "diff", "stat", "echo", "cd",
    "basename", "dirname", "realpath", "dir",
    "get-childitem", "get-content", "get-service", "get-process",
    "get-location", "get-command", "get-item", "get-nettcpconnection",
    "select-object", "where-object", "format-table", "format-list",
    "measure-object", "test-path", "resolve-path", "gci", "gc",
}
GIT_SAFE = {"status", "diff", "log", "show", "branch", "rev-parse",
            "remote", "fetch", "ls-files", "describe", "config"}
# Herramientas de verificación que SÍ auto-aprobamos (no escriben código de producto).
RUFF_SAFE = {"check"}

DANGER = re.compile(
    r"\brm\b|\brmdir\b|\bmv\b|\bdd\b|mkfs|\bchmod\b|\bchown\b|\bsudo\b|"
    r"\bwget\b|--dangerously|>>|(?<![0-9])>(?!\s*/dev/null)|"
    r"\bgit\s+push\b|\bgit\s+reset\b|\bgit\s+clean\b|\bgit\s+rebase\b|"
    r"\bkill\b|\bpkill\b|\bset-content\b|\bremove-item\b|\bnew-item\b|"
    r"\bout-file\b|\bif\b|\belse\b|\{|\}|\.env\b|\.pem\b|id_rsa|\.ssh|"
    r"secret|credential|\s-c\s|--fix\b|ruff\s+format(?!\s+--check)",
    re.IGNORECASE,
)


def seg_ok(seg: str) -> bool:
    seg = seg.strip()
    if not seg:
        return True
    parts = seg.split()
    cmd = parts[0].lower()

    # pytest directo, o vía python/python.exe -m pytest|mypy
    if cmd == "pytest" or cmd.endswith("/pytest") or cmd.endswith("pytest.exe"):
        return True
    if cmd in ("python", "python3") or cmd.endswith("python.exe"):
        if len(parts) >= 3 and parts[1] == "-m" and parts[2] in ("pytest", "mypy", "ruff"):
            # python -m ruff solo con subcomando check (el DANGER ya vetó --fix)
            if parts[2] == "ruff":
                return len(parts) >= 4 and parts[3] in RUFF_SAFE
            return True
        return any(p.lower() in ("--version", "-v", "version") for p in parts[1:])
    if cmd == "ruff":
        return len(parts) >= 2 and parts[1].lower() in RUFF_SAFE
    if cmd == "mypy":
        return True
    if cmd == "npx":
        # solo tsc en modo verificación
        return len(parts) >= 3 and parts[1] == "tsc" and "--noemit" in [p.lower() for p in parts[2:]]
    if cmd == "npm":
        # npm run lint / npm test: verifican, no escriben producto
        if len(parts) >= 3 and parts[1] == "run" and parts[2] in ("lint", "test"):
            return True
        return len(parts) >= 2 and parts[1] == "test"
    if cmd == "git":
        return (parts[1].lower() if len(parts) > 1 else "") in GIT_SAFE
    if cmd in ("pip", "pip3", "node"):
        return any(p.lower() in ("--version", "-v", "version") for p in parts[1:])
    if cmd.startswith("$"):
        return True
    return cmd in SAFE


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    cmd = (data.get("tool_input") or {}).get("command", "")
    if not cmd:
        sys.exit(0)
    if DANGER.search(cmd):
        sys.exit(0)
    segments = re.split(r"&&|\|\||[;|]", cmd)
    if all(seg_ok(s) for s in segments):
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "Comando seguro (lectura / verificación) — auto-aprobado por el hook de Fiscalito."
            }
        }))
    sys.exit(0)


if __name__ == "__main__":
    main()
