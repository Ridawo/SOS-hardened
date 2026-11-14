# Montaje DevSecOps de SOS-hardened (PAI-4)

Pipeline de GitHub Actions que analiza la aplicacion SOS con cuatro herramientas libres,
sube los resultados a DefectDojo y bloquea la ejecucion si hay dependencias con
vulnerabilidades altas o criticas.

- Workflow: [`.github/workflows/devsecops.yml`](../.github/workflows/devsecops.yml)
  (el `cicd.yaml` anterior se deja como referencia).
- Se ejecuta en un runner self-hosted (`runs-on: [self-hosted, linux]`) con los eventos
  `push` y `pull_request`.
- Los puertos: app SOS en 8080 y DefectDojo en 8082.

## Herramientas y etapa

| Tipo | Herramienta | Que analiza | Etapa | Informe | Tipo en DefectDojo |
|---|---|---|---|---|---|
| SCA | `npm audit` | dependencias npm | commit | `npm-audit.json` | NPM Audit v7+ Scan |
| SAST | Semgrep 1.90.0 | codigo fuente | commit | `semgrep.json` | Semgrep JSON Report |
| IaC y contenedor | Trivy 0.58.1 | Dockerfile, compose e imagen `sos-hardened:ci` | build | JSON | Trivy Scan |
| DAST | ZAP baseline 2.15.0 | la app corriendo en el puerto 8080 | despliegue de prueba | `zap.xml` | ZAP Scan |

Semgrep, Trivy y ZAP se ejecutan como contenedores Docker con la version fijada. Sus reglas
y exclusiones estan en [`config/`](config/).

## Orden del pipeline

1. Checkout, Node 20, instalacion de dependencias del backend y del frontend.
2. SCA (`npm audit --json`) y subida a DefectDojo.
3. SAST (Semgrep) y subida.
4. Build del frontend y de la imagen Docker.
5. Trivy sobre la configuracion (Dockerfile, compose) y sobre la imagen; subida.
6. DAST: se levanta la app en un contenedor, ZAP baseline la ataca en el 8080, se para el
   contenedor y se sube el informe.
7. Se guardan los informes como artefactos del run.
8. **Quality gate** (ultimo paso).

## Quality gate

El gate bloqueante es el SCA: `scripts/check_npm_gate.py npm-audit.json` suma las
vulnerabilidades `high` y `critical` de `npm-audit.json` y sale con codigo 1 si hay alguna,
con lo que el run queda en rojo.

Se evalua **al final** y no justo despues del SCA para que Semgrep, Trivy y ZAP tambien se
ejecuten y suban su informe en cada run. Si el gate cortara pronto, el DAST nunca se
ejecutaria mientras haya dependencias vulnerables. El resto de herramientas van en modo aviso
(`continue-on-error: true`): generan informe, pero no tumban el pipeline.

Las dependencias de SOS siguen vulnerables a proposito (35 segun `npm audit`: 5 criticas,
19 altas, 11 moderadas), asi que el gate falla en este repo mientras no se actualicen. Es el
comportamiento esperado de la practica.

## Flujo de resultados a DefectDojo

```
herramienta -> informe (json/xml) -> scripts/upload_to_defectdojo.py -> DefectDojo
                                      POST /api/v2/import-scan/
```

- El script usa `DEFECTDOJO_URL` (por defecto `http://localhost:8082`) y `DEFECTDOJO_API_KEY`
  (secreto de GitHub, nunca en el repo).
- Con `auto_create_context=true` se crean solos el producto `SOS-hardened (PAI-4)` y el
  engagement `CI-CD`; cada subida lleva el commit, el numero de run y la rama.
- Si DefectDojo no responde, el script avisa y sale con 0: no rompe el pipeline.

## Que hay que tener encendido

El runner y DefectDojo tienen que estar encendidos mientras corre el pipeline. Pasos en:

- [`runner/README.md`](runner/README.md): registrar y ejecutar el self-hosted runner, y sus
  riesgos de seguridad en un repo publico.
- [`defectdojo/README.md`](defectdojo/README.md): levantar DefectDojo en el 8082, sacar la
  contrasena de admin y crear la API key.

## Estructura de `devsecops/`

```
devsecops/
  README.md              este fichero
  config/                semgrep.yml, .zap/rules.tsv, trivy.yaml
  scripts/               upload_to_defectdojo.py, check_npm_gate.py
  defectdojo/            README.md y docker-compose.yml (puerto 8082)
  runner/                README.md del self-hosted runner
  diagrams/              pipeline.mmd, vuln-flow.mmd (diagramas Mermaid)
```

Los diagramas del pipeline y del flujo de una vulnerabilidad estan en
[`diagrams/`](diagrams/).
