# Self-hosted runner de GitHub Actions

Todos los jobs del workflow `.github/workflows/devsecops.yml` usan
`runs-on: [self-hosted, linux]`, asi que hace falta un runner registrado en el repo
`Ridawo/SOS-hardened` y encendido durante la ejecucion. Se instala en esta misma maquina
(Kali Linux), por eso el pipeline puede hablar con DefectDojo en `http://localhost:8082`
y con Docker del host.

## Requisitos

- Docker instalado y usable por el usuario que ejecuta el runner (`docker ps` sin sudo; si no,
  `sudo usermod -aG docker $USER` y volver a abrir sesion).
- `git` y `curl`.
- Node 20 y Python 3.12: los instalan `actions/setup-node` y `actions/setup-python` en el propio
  workflow. Si `setup-python` falla en Kali (no es Ubuntu), instalar Python 3 en el sistema y
  quitar o ajustar ese paso del workflow.
- Ver `docker compose version` y que DefectDojo este levantado
  (ver [../defectdojo/README.md](../defectdojo/README.md)).
- Las imagenes de Semgrep, ZAP y Trivy se descargan solas la primera vez (algo de GB).

## 1. Sacar el token de registro

1. Ir a <https://github.com/Ridawo/SOS-hardened>.
2. Settings -> Actions -> Runners -> **New self-hosted runner**.
3. Elegir **Linux** y arquitectura **x64**.
4. GitHub muestra los comandos con un token de registro (`--token ...`). Ese token caduca
   en una hora y es de un solo uso para registrar; no se guarda en el repo.

Los comandos que da GitHub son los que valen, porque la version del runner cambia. Al
escribir esto la ultima era la 2.338.2; si GitHub muestra otra, usar la suya.

## 2. Descargar y configurar

```bash
mkdir -p ~/actions-runner && cd ~/actions-runner

# Descarga (usar la version/URL que muestre GitHub)
curl -o actions-runner-linux-x64-2.338.2.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.338.2/actions-runner-linux-x64-2.338.2.tar.gz
tar xzf ./actions-runner-linux-x64-2.338.2.tar.gz

# Registro
./config.sh --url https://github.com/Ridawo/SOS-hardened --token <TOKEN_DE_REGISTRO> \
  --name kali-ridao --labels self-hosted,linux --unattended
```

Notas:

- `self-hosted`, `linux` y `X64` se anaden solos como etiquetas; `--labels` las deja
  explicitas. El workflow solo exige `self-hosted` y `linux`.
- Sin `--unattended`, `config.sh` pregunta nombre, grupo y etiquetas (Enter para los valores
  por defecto).
- El directorio `~/actions-runner` esta fuera del repo a proposito: contiene credenciales
  del runner y no debe subirse nunca.

## 3. Ejecutarlo

Opcion A, en primer plano (la mas sencilla para la practica; se para con Ctrl+C):

```bash
cd ~/actions-runner
./run.sh
```

Debe salir `Listening for Jobs`. En GitHub, Settings -> Actions -> Runners, el runner
aparece como **Idle**.

Opcion B, como servicio para que arranque con el sistema:

```bash
cd ~/actions-runner
sudo ./svc.sh install
sudo ./svc.sh start
sudo ./svc.sh status
```

(Parar con `sudo ./svc.sh stop`; quitar con `sudo ./svc.sh uninstall`.)

## 4. Probarlo

Con el runner en `Idle` y DefectDojo arriba, hacer un push a la rama (el workflow se dispara
con `push` y `pull_request`) y mirar la pestana Actions. El job debe pasar de `Queued` a
`In progress` en unos segundos. Si se queda en `Queued` mucho rato, el runner esta
apagado o las etiquetas no coinciden.

## Que tiene que estar encendido

Durante cada ejecucion del pipeline tienen que estar a la vez:

1. El runner (`./run.sh` o el servicio).
2. DefectDojo en el puerto 8082 (`docker compose ps` en `devsecops/defectdojo`).
3. Docker funcionando, y el puerto 8080 libre (el DAST levanta la app ahi).

Si DefectDojo esta apagado, el pipeline no se rompe por eso: la subida avisa y sigue, pero
los resultados no llegan a DefectDojo. Si el runner esta apagado, el pipeline no arranca.

## Seguridad

Un self-hosted runner ejecuta en esta maquina el codigo del workflow, con acceso a Docker (que
equivale casi a root) y a la red local. GitHub desaconseja usarlos en repos publicos, y este
repo es publico. Precauciones:

- Ejecutar solo workflows de confianza, es decir, los de ramas del propio repo.
- **No dejar que los PRs de forks externos se ejecuten solos.** En Settings -> Actions ->
  General -> "Fork pull request workflows from outside collaborators", elegir
  **Require approval for all outside collaborators** (o, mas estricto, desactivar los
  workflows para forks). Revisar el codigo del PR antes de aprobar su ejecucion.
- El workflow dispara con `push` y `pull_request`. Evitar `pull_request_target` y no pasar
  secretos a codigo de forks (GitHub no da los secretos a los PRs de forks con
  `pull_request`, pero el codigo del PR si se ejecutaria en este equipo).
- Dejar los permisos del `GITHUB_TOKEN` en solo lectura (`permissions: contents: read`).
- Mantener el runner solo encendido mientras se necesita, y no ejecutarlo con root.
- Si el repo deja de usarse, quitar el runner: Settings -> Actions -> Runners -> Remove, y
  en la maquina `./config.sh remove --token <TOKEN>`.
