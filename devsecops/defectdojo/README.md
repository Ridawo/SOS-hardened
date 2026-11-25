# DefectDojo en local (puerto 8082)

DefectDojo centraliza los informes de las herramientas del pipeline (npm audit, Semgrep,
Trivy y ZAP). Se ejecuta en local con Docker. Los informes llegan solos desde el pipeline:
el job `defectdojo` del workflow los envía por la API a través de Tailscale (ver
"Conectar el pipeline con Tailscale" más abajo).

Puertos: la app SOS usa el **8080**, el 8081 está ocupado por otro contenedor (`sie_bonita`)
y DefectDojo va en el **8082**. DefectDojo usa el 8080 por defecto, por eso hay que cambiarlo.

## Requisitos

- Docker con Compose v2 (`docker compose version`). Aquí hay Compose 2.40.
- Git.
- Unos 4 GB de RAM libres para el stack (postgres, valkey, uwsgi, celery, nginx).
- Los puertos 8082 y 8444 libres: `ss -ltn | grep -E ':8082|:8444'` no debe devolver nada.

## Cómo funciona este directorio

La forma oficial de instalarlo es clonar `django-DefectDojo` y usar su `docker-compose.yml`.
El fichero [`docker-compose.yml`](docker-compose.yml) de esta carpeta no define servicios:
usa `include` para cargar el compose oficial y le pasa `defectdojo.env` con los puertos.
Las imágenes son las oficiales (`registry.defectdojo.com/defectdojo/...`).

Por defecto las imágenes se descargan desde `registry.defectdojo.com`. Si se prefiere Docker Hub,
exportar `DD_IMAGE_REGISTRY=docker.io` antes de levantar.

## Levantarlo

Desde `devsecops/defectdojo/`:

```bash
# 1. Clonar el repo oficial dentro de esta carpeta
git clone --depth 1 https://github.com/DefectDojo/django-DefectDojo.git

# 2. Que git ignore el clon y el fichero de entorno (no deben ir al repo de la práctica)
echo 'devsecops/defectdojo/django-DefectDojo/' >> ../../.git/info/exclude
echo 'devsecops/defectdojo/defectdojo.env'     >> ../../.git/info/exclude

# 3. Puertos: 8082 para HTTP y 8444 para HTTPS
printf 'DD_PORT=8082\nDD_TLS_PORT=8444\n' > defectdojo.env

# 4. Arrancar en segundo plano
docker compose up -d
```

La primera vez tarda unos minutos (descarga de imágenes y migraciones de la base de datos).
Para ver cómo va:

```bash
docker compose ps
docker compose logs -f initializer   # termina cuando acaba la inicialización
```

Cuando el servicio `initializer` ha terminado, la interfaz está en <http://localhost:8082>.

### Parar y borrar

```bash
docker compose stop        # para y conserva los datos
docker compose down        # borra los contenedores; los datos siguen en los volúmenes
docker compose down -v     # borra también los volúmenes (se pierde todo)
```

## Contraseña inicial de admin

El usuario es `admin`. La contraseña se genera al inicializar y sale en los logs del
contenedor `initializer`:

```bash
docker compose logs initializer | grep "Admin password:"
```

Guardarla, porque solo aparece ahí. Si se pierde, se puede poner una nueva:

```bash
docker compose exec -it uwsgi ./manage.py changepassword admin
```

## Crear la API key

El pipeline usa la API v2 con una clave de este usuario.

