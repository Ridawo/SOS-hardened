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
- Node 20: lo instala `actions/setup-node` en el propio workflow. Python 3 hay que tenerlo en
  el sistema del runner: los scripts del pipeline usan el `python3` de la maquina (solo
  libreria estandar, sin `pip install`). No se usa `actions/setup-python`, que falla en Kali.
- Para que el equipo no se suspenda mientras corre un pipeline, arrancar el runner con
  `systemd-inhibit --what=sleep:idle:handle-lid-switch ./run.sh`. Si el portatil se suspende, el
  trabajo en curso queda a medias y, al despertar, el runner puede seguir ejecutandolo.
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

## 5. Runners extra para los jobs en paralelo

El workflow tiene jobs que pueden correr a la vez (`sca`, `sast`, `iac` y `build`, y luego
`container` y `dast`: hasta 4 a la vez). Un runner ejecuta **un solo job a la vez**: con un unico runner los
jobs paralelos se encolan uno detras de otro y no se gana tiempo. Por eso se registran tres
instancias mas en la misma maquina, cada una en su propio directorio (no se pueden compartir,
cada una guarda sus credenciales y su carpeta `_work`).

Sacar un token nuevo en Settings -> Actions -> Runners -> New self-hosted runner por cada
instancia (o reutilizar uno que no haya caducado) y usar los comandos que muestre GitHub:

```bash
# Instancia 2
mkdir -p ~/actions-runner-2 && cd ~/actions-runner-2
curl -o actions-runner-linux-x64-2.338.2.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.338.2/actions-runner-linux-x64-2.338.2.tar.gz
tar xzf ./actions-runner-linux-x64-2.338.2.tar.gz
./config.sh --url https://github.com/Ridawo/SOS-hardened --token <TOKEN_DE_REGISTRO> \
  --name kali-ridao-2 --labels self-hosted,linux --unattended

# Instancia 3
mkdir -p ~/actions-runner-3 && cd ~/actions-runner-3
# (misma descarga y tar)
./config.sh --url https://github.com/Ridawo/SOS-hardened --token <TOKEN_DE_REGISTRO> \
  --name kali-ridao-3 --labels self-hosted,linux --unattended

# Instancia 4
mkdir -p ~/actions-runner-4 && cd ~/actions-runner-4
# (misma descarga y tar)
./config.sh --url https://github.com/Ridawo/SOS-hardened --token <TOKEN_DE_REGISTRO> \
  --name kali-ridao-4 --labels self-hosted,linux --unattended
```

El label es el mismo que el del primer runner (`self-hosted,linux`), asi que GitHub reparte
los jobs entre los cuatro. Lanzarlos cada uno en su terminal, evitando la suspension:

```bash
cd ~/actions-runner   && systemd-inhibit --what=sleep:idle:handle-lid-switch ./run.sh
cd ~/actions-runner-2 && systemd-inhibit --what=sleep:idle:handle-lid-switch ./run.sh
cd ~/actions-runner-3 && systemd-inhibit --what=sleep:idle:handle-lid-switch ./run.sh
cd ~/actions-runner-4 && systemd-inhibit --what=sleep:idle:handle-lid-switch ./run.sh
```

Los cuatro aparecen como **Idle** en Settings -> Actions -> Runners. Para quitarlos:
`./config.sh remove --token <TOKEN>` dentro de cada directorio.

Recursos: la maquina tiene 15 GB de RAM utiles y 8 hilos. Cuatro runners con jobs que lanzan
contenedores (Semgrep, Trivy, ZAP, el build de la imagen) a la vez pueden apretar la memoria;
si se queda corta, dejar solo dos o tres. Los cuatro comparten el mismo daemon Docker, el puerto 8080
y la imagen `sos-hardened:ci`, y el workflow ya impide dos ejecuciones simultaneas con
`concurrency`.

## Que tiene que estar encendido

Durante cada ejecucion del pipeline tienen que estar a la vez:

1. Los runners (`./run.sh` o el servicio): al menos uno, mejor los cuatro.
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
  workflows para forks). Revisar el codigo del PR antes de aprobar su ejecucion. En este
  repo esta aplicado desde el 18-nov-2026 (`approval_policy: all_external_contributors`;
  se comprueba con `gh api repos/Ridawo/SOS-hardened/actions/permissions/fork-pr-contributor-approval`).
- El workflow dispara con `push` y `pull_request`. Evitar `pull_request_target` y no pasar
  secretos a codigo de forks (GitHub no da los secretos a los PRs de forks con
  `pull_request`, pero el codigo del PR si se ejecutaria en este equipo).
- Dejar los permisos del `GITHUB_TOKEN` en solo lectura (`permissions: contents: read`).
- Mantener el runner solo encendido mientras se necesita, y no ejecutarlo con root.
- Si el repo deja de usarse, quitar el runner: Settings -> Actions -> Runners -> Remove, y
  en la maquina `./config.sh remove --token <TOKEN>`.
