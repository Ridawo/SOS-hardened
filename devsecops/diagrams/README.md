# Diagramas del pipeline

Los dos diagramas que pide el enunciado (objetivo 1), escritos en Mermaid para que se
puedan versionar junto al código.

| Fichero | Contenido |
|---|---|
| `pipeline.mmd` | Objetivo 1.a: etapas en orden, herramienta de cada etapa, informe que genera, cómo llega a DefectDojo y posición de cada quality gate (aviso o bloqueante y umbral). |
| `vuln-flow.mmd` | Objetivo 1.b: qué pasa desde que una herramienta detecta una vulnerabilidad hasta que se resuelve (decisiones, si el pipeline continúa o se detiene, a quién se avisa y cómo se trata en DefectDojo). |

En `pipeline.mmd` el amarillo es un gate en modo aviso (`continue-on-error`) y el rojo es
el gate bloqueante (`check_npm_gate.py`).

Los diagramas tienen que coincidir con `.github/workflows/devsecops.yml`. Si cambia el
workflow (una etapa, una herramienta, un umbral), hay que actualizar aquí también.

## Renderizar a PNG o SVG

### Opción 1: mermaid-cli (línea de comandos)

```bash
npm install -g @mermaid-js/mermaid-cli
cd devsecops/diagrams
mmdc -i pipeline.mmd  -o pipeline.png  -s 3 -b white
mmdc -i vuln-flow.mmd -o vuln-flow.png -s 3 -b white
# SVG (vectorial, mejor para el PDF del informe)
mmdc -i pipeline.mmd  -o pipeline.svg
mmdc -i vuln-flow.mmd -o vuln-flow.svg
```

`-s 3` multiplica la escala para que el texto se lea bien al incrustarlo en el informe.
Si mmdc no encuentra Chromium o falla por el sandbox, crea un `puppeteer.json` con
`{"executablePath": "/usr/bin/chromium", "args": ["--no-sandbox"]}` y añade `-p puppeteer.json`.

### Opción 2: Docker, sin instalar nada

```bash
docker run --rm -u "$(id -u):$(id -g)" -v "$PWD":/data minlag/mermaid-cli \
  -i /data/pipeline.mmd -o /data/pipeline.png -s 3 -b white
```

### Opción 3: web

Pegar el contenido del `.mmd` en <https://mermaid.live> y descargar PNG o SVG.

## Notas

- Las líneas que empiezan por `%%` son comentarios de Mermaid.
- Las etiquetas no deben empezar por `1. ` ni por `- `: Mermaid las toma como lista de
  Markdown y pinta "Unsupported markdown". Por eso las etapas se llaman `Etapa 1: ...`.
- Sin tildes en los diagramas para evitar problemas de fuentes al renderizar en algunos
  entornos.
