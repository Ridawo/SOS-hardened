# Montaje DevSecOps de SOS-hardened (PAI-4)

Pipeline de GitHub Actions que analiza la aplicación SOS con cuatro herramientas libres,
guarda los informes como artefactos y bloquea la entrega si hay dependencias con
vulnerabilidades altas o críticas.

- Workflow: [`.github/workflows/devsecops.yml`](../.github/workflows/devsecops.yml)
  (el `cicd.yaml` anterior se deja como referencia).
- Todo el pipeline corre en runners de GitHub (`runs-on: ubuntu-latest`). No hay ningún
  runner propio ni en esta máquina ni en otra.
- Eventos: `push` y `pull_request`. La publicación en GHCR solo se hace en `push`.
- Puertos: la app SOS escucha en el 8080 dentro del job `dast`. DefectDojo, que es local,
  va en el 8082 (ver [`defectdojo/README.md`](defectdojo/README.md)).

## Herramientas

| Tipo | Herramienta | Qué analiza | Informe |
|---|---|---|---|
| SCA | `npm audit` | dependencias npm | `npm-audit.json` |
| SAST | Semgrep 1.90.0 | código fuente | `semgrep.json` |
| IaC | Trivy 0.58.1 (modo `config`) | Dockerfile, compose | JSON |
| Contenedor | Trivy 0.58.1 (modo `image`) | imagen `sos-hardened:ci` | JSON |
| DAST | ZAP baseline 2.17.0 | la app corriendo en el 8080 | `zap.xml` |

Semgrep, Trivy y ZAP se ejecutan como contenedores Docker fijados por versión y digest.
Las acciones de GitHub (`checkout`, `setup-node`, `upload-artifact`, `download-artifact`)
se fijan por el SHA de su commit. Las reglas de las herramientas están en [`config/`](config/).

## Etapas y jobs

El workflow tiene 10 jobs. Cuatro arrancan a la vez, dos dependen de `build`, y después
hay un gate de aviso, la recogida de evidencias, el gate bloqueante y la entrega.
Diagrama en [`diagrams/pipeline.mmd`](diagrams/pipeline.mmd).

| Job | Etapa | Qué hace | `needs` | Artefacto |
|---|---|---|---|---|
| `sca` | 2 | `npm audit` sobre las dependencias | - | `report-sca` |
| `sast` | 3 | Semgrep sobre el código | - | `report-sast` |
| `iac` | 5a | Trivy config sobre Dockerfile y compose | - | `report-iac` |
| `build` | 4 | `docker build -t sos-hardened:ci .` y guarda la imagen comprimida | - | `app-image` (1 día) |
| `container` | 5b | Trivy image sobre `sos-hardened:ci` | `build` | `report-container` |
| `dast` | 6 | carga la imagen, levanta la app en el 8080 con secretos aleatorios y pasa ZAP baseline | `build` | `report-dast` |
| `gate-aviso` | 5c | quality gate de aviso sobre SAST e IaC | `sast, iac` (`if: always()`) | - |
| `evidencias` | 7 | junta los `report-*` en un único artefacto | `sca, sast, iac, container, dast` (`if: always()`) | `devsecops-reports` (30 días) |
| `gate` | 8 | quality gate bloqueante sobre npm audit | `sca, sast, iac, container, dast, gate-aviso` (`if: always()`) | - |
| `release` | 9 | publica la imagen en GHCR | `build, container, dast, gate, evidencias` | - |

- `sca`, `sast` e `iac` no tienen aviso propio: su resultado se evalúa en `gate-aviso`
  (SAST e IaC) y en `gate` (SCA).
- `container` y `dast` llevan su propio aviso (ver tabla de umbrales).
- `release` solo se ejecuta en `push`, con permisos `contents: read` y `packages: write`.
  Carga `app-image` y la sube a GHCR como `ghcr.io/<owner en minúsculas>/sos-hardened:release-<sha7>`.

## Quality gates: bloqueante y aviso

Hay dos tipos de control. Solo uno puede poner el pipeline en rojo.

### Bloqueante (Etapa 8, job `gate`)

`scripts/check_npm_gate.py npm-audit.json` suma las vulnerabilidades `high` y `critical`
de npm audit y sale con código 1 si hay alguna. El run queda en rojo y el job `release`
no se ejecuta: la imagen no se entrega.

El gate espera a **todas** las herramientas (`needs` de los cinco jobs de análisis y de
`gate-aviso`) y no va justo después del SCA. Así Semgrep, Trivy y ZAP también se ejecutan
y suben su informe en cada run, aunque las dependencias ya estén rotas.

### Aviso (Etapa 5c y avisos de `container` y `dast`)

Los controles de aviso tienen `continue-on-error: true` y nunca tumban el pipeline. Si se
supera el umbral, el script `scripts/check_aviso.py` deja una anotación `::warning::` que
se ve en el resumen del run y en el pull request.

| Control | Job | Umbral de aviso |
|---|---|---|
| Semgrep | `gate-aviso` | más de 0 resultados con severidad WARNING o ERROR |
| Trivy config | `gate-aviso` | más de 0 errores de configuración HIGH o CRITICAL |
| Trivy image | `container` | más de 0 vulnerabilidades CRITICAL |
| ZAP baseline | `dast` | más de 0 alertas de riesgo Medium o High |

### Estado actual

Las dependencias de SOS siguen vulnerables a propósito (35 según `npm audit`: 5 críticas,
19 altas y 11 moderadas). Por eso el gate falla en este repo mientras no se actualicen.
Es el comportamiento esperado para la práctica.

## Artefactos

- Cada job de análisis sube su informe como `report-*`.
- `evidencias` junta todos en `devsecops-reports`, que se guarda 30 días. Es el artefacto
  que se descarga para importar en DefectDojo.
- `app-image` es la imagen Docker comprimida. Solo la usan `container`, `dast` y `release`,
  y caduca al día.

## Importación manual a DefectDojo

El pipeline no sube nada a DefectDojo y no depende de ningún equipo local para terminar.
La importación se hace a mano desde el portátil, después de cada run:

```bash
devsecops/scripts/importar_defectdojo.sh <run_id>
```

El script:

1. Descarga el artefacto `devsecops-reports` del run con `gh run download`.
2. Llama 5 veces a `scripts/upload_to_defectdojo.py`, que usa la API `reimport-scan`
   de DefectDojo, una vez por cada informe.

Requisitos: `gh` autenticado en el repo y DefectDojo levantado en `http://localhost:8082`.
La clave de la API se pasa en la variable `DEFECTDOJO_API_KEY` o el script la pide sin eco.
Los pasos para levantar DefectDojo y crear la clave están en
[`defectdojo/README.md`](defectdojo/README.md).

Para saber el `<run_id>`: `gh run list --repo Ridawo/SOS-hardened --workflow devsecops.yml`.

## Estructura de `devsecops/`

```
devsecops/
  README.md              este fichero
  config/                semgrep.yml, .zap/rules.tsv, trivy.yaml
  scripts/               upload_to_defectdojo.py, check_npm_gate.py, check_aviso.py,
                         importar_defectdojo.sh
  defectdojo/            README.md y docker-compose.yml (puerto 8082)
  diagrams/              pipeline.mmd, vuln-flow.mmd (diagramas Mermaid)
```

Los diagramas del pipeline y del flujo de una vulnerabilidad están en
[`diagrams/`](diagrams/).