1. Entrar en <http://localhost:8082> con `admin`.
2. Arriba a la derecha, el icono de usuario, **API v2 Key**
   (también se llega en <http://localhost:8082/api/v2/key/>).
3. Copiar la clave (cadena hexadecimal de 40 caracteres).

Comprobar que funciona, sin pegar la clave en el historial del terminal:

```bash
read -rs DEFECTDOJO_API_KEY && export DEFECTDOJO_API_KEY
curl -s -H "Authorization: Token $DEFECTDOJO_API_KEY" http://localhost:8082/api/v2/users/ | head -c 200
```

### Dónde se guarda la clave

La API key es un secreto. **Nunca va en el repositorio**, ni en el workflow ni en un
fichero `.env` que se suba. El pipeline la lee del secreto de GitHub `DEFECTDOJO_API_KEY`
(ver el paso 5 de la sección siguiente).

## Conectar el pipeline con Tailscale

El pipeline corre en runners de GitHub y DefectDojo está en este portátil, que no es
accesible desde internet. Para unirlos se usa Tailscale: el runner entra en un tailnet
privado como nodo efímero solo mientras dura el job, y la ACL del tailnet solo le deja llegar
al 8082 del portátil. No se abre nada a internet.

1. Instalar Tailscale en el portátil y conectarlo al tailnet:

   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up
   ```

   (Si se prefiere, se puede instalar desde el repositorio apt que indica
   <https://tailscale.com/download/linux>.) `tailscale up` abre un enlace para iniciar sesión.
   Luego `tailscale status` muestra el nombre de la máquina; el nombre completo
   (`<maquina>.<tailnet>.ts.net`) sale con `tailscale status --json | grep DNSName`.

2. Comprobar que DefectDojo se ve por el tailnet. No hace falta `tailscale serve`: Docker
   publica el 8082 en todas las interfaces, también en la de Tailscale (`tailscale0`), y lo que
   decide quién llega es la ACL del paso 3.

   ```bash
   curl -sI "http://$(tailscale ip -4):8082/" | head -n 1
   ```

   No usar `tailscale funnel`, que sí lo publicaría en internet.

3. Definir la etiqueta `tag:ci` y la ACL en la consola de administración
   (<https://login.tailscale.com/admin/acls>). Ejemplo de política (cambiar `100.x.y.z` por la IP
   del portátil, que da `tailscale ip -4`):

   ```json
   {
     "tagOwners": {
       "tag:ci": ["autogroup:admin"]
     },
     "hosts": {
       "portatil": "100.x.y.z"
     },
     "grants": [
       {"src": ["autogroup:member"], "dst": ["*"], "ip": ["*"]},
       {"src": ["tag:ci"], "dst": ["portatil"], "ip": ["tcp:8082"]}
     ]
   }
   ```

   La primera regla deja a los dispositivos de los usuarios hablar entre ellos. La segunda es la
   única de `tag:ci`: solo puede llegar al portátil, y solo al puerto 8082. Si la política ya
   tenía una regla `"src": ["*"], "dst": ["*"]`, hay que quitarla, porque `*` incluiría a `tag:ci`.

4. Crear el cliente OAuth en <https://login.tailscale.com/admin/settings/oauth> (Generate OAuth
   client). Permiso necesario: el scope `auth_keys` con escritura (en la consola, Keys, Auth
   Keys, Write), asociado a la etiqueta `tag:ci`. Con eso la acción crea la clave para unir el
   runner al tailnet. El secreto del cliente solo se muestra una vez.

5. Guardar los 4 secretos en el repo. `gh secret set` pide el valor por teclado sin mostrarlo,
   así no queda en el historial:

   ```bash
   gh secret set TS_OAUTH_CLIENT_ID  --repo Ridawo/SOS-hardened   # ID del cliente OAuth
   gh secret set TS_OAUTH_SECRET     --repo Ridawo/SOS-hardened   # secreto del cliente OAuth
   gh secret set DEFECTDOJO_URL      --repo Ridawo/SOS-hardened   # http://<maquina>.<tailnet>.ts.net:8082
   gh secret set DEFECTDOJO_API_KEY  --repo Ridawo/SOS-hardened   # la API key de DefectDojo
   ```

6. Probar: lanzar un run (`gh workflow run devsecops.yml --ref <rama>`, o Re-run del job `defectdojo` en la pestaña Actions) con el
   portátil encendido. Con el portátil apagado el job avisa con `::warning::` y el resto del
   pipeline no se ve afectado.

El pipeline también puede fallar por motivos concretos: si falta un secreto, el job avisa
"DefectDojo no configurado"; si la clave es incorrecta, DefectDojo contesta 401 y el job
termina en error (sin bloquear nada).

## Qué crea el envío en DefectDojo

No hay que crear nada a mano. `scripts/upload_to_defectdojo.py` usa `auto_create_context=true`,
así que en el primer envío se crean:

- Producto: `SOS-hardened (PAI-4)`
- Engagement: `CI-CD` para los runs de `main` y `CI-CD rama <rama>` para el resto de ramas
- Un test por tipo de informe: NPM Audit v7+ Scan, Semgrep JSON Report, Trivy Scan (config e
  imagen) y ZAP Scan.

Como el envío es `reimport`, con `close_old_findings=true` los hallazgos no se duplican
y los que desaparecen entre runs se cierran. Cada rama tiene su propio engagement para que
cerrar los de una rama no afecte a los de `main`.

## Problemas habituales

- **El puerto 8082 no responde justo tras `up`**: el stack todavía se está inicializando;
  esperar a que `initializer` termine.
- **`port is already allocated`**: algún puerto está ocupado. Cambiar `DD_PORT` o `DD_TLS_PORT`
  en `defectdojo.env` y repetir `docker compose up -d`.
- **401 al enviar**: la clave del secreto `DEFECTDOJO_API_KEY` está mal copiada.
- **El job `defectdojo` dice que no responde**: el portátil está apagado o sin Tailscale, o falta
  la regla de la ACL del paso 3. Comprobar con `tailscale status` y con el `curl` del paso 2.
- **Va lento**: es un stack grande para un portátil de 16 GB; no conviene tenerlo junto a
  otras máquinas virtuales pesadas.
