#!/usr/bin/env bash
# Importa a DefectDojo (local) los informes de un run de DevSecOps en GitHub.
# Uso (desde la raiz del repo):
#   DEFECTDOJO_API_KEY=... devsecops/scripts/importar_defectdojo.sh <run_id>
set -euo pipefail

RUN_ID="${1:-}"
REPO="${GH_REPO:-Ridawo/SOS-hardened}"   # el gh de este clon apunta al upstream
DEFECTDOJO_URL="${DEFECTDOJO_URL:-http://localhost:8082}"
UPLOADER="devsecops/scripts/upload_to_defectdojo.py"

if [[ ! "$RUN_ID" =~ ^[0-9]+$ ]]; then
    echo "Uso: $0 <run_id numerico>" >&2
    exit 2
fi

# Pedir la API key sin eco si no viene en el entorno. Nunca se imprime.
if [[ -z "${DEFECTDOJO_API_KEY:-}" ]]; then
    read -rsp "DEFECTDOJO_API_KEY: " DEFECTDOJO_API_KEY
    echo
fi
export DEFECTDOJO_API_KEY DEFECTDOJO_URL

# upload_to_defectdojo.py sale con 0 si DefectDojo no responde (en CI no debia romper
# nada), asi que aqui se comprueba antes que DefectDojo esta levantado y acepta la
# clave. La cabecera va por stdin para que la clave no aparezca en la lista de procesos.
if ! printf 'Authorization: Token %s\n' "$DEFECTDOJO_API_KEY" |
        curl -sf -o /dev/null -H @- "$DEFECTDOJO_URL/api/v2/users/?limit=1"; then
    echo "DefectDojo no responde en $DEFECTDOJO_URL o la API key no es valida." >&2
    exit 2
fi

# Datos del run analizado. Los lee upload_to_defectdojo.py como DD_*.
IFS=$'\t' read -r workflow DD_COMMIT_HASH DD_BRANCH_TAG < <(gh run view "$RUN_ID" \
    --repo "$REPO" --json workflowName,headSha,headBranch \
    --jq '[.workflowName, .headSha, .headBranch] | @tsv')
if [[ "$workflow" != "DevSecOps" ]]; then
    echo "El run $RUN_ID es del workflow '$workflow', no de 'DevSecOps'." >&2
    exit 2
fi
DD_BUILD_ID="$RUN_ID"
export DD_COMMIT_HASH DD_BUILD_ID DD_BRANCH_TAG

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "Descargando devsecops-reports del run $RUN_ID ($REPO)..."
gh run download "$RUN_ID" --repo "$REPO" -n devsecops-reports -D "$tmp"

# Pares scan-type / fichero / test-title (el test-title fija el test en DefectDojo).
subidos=0
total=0
fallidos=0
while IFS='|' read -r scan_type fichero titulo; do
    total=$((total + 1))
    ruta="$tmp/$fichero"
    if [[ ! -f "$ruta" ]]; then
        echo "[ERROR] Falta $fichero en el artefacto." >&2
        fallidos=$((fallidos + 1))
        continue
    fi
    echo "Subiendo $fichero ($titulo)..."
    if python3 -I "$UPLOADER" --scan-type "$scan_type" --file "$ruta" --test-title "$titulo"; then
        subidos=$((subidos + 1))
    else
        echo "[ERROR] Fallo al subir $fichero." >&2
        fallidos=$((fallidos + 1))
    fi
done <<'LISTA'
NPM Audit v7+ Scan|npm-audit.json|npm audit (SCA)
Semgrep JSON Report|semgrep.json|Semgrep (SAST)
Trivy Scan|trivy-config.json|Trivy config (IaC)
Trivy Scan|trivy-image.json|Trivy image (contenedor)
ZAP Scan|zap.xml|ZAP baseline (DAST)
LISTA

echo "Resumen: $subidos de $total informes subidos, $fallidos con error."
if (( fallidos > 0 )); then
    exit 1
fi
