#!/usr/bin/env python3
"""Umbral de las etapas en modo AVISO (Semgrep, Trivy config, Trivy image, ZAP).

Uso:
    python3 devsecops/scripts/check_aviso.py --tool semgrep --file semgrep.json

Cuenta los hallazgos del informe que superan el umbral de la herramienta y, si
hay alguno, deja una anotacion ::warning:: en GitHub Actions (se ve en el
resumen del run y en el pull request) y una linea en el resumen del job. Nunca
hace fallar el job: es un gate de aviso. El unico gate bloqueante es
check_npm_gate.py.

Umbrales (aviso si el recuento es mayor que 0):
- semgrep       resultados con severidad WARNING o ERROR
- trivy-config  errores de configuracion HIGH o CRITICAL
- trivy-image   vulnerabilidades CRITICAL
- zap           alertas de riesgo Medium o High

Solo stdlib.
"""

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET


def count_semgrep(path):
    with open(path, encoding="utf-8") as fh:
        results = json.load(fh).get("results", [])
    return sum(1 for r in results
               if r.get("extra", {}).get("severity") in ("WARNING", "ERROR"))


def _trivy_items(path, key):
    with open(path, encoding="utf-8") as fh:
        report = json.load(fh)
    for result in report.get("Results") or []:
        yield from result.get(key) or []


def count_trivy_config(path):
    return sum(1 for m in _trivy_items(path, "Misconfigurations")
               if m.get("Severity") in ("HIGH", "CRITICAL"))


def count_trivy_image(path):
    return sum(1 for v in _trivy_items(path, "Vulnerabilities")
               if v.get("Severity") == "CRITICAL")


def count_zap(path):
    root = ET.parse(path).getroot()
    return sum(1 for alert in root.iter("alertitem")
               if int(alert.findtext("riskcode", "0")) >= 2)


TOOLS = {
    "semgrep": ("Semgrep", "resultados con severidad WARNING o ERROR", count_semgrep),
    "trivy-config": ("Trivy config", "errores de configuracion HIGH o CRITICAL", count_trivy_config),
    "trivy-image": ("Trivy image", "vulnerabilidades CRITICAL", count_trivy_image),
    "zap": ("ZAP", "alertas de riesgo Medium o High", count_zap),
}


def escape(text):
    """Escapa %, CR y LF para que el texto no pueda cerrar la anotacion ni
    inyectar otro comando de GitHub Actions (formato de workflow commands)."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def summary(line):
    """Anade una linea al resumen del job si GitHub Actions lo expone."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tool", required=True, choices=sorted(TOOLS))
    parser.add_argument("--file", required=True)
    args = parser.parse_args(argv)

    name, what, counter = TOOLS[args.tool]
    try:
        count = counter(args.file)
    except (OSError, ValueError, ET.ParseError) as err:
        # Sin informe no se puede evaluar: se avisa, pero no se bloquea.
        print("::warning title=%s (aviso)::No se pudo leer el informe %s: %s"
              % (name, escape(args.file), escape(err)))
        summary("- %s: informe no disponible" % name)
        return 0

    if count > 0:
        print("::warning title=%s (aviso)::%d %s (umbral: mas de 0). "
              "El pipeline continua; revisar en DefectDojo." % (name, count, what))
        summary("- %s: **AVISO**, %d %s" % (name, count, what))
    else:
        print("[AVISO] %s: 0 %s." % (name, what))
        summary("- %s: 0 %s" % (name, what))
    return 0


if __name__ == "__main__":
    sys.exit(main())
