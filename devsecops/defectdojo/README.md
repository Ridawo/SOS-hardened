# DefectDojo en local (puerto 8082)

DefectDojo es donde se centralizan los informes de las herramientas del pipeline (npm audit,
Semgrep, ZAP y Trivy). Aqui se levanta en local con Docker y el pipeline le sube los
resultados por API.

Puertos del montaje: la app SOS usa el **8080**, el 8081 esta ocupado por otro contenedor
(`sie_bonita`) y DefectDojo va en el **8082**. DefectDojo usa el 8080 por defecto, por eso
hay que cambiarlo.

## Requisitos

- Docker con Compose v2 (`docker compose version`). Aqui hay Compose 2.40.
- Git.
- Unos 4 GB de RAM libres para el stack (postgres, valkey, uwsgi, celery, nginx).
- Los puertos 8082 y 8444 libres: `ss -ltn | grep -E ':8082|:8444'` no debe devolver nada.

## Como funciona este directorio

La forma oficial de instalarlo es clonar `django-DefectDojo` y usar su `docker-compose.yml`.
El fichero [`docker-compose.yml`](docker-compose.yml) de esta carpeta no define servicios:
usa `include` para cargar el compose oficial y le pasa `defectdojo.env` con los puertos.
Las imagenes son las oficiales (`registry.defectdojo.com/defectdojo/...`).

Nota: por defecto las imagenes se descargan a traves de `registry.defectdojo.com`, que
registra las descargas. Si se prefiere Docker Hub, exportar `DD_IMAGE_REGISTRY=docker.io`
antes de levantar.

## Levantarlo

Desde `devsecops/defectdojo/`:

```bash
# 1. Clonar el repo oficial dentro de esta carpeta
git clone --depth 1 https://github.com/DefectDojo/django-DefectDojo.git

# 2. Que git ignore el clon (es otro repositorio, no debe ir al repo de la practica)
echo 'devsecops/defectdojo/django-DefectDojo/' >> ../../.git/info/exclude
echo 'devsecops/defectdojo/defectdojo.env'     >> ../../.git/info/exclude

# 3. Puertos: 8082 para HTTP y 8444 para HTTPS (el 8443 por defecto tambien vale si esta libre)
printf 'DD_PORT=8082\nDD_TLS_PORT=8444\n' > defectdojo.env

# 4. Construir/descargar y arrancar en segundo plano
docker compose up -d
```

La primera vez tarda unos minutos (descarga de imagenes y migraciones de la base de datos).
Para ver como va:

```bash
docker compose ps
docker compose logs -f initializer   # termina cuando acaba la inicializacion
```

Cuando el servicio `initializer` ha terminado, la interfaz esta en <http://localhost:8082>.

Alternativa sin este compose: dentro del clon, `DD_PORT=8082 docker compose up -d`
(el compose oficial lee la variable `DD_PORT`).

### Parar y borrar

```bash
docker compose stop        # para y conserva los datos
docker compose down        # borra los contenedores, los datos siguen en los volumenes
docker compose down -v     # borra tambien los volumenes (se pierde todo)
```

## Contrasena inicial de admin

El usuario es `admin`. La contrasena se genera al inicializar y sale en los logs del
contenedor `initializer`:

```bash
docker compose logs initializer | grep "Admin password:"
```

Guardarla, porque solo se ve ahi. Si se pierde, se puede poner una nueva:

```bash
docker compose exec -it uwsgi ./manage.py changepassword admin
```

## Crear la API key

El pipeline sube los informes a `POST /api/v2/import-scan/` con una API key de este usuario.

1. Entrar en <http://localhost:8082> con `admin`.
2. Arriba a la derecha, el icono de usuario, **API v2 Key**
   (tambien se llega directamente en <http://localhost:8082/api/v2/key/>).
3. Copiar la clave (cadena hexadecimal de 40 caracteres).

Comprobar que funciona:

```bash
curl -s -H "Authorization: Token <API_KEY>" http://localhost:8082/api/v2/users/ | head -c 200
```

### Donde se guarda la clave

La API key es un secreto. **Nunca va en el repositorio** (ni en el workflow, ni en un
`.env` que se suba). Se guarda como secreto de GitHub con el nombre exacto
`DEFECTDOJO_API_KEY`:

Repo `Ridawo/SOS-hardened` -> Settings -> Secrets and variables -> Actions ->
New repository secret -> Name: `DEFECTDOJO_API_KEY`, Secret: la clave.

O con la CLI: `gh secret set DEFECTDOJO_API_KEY --repo Ridawo/SOS-hardened`
(pide el valor por entrada estandar, no queda en el historial).

La URL, `DEFECTDOJO_URL`, vale `http://localhost:8082` por defecto; como el runner corre
en esta misma maquina, no hace falta configurarla.

## Que crea el pipeline en DefectDojo

No hay que crear nada a mano. El script `devsecops/scripts/upload_to_defectdojo.py` usa
`auto_create_context=true`, asi que en la primera subida se crean:

- Producto: `SOS-hardened (PAI-4)`
- Engagement: `CI-CD`
- Un test por tipo de informe: NPM Audit v7+ Scan, Semgrep JSON Report, ZAP Scan y Trivy Scan.

## Problemas habituales

- **El puerto 8082 no responde justo tras `up`**: el stack todavia se esta inicializando;
  esperar a que `initializer` termine.
- **`port is already allocated`**: algun puerto esta ocupado; cambiar `DD_PORT`/`DD_TLS_PORT`
  en `defectdojo.env` y volver a hacer `docker compose up -d`.
- **401 al subir un informe**: la clave esta mal copiada o el secreto de GitHub no existe.
- **Se levanta pero va lento**: es un stack grande para un portatil de 16 GB; no
  conviene tenerlo junto a otras maquinas virtuales pesadas.
