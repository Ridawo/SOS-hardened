# Montaje DevSecOps de SOS-hardened (PAI-4)

Pipeline de GitHub Actions que analiza la aplicación SOS con cuatro herramientas libres,
guarda los informes como artefactos, los envía solos a DefectDojo por su API y bloquea
la entrega si hay dependencias con vulnerabilidades altas o críticas.

- Workflow: [`.github/workflows/devsecops.yml`](../.github/workflows/devsecops.yml)
  (el `cicd.yaml` anterior se deja como referencia).
- Todo el pipeline corre en runners de GitHub (`runs-on: ubuntu-latest`). No hay ningún
  runner propio ni en esta máquina ni en otra. Para llegar a DefectDojo, el job
  `defectdojo` entra en un tailnet de Tailscale como nodo efímero durante el job.
- Eventos: `push` a `main`, `pull_request` y `workflow_dispatch`. Así una rama con PR abierto
  se analiza una sola vez y no dos (una por el push y otra por el PR). La publicación en GHCR
  se hace en el push a `main` (al mergear un PR) o al lanzarlo a demanda sobre una rama con
  `gh workflow run devsecops.yml --ref <rama>`; nunca en un pull request.
- Puertos: la app SOS escucha en el 8080 dentro del job `dast`. DefectDojo, que es local,
  va en el 8082 y el runner llega a él por Tailscale (ver [`defectdojo/README.md`](defectdojo/README.md)).

## Herramientas

| Tipo | Herramienta | Qué analiza | Informe |
|---|---|---|---|
| SCA | `npm audit` | dependencias npm | `npm-audit.json` |
| SAST | Semgrep 1.90.0 | código fuente | `semgrep.json` |
| IaC | Trivy 0.58.1 (modo `config`) | Dockerfile, compose | JSON |
| Contenedor | Trivy 0.58.1 (modo `image`) | imagen `sos-hardened:ci` | JSON |
| DAST | ZAP baseline 2.17.0 | la app corriendo en el 8080 | `zap.xml` |

Semgrep, Trivy y ZAP se ejecutan como contenedores Docker fijados por versión y digest.
Las acciones de GitHub (`checkout`, `setup-node`, `upload-artifact`, `download-artifact`,
`tailscale/github-action`) se fijan por el SHA de su commit, y la imagen base `node:20-slim`
del Dockerfile por su digest. Las reglas de las herramientas están en [`config/`](config/).

## Etapas y jobs

El workflow tiene 11 jobs. Cuatro arrancan a la vez, dos dependen de `build`, y después
hay un gate de aviso, la recogida de evidencias, el envío a DefectDojo, el gate bloqueante
y la entrega.
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
| `defectdojo` | 7b | entra en Tailscale, descarga `devsecops-reports` y envía los 5 informes a DefectDojo | `evidencias` (`if: always()`, solo corre si `evidencias` va bien) | - |
| `gate` | 8 | quality gate bloqueante sobre npm audit; si falla en un PR, comenta en él | `sca, sast, iac, container, dast, gate-aviso` (`if: always()`) | - |
| `release` | 9 | publica la imagen en GHCR | `build, container, dast, gate, evidencias` | - |

- `sca`, `sast` e `iac` no tienen aviso propio: su resultado se evalúa en `gate-aviso`
  (SAST e IaC) y en `gate` (SCA).
- `container` y `dast` llevan su propio aviso (ver tabla de umbrales).
- `defectdojo` tiene `continue-on-error: true` y `timeout-minutes: 10`, y ningún job lo
  espera: ni `gate` ni `release` dependen de él. Si el portátil está apagado, deja un
  `::warning::` y el pipeline sigue igual.
- `release` no se ejecuta en pull requests (sí en el push a `main` y con `workflow_dispatch`), con permisos `contents: read` y `packages: write`.
  Carga `app-image` y la sube a GHCR como `ghcr.io/<owner en minúsculas>/sos-hardened:release-<sha7>`.

## Quality gates: bloqueante y aviso

Hay dos tipos de control. Solo uno puede poner el pipeline en rojo.

### Bloqueante (Etapa 8, job `gate`)

`scripts/check_npm_gate.py npm-audit.json` suma las vulnerabilidades `high` y `critical`
de npm audit y sale con código 1 si hay alguna. El run queda en rojo y el job `release`
no se ejecuta: la imagen no se entrega. Si el fallo es en un pull request, el job
comenta en el PR (`gh pr comment`, con `pull-requests: write` solo en este job).

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
  que descarga el job `defectdojo` para enviarlo a DefectDojo.
- `app-image` es la imagen Docker comprimida. Solo la usan `container`, `dast` y `release`,
  y caduca al día.

## Envío automático a DefectDojo

Lo hace el job `defectdojo` (etapa 7b) en cada push a `main`, en cada `workflow_dispatch` y en cada `pull_request` del propio
repo (los PR de forks no tienen secretos y se saltan):

1. Comprueba que están los 4 secretos. Si falta alguno, avisa (`::warning::`) y termina sin error.
2. Entra en el tailnet con `tailscale/github-action` (cliente OAuth, etiqueta `tag:ci`).
   El nodo es efímero: desaparece al acabar el job.
3. Descarga `devsecops-reports`.
4. Comprueba con `curl` que DefectDojo responde (la clave va por stdin, no sale en el log).
   Si no responde (portátil apagado) avisa y termina sin error; los informes siguen en el
   artefacto y se puede relanzar el job con Re-run cuando esté encendido.
5. Llama 5 veces a `scripts/upload_to_defectdojo.py`, que usa la API `reimport-scan`, una por
   informe. Si alguna falla, avisa con cuántas y el job termina en error (no bloquea nada).

El engagement es `CI-CD` en `main` y `CI-CD rama <rama>` en el resto de ramas, para que
`close_old_findings` de una rama no cierre los hallazgos de `main`.

Secretos del repo: `TS_OAUTH_CLIENT_ID`, `TS_OAUTH_SECRET`, `DEFECTDOJO_URL`
(`http://<IP del portátil en el tailnet>:8082`) y `DEFECTDOJO_API_KEY`. Son secretos porque el repo
es público y no hace falta publicar la dirección interna del portátil. Cómo prepararlo está en
[`defectdojo/README.md`](defectdojo/README.md).

## Estructura de `devsecops/`

```
devsecops/
  README.md              este fichero
  config/                semgrep.yml, .zap/rules.tsv, trivy.yaml
  scripts/               upload_to_defectdojo.py, check_npm_gate.py, check_aviso.py
  defectdojo/            README.md y docker-compose.yml (puerto 8082, accesible por Tailscale)
  diagrams/              pipeline.mmd, vuln-flow.mmd (diagramas Mermaid)
```

Los diagramas del pipeline y del flujo de una vulnerabilidad están en
[`diagrams/`](diagrams/).
