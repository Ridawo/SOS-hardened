#!/usr/bin/env python3
"""Quality gate bloqueante basado en `npm audit --json`.

Uso:
    python devsecops/scripts/check_npm_gate.py npm-audit.json

Lee `.metadata.vulnerabilities` (formato npm v7+: info/low/moderate/high/
critical/total), imprime un resumen por severidad y decide:
- sale 1 si high + critical > 0  -> hace fallar el pipeline (gate real).
- sale 0 si no hay high ni critical.

Fichero ausente o JSON invalido -> mensaje claro y codigo != 0.
Solo stdlib.
"""

import json
import sys

EXIT_PASS = 0
EXIT_FAIL = 1       # hay vulnerabilidades high/critical
EXIT_ERROR = 2      # error de uso / fichero / parseo

SEVERITIES = ("critical", "high", "moderate", "low", "info")


def eprint(*args):
    print(*args, file=sys.stderr)


def load_report(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        eprint("Uso: check_npm_gate.py <npm-audit.json>")
        return EXIT_ERROR

    path = argv[0]
    try:
        report = load_report(path)
    except FileNotFoundError:
        eprint("[ERROR] No se encuentra el fichero de auditoria: %s" % path)
        return EXIT_ERROR
    except json.JSONDecodeError as err:
        eprint("[ERROR] JSON invalido en %s: %s" % (path, err))
        return EXIT_ERROR
    except OSError as err:
        eprint("[ERROR] No se puede leer %s: %s" % (path, err))
        return EXIT_ERROR

    if not isinstance(report, dict):
        eprint("[ERROR] El informe no tiene la estructura esperada (objeto JSON).")
        return EXIT_ERROR

    vulns = report.get("metadata", {}).get("vulnerabilities")
    if not isinstance(vulns, dict):
        eprint("[ERROR] No se encontro '.metadata.vulnerabilities' en el "
               "informe. Comprueba que es salida de 'npm audit --json' (npm v7+).")
        return EXIT_ERROR

    counts = {sev: int(vulns.get(sev, 0) or 0) for sev in SEVERITIES}
    total = int(vulns.get("total", sum(counts.values())) or 0)

    print("Resumen npm audit (quality gate SCA):")
    for sev in SEVERITIES:
        print("  %-9s %d" % (sev + ":", counts[sev]))
    print("  %-9s %d" % ("total:", total))

    blocking = counts["high"] + counts["critical"]
    if blocking > 0:
        eprint("[GATE] FALLO: %d vulnerabilidad(es) high/critical "
               "(critical=%d, high=%d). El pipeline debe fallar."
               % (blocking, counts["critical"], counts["high"]))
        return EXIT_FAIL

    print("[GATE] OK: sin vulnerabilidades high/critical.")
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
