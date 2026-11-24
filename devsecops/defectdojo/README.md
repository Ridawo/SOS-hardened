# DefectDojo en local (puerto 8082)

DefectDojo centraliza los informes de las herramientas del pipeline (npm audit, Semgrep,
Trivy y ZAP). Se ejecuta en local con Docker. Los informes no se suben solos: se importan
a mano después de cada run con el script de [`../scripts/`](../scripts/).

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

La importación usa la API v2 con una clave de este usuario.

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
fichero `.env` que se suba. Tampoco se guarda como secreto de GitHub: el pipeline no
usa DefectDojo.

Para la importación, la clave se pasa en la variable de entorno `DEFECTDOJO_API_KEY`
(solo para esa sesión de terminal). Si no está definida, `importar_defectdojo.sh` la pide
por teclado sin mostrarla.

La URL por defecto es `http://localhost:8082`. Se puede cambiar con `DEFECTDOJO_URL`.

## Importar un run

Con DefectDojo levantado y `gh` autenticado en el repo:

```bash
devsecops/scripts/importar_defectdojo.sh <run_id>
```

El script baja el artefacto `devsecops-reports` del run y sube los 5 informes con
`reimport-scan`. El `<run_id>` sale de `gh run list --repo Ridawo/SOS-hardened --workflow devsecops.yml`.

## Qué crea la importación en DefectDojo

No hay que crear nada a mano. `scripts/upload_to_defectdojo.py` usa `auto_create_context=true`,
así que en la primera importación se crean:

- Producto: `SOS-hardened (PAI-4)`
- Engagement: `CI-CD`
- Un test por tipo de informe: NPM Audit v7+ Scan, Semgrep JSON Report, Trivy Scan y ZAP Scan.

Como la importación es `reimport`, con `close_old_findings=true` los hallazgos no se duplican
y los que desaparecen entre runs se cierran.

## Problemas habituales

- **El puerto 8082 no responde justo tras `up`**: el stack todavía se está inicializando;
  esperar a que `initializer` termine.
- **`port is already allocated`**: algún puerto está ocupado. Cambiar `DD_PORT` o `DD_TLS_PORT`
  en `defectdojo.env` y repetir `docker compose up -d`.
- **401 al importar**: la clave está mal copiada o no está definida `DEFECTDOJO_API_KEY`.
- **Va lento**: es un stack grande para un portátil de 16 GB; no conviene tenerlo junto a
  otras máquinas virtuales pesadas.
