#!/usr/bin/env python3
"""Sube un informe de seguridad a DefectDojo via la API import-scan.

Uso:
    python3 -I devsecops/scripts/upload_to_defectdojo.py \
        --scan-type "NPM Audit v7+ Scan" --file npm-audit.json

Pensado para correr dentro del pipeline (self-hosted runner en Kali). Usa SOLO
la libreria estandar de Python (urllib): no requiere `pip install` ni
actions/setup-python, basta el python3 del sistema.

Diseno robusto:
- Si DefectDojo no responde (esta caido, timeout, red), NO rompe el pipeline:
  imprime un warning y sale con codigo 0. Subir el informe es un paso de aviso,
  no el quality gate (ese es check_npm_gate.py).
- Si la API responde con error (credenciales, parseo del informe...), imprime
  el cuerpo de la respuesta para poder depurar y sale != 0.

Variables de entorno:
- DEFECTDOJO_URL      (por defecto http://localhost:8082)
- DEFECTDOJO_API_KEY  (obligatoria)
- GITHUB_SHA / GITHUB_RUN_ID / GITHUB_REF_NAME  (opcionales; se envian como
  commit_hash / build_id / branch_tag si existen)
"""

import argparse
import os
import sys
import urllib.error
import urllib.request
import uuid

# ---- Valores fijos del contrato PAI-4 -------------------------------------
DEFAULT_URL = "http://localhost:8082"
PRODUCT_NAME = "SOS-hardened (PAI-4)"
ENGAGEMENT_NAME = "CI-CD"
# Con auto_create_context DefectDojo exige un tipo de producto para crear el
# producto la primera vez (si no, responde 400). Este ya existe por defecto.
PRODUCT_TYPE_NAME = "Research and Development"
MINIMUM_SEVERITY = "Info"
TIMEOUT = 60  # segundos


def eprint(*args):
    print(*args, file=sys.stderr)


def build_fields(args):
    """Campos del formulario multipart (sin incluir el fichero)."""
    fields = {
        "scan_type": args.scan_type,
        "auto_create_context": "true",
        "product_name": args.product_name,
        "product_type_name": PRODUCT_TYPE_NAME,
        "engagement_name": args.engagement_name,
        "active": "true",
        "verified": "false",
        "minimum_severity": MINIMUM_SEVERITY,
    }
    # Metadatos de CI, solo si GitHub Actions los expone.
    for env_var, field in (("GITHUB_SHA", "commit_hash"),
                           ("GITHUB_RUN_ID", "build_id"),
                           ("GITHUB_REF_NAME", "branch_tag")):
        value = os.environ.get(env_var)
        if value:
            fields[field] = value
    return fields


def encode_multipart(fields, file_path):
    """Construye un cuerpo multipart/form-data con la stdlib."""
    boundary = "----pai4boundary" + uuid.uuid4().hex
    bound = boundary.encode()
    crlf = b"\r\n"
    body = bytearray()
    for name, value in fields.items():
        body += b"--" + bound + crlf
        body += ('Content-Disposition: form-data; name="%s"' % name).encode() + crlf
        body += crlf
        body += str(value).encode() + crlf
    with open(file_path, "rb") as fh:
        file_data = fh.read()
    filename = os.path.basename(file_path)
    body += b"--" + bound + crlf
    body += ('Content-Disposition: form-data; name="file"; filename="%s"'
             % filename).encode() + crlf
    body += b"Content-Type: application/octet-stream" + crlf
    body += crlf
    body += file_data + crlf
    body += b"--" + bound + b"--" + crlf
    content_type = "multipart/form-data; boundary=" + boundary
    return bytes(body), content_type


def upload(url, api_key, fields, file_path):
    """Hace el POST. Devuelve (status, cuerpo_texto).

    Lanza urllib.error.URLError (sin ser HTTPError) si no hay conexion, para
    que main() lo trate como "DefectDojo no responde" y no rompa el pipeline.
    """
    body, content_type = encode_multipart(fields, file_path)
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", "Token " + api_key)
    req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        # La API respondio con un codigo de error: devolvemos el cuerpo.
        return err.code, err.read().decode("utf-8", "replace")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Sube un informe de seguridad a DefectDojo (import-scan).")
    parser.add_argument("--scan-type", required=True,
                        help='Tipo DefectDojo, p.ej. "NPM Audit v7+ Scan".')
    parser.add_argument("--file", required=True,
                        help="Ruta del informe a subir.")
    parser.add_argument("--product-name", default=PRODUCT_NAME)
    parser.add_argument("--engagement-name", default=ENGAGEMENT_NAME)
    args = parser.parse_args(argv)

    if not os.path.isfile(args.file):
        eprint("[ERROR] No existe el fichero de informe: %s" % args.file)
        return 2

    api_key = os.environ.get("DEFECTDOJO_API_KEY")
    if not api_key:
        eprint("[ERROR] Falta la variable de entorno DEFECTDOJO_API_KEY "
               "(obligatoria).")
        return 2

    base_url = os.environ.get("DEFECTDOJO_URL", DEFAULT_URL).rstrip("/")
    url = base_url + "/api/v2/import-scan/"
    fields = build_fields(args)

    print("[INFO] Subiendo '%s' como '%s' a %s"
          % (args.file, args.scan_type, url))

    try:
        status, text = upload(url, api_key, fields, args.file)
    except urllib.error.URLError as err:
        # Sin conexion / DNS / timeout: no rompemos el pipeline.
        eprint("[WARN] DefectDojo no responde (%s). Se omite la subida y el "
               "pipeline continua." % err.reason)
        return 0
    except OSError as err:
        # socket.timeout y similares heredan de OSError.
        eprint("[WARN] DefectDojo no responde (%s). Se omite la subida y el "
               "pipeline continua." % err)
        return 0

    body_preview = text if len(text) <= 4000 else text[:4000] + "...(truncado)"
    if 200 <= status < 300:
        print("[OK] Informe subido. HTTP %s" % status)
        print(body_preview)
        return 0

    eprint("[ERROR] La API devolvio HTTP %s" % status)
    eprint(body_preview)
    return 1


if __name__ == "__main__":
    sys.exit(main())
