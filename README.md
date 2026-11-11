# Portafolio de arquitectura — Backend

API HTTP para una plataforma de portafolio de arquitectura. Gestiona proyectos, contenido profesional, archivos multimedia y sesiones de administración, y entrega al sitio público únicamente el contenido autorizado por sus reglas de publicación y visibilidad.

Este repositorio contiene el backend FastAPI. La interfaz pública y el panel administrativo se encuentran en el [repositorio del frontend Angular](https://github.com/TheDanielrity/portfolio-arquitect-front).

## Funcionalidades

- Autenticación de administradores con JWT, contraseñas protegidas con Argon2 y sesiones persistidas con renovación de tokens.
- Gestión de proyectos, categorías, etiquetas, atributos, publicación, visibilidad y eliminación lógica.
- Secciones dinámicas de texto, imagen, galería, vídeo, modelo 3D, cita y composición dividida.
- Perfil profesional, redes sociales, servicios y configuración del sitio.
- Recepción y administración de mensajes de contacto mediante la API.
- Metadatos y entrega autorizada de medios, con almacenamiento local o Cloudflare R2.
- Autorización de subidas directas a R2, confirmación y limpieza de operaciones pendientes.
- API pública separada de las operaciones administrativas, documentación OpenAPI y migraciones de base de datos.

La disponibilidad de una operación en la API no implica que el frontend actual muestre una pantalla para ella. Por ejemplo, la interfaz Angular no incluye actualmente una bandeja de mensajes ni un formulario público de contacto.

## Estado del proyecto

Las fases 0 a 14 del backend figuran como completadas en [PLANS.md](PLANS.md). El alojamiento de la nueva demo en Render y la transferencia de datos siguen pendientes de configuración y verificación. El estado de las fases no equivale a una certificación del despliegue de producción.

## Tecnologías

Python 3.12+, FastAPI, Pydantic, SQLAlchemy 2 con sesiones asíncronas, PostgreSQL, Psycopg 3, Alembic, PyJWT, Argon2 y Boto3. Las herramientas de desarrollo son pytest, pytest-asyncio, HTTPX, Ruff y mypy.

## Requisitos

- Python 3.12 o superior; el desarrollo local está documentado con Python 3.13.
- PostgreSQL con permisos para crear los esquemas y funciones de la aplicación y con la extensión `pgcrypto` disponible.
- Git y una terminal. Los ejemplos de instalación siguientes utilizan PowerShell.
- Una cuenta y un bucket privado de Cloudflare R2 solamente si se selecciona ese almacenamiento.

Las dependencias de Python deben instalarse en un entorno virtual local llamado `.venv`. No se necesita Docker.

## Instalación local

```powershell
git clone https://github.com/TheDanielrity/portfolio-arquitect-back.git
cd portfolio-arquitect-back
if (-not (Test-Path .venv)) { py -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

En Linux o macOS, crea el entorno con `python3 -m venv .venv` y utiliza `.venv/bin/python` en los comandos siguientes.

### Preparar PostgreSQL

Con PostgreSQL en ejecución, crea un usuario y una base de datos para la aplicación. Por ejemplo, desde `psql` con un usuario administrador:

```sql
CREATE ROLE portfolio LOGIN;
\password portfolio
CREATE DATABASE portfolio OWNER portfolio;
```

`\password` solicita la contraseña de forma interactiva. Si el usuario de la aplicación no puede instalar `pgcrypto`, solicita su instalación al administrador de PostgreSQL antes de ejecutar las migraciones. No ejecutes el SQL de diseño por separado: Alembic administra el esquema.

### Configurar el entorno

Edita `.env` antes de iniciar la aplicación o ejecutar las migraciones. Las variables de proceso tienen prioridad sobre ese archivo.

| Variable           | Configuración                                                                |
| ------------------ | ---------------------------------------------------------------------------- |
| `DATABASE_URL`     | URL `postgresql+psycopg://USUARIO:CONTRASEÑA@HOST:5432/BASE`                 |
| `JWT_SECRET_KEY`   | Secreto aleatorio de al menos 32 bytes; el marcador del ejemplo se rechaza   |
| `APP_ENV`          | `development`, `test` o `production`                                         |
| `DEBUG`            | `false` en producción                                                        |
| `CORS_ORIGINS`     | Lista JSON de orígenes exactos; para desarrollo, `["http://localhost:4200"]` |
| `STORAGE_PROVIDER` | `local` para desarrollo sin R2, o `r2`                                       |
| `MEDIA_BASE_URL`   | Origen accesible del backend; localmente, `http://127.0.0.1:8000`            |

Codifica los caracteres especiales de las credenciales cuando formen parte de la URL de conexión. No publiques `.env`, contraseñas ni tokens. La plantilla [`.env.example`](.env.example) enumera también los tiempos de sesión, límites de peticiones y configuración de medios.

### Aplicar migraciones y crear el administrador

Con una base nueva y la configuración anterior lista:

```powershell
.\.venv\Scripts\python.exe -m app.core.check_database
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.modules.auth.create_admin
```

El último comando requiere una terminal interactiva y solicita la contraseña sin mostrarla. No existe una cuenta administrativa predeterminada. El inicio del servidor no aplica migraciones automáticamente.

### Iniciar la API

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --loop app.core.event_loop:selector_loop_factory
```

La opción de bucle permite utilizar las conexiones asíncronas de Psycopg en Windows. En Linux y macOS se puede usar el mismo comando con `.venv/bin/python`.

| Dirección local                       | Uso                                                  |
| ------------------------------------- | ---------------------------------------------------- |
| <http://127.0.0.1:8000/api/v1/health> | Comprobación de que la API responde                  |
| <http://127.0.0.1:8000/docs>          | Documentación interactiva de Swagger                 |
| <http://127.0.0.1:8000/redoc>         | Referencia de la API                                 |
| <http://127.0.0.1:8000/openapi.json>  | Contrato OpenAPI para clientes y generación de tipos |

La comprobación `/health` no verifica PostgreSQL ni R2. Usa `app.core.check_database` para comprobar la conexión a la base. Con una base vacía, las colecciones pueden estar vacías y el perfil público puede responder 404 hasta que se configure.

## Organización de la API

Todas las operaciones de negocio utilizan el prefijo `/api/v1`:

| Grupo         | Responsabilidad                                        |
| ------------- | ------------------------------------------------------ |
| `/auth/...`   | Inicio y cierre de sesión, renovación y usuario actual |
| `/admin/...`  | Operaciones protegidas de administración               |
| `/public/...` | Consulta de contenido público y contacto               |

Consulta los métodos, rutas y modelos reales en OpenAPI y en el [inventario de endpoints](docs/api/endpoints.md). El backend controla permisos, validación y visibilidad; ocultar una ruta del frontend no sustituye esa autorización.

La autenticación utiliza `Authorization: Bearer <access_token>`. La renovación rota las credenciales: el cliente debe coordinar las solicitudes simultáneas y conservar la pareja de tokens vigente. Consulta el [contrato de integración](docs/api/frontend-handoff.md) para el flujo completo.

<a id="administrative-api-conventions-phase-11"></a>

### Convenciones administrativas

Las colecciones paginadas devuelven `items`, `total`, `limit` y `offset`. `limit` acepta de 1 a 100 y `offset` comienza en cero. La búsqueda `q` compara fragmentos literales sin distinguir mayúsculas y minúsculas. Los filtros se combinan; los parámetros no admitidos producen un error de validación.

| Colección bajo `/api/v1/admin` | Campos de búsqueda                         | Filtros                                                        | Orden disponible; predeterminado entre paréntesis              |
| ------------------------------ | ------------------------------------------ | -------------------------------------------------------------- | -------------------------------------------------------------- |
| `projects`                     | `title`, `slug`, `client_name`, `location` | `status`, `visibility`, `is_featured`, `category_id`, `tag_id` | `sort_order` (ascendente), `title`, `created_at`, `updated_at` |
| `categories`                   | `name`, `slug`                             | `is_active`                                                    | `sort_order` (ascendente), `name`, `created_at`                |
| `tags`                         | `name`, `slug`                             | —                                                              | `name` (ascendente), `created_at`                              |
| `media`                        | `original_filename`, `title`, `alt_text`   | `type`                                                         | `created_at` (descendente), `original_filename`, `file_size`   |
| `services`                     | `name`, `slug`                             | `is_visible`                                                   | `sort_order` (ascendente), `name`, `created_at`                |
| `profile/social-links`         | `platform`, `username`                     | `is_visible`                                                   | `sort_order` (ascendente), `platform`, `created_at`            |
| `contact-messages`             | `name`, `email`, `subject`, `message`      | `status`                                                       | `created_at` (descendente), `name`                             |

`sort` selecciona el campo y `direction` acepta `asc` o `desc`. Los atributos, medios y secciones conservan su orden editorial mediante las operaciones de reordenación del contrato. La configuración global devuelve una lista acotada sin paginación.

## Almacenamiento de medios

En desarrollo, `STORAGE_PROVIDER=local` guarda los archivos en el directorio configurado por `LOCAL_STORAGE_PATH`, excluido del repositorio.

Para R2, configura `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` y `R2_BUCKET_NAME`, y selecciona `STORAGE_PROVIDER=r2`. El cliente solicita autorización, envía los bytes directamente al destino firmado y confirma la operación con el backend. El bucket permanece privado; las políticas del backend determinan qué contenido puede entregarse públicamente.

El navegador necesita los orígenes y encabezados correctos en CORS. Los límites de tamaño y formatos siguen el contrato del backend. Consulta la [guía de integración de medios](docs/api/frontend-handoff.md) y el [informe de almacenamiento](docs/media-storage-phase14-report.md).

## Pruebas y comprobaciones

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pip check
```

Sin las variables de conexión de pruebas, las pruebas que requieren PostgreSQL se omiten. Las pruebas normales no utilizan un bucket R2 real.

### Validación de migraciones

Para las pruebas de PostgreSQL, configura de forma privada `TEST_DATABASE_URL` y `MIGRATION_TEST_ADMIN_URL` en el entorno del proceso de pruebas, con el esquema `postgresql+psycopg`. pytest no obtiene esas variables del `.env` de la aplicación.

`TEST_DATABASE_URL` permite comprobar conectividad y transacciones. `MIGRATION_TEST_ADMIN_URL` requiere un usuario de pruebas con permiso `CREATEDB` y capacidad para instalar `pgcrypto`. Las pruebas de dominio y migraciones crean bases temporales con nombres aleatorios y eliminan las que crearon durante la limpieza; no utilices credenciales de producción.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_migrations_integration.py
```

Estas pruebas comprueban el ciclo de migraciones, el esquema frente al SQL aprobado y las restricciones de la base. `alembic check` permite comprobar diferencias entre la base migrada y los modelos. Consulta la [guía de desarrollo](docs/development.md) para preparar el entorno completo.

## Despliegue

El destino previsto para la demo es **Render**, con PostgreSQL y Cloudflare R2. El frontend se prepara para Netlify. Aún no se ha verificado el despliegue de esta migración.

La [guía de Netlify y Render del frontend](https://github.com/TheDanielrity/portfolio-arquitect-front/blob/main/docs/netlify-render.md) documenta los comandos de compilación, migración y arranque, las variables privadas, CORS y la transferencia de datos desde el entorno anterior. Las migraciones de esquema no transfieren automáticamente los proyectos ni sus archivos.

## Organización del código

```text
app/
├── core/       # Configuración, base de datos, seguridad y errores
└── modules/
    ├── auth/       # Administradores y sesiones
    ├── portfolio/  # Proyectos, taxonomía y secciones
    ├── media/      # Archivos, subidas y almacenamiento
    ├── content/    # Perfil, servicios y configuración
    └── contact/    # Mensajes de contacto
alembic/        # Migraciones versionadas
tests/          # Pruebas unitarias y de integración
docs/           # Contratos, diseño de base y guías
```

## Documentación

- [Instalación y desarrollo local](docs/development.md).
- [Contrato de integración con Angular](docs/api/frontend-handoff.md).
- [Inventario de endpoints](docs/api/endpoints.md).
- [Esquema SQL](docs/database/schema.sql) y [modelo DBML](docs/database/schema.dbml).
- [Revisión de seguridad](docs/security/phase12-review.md).
- [Plan de implementación](PLANS.md) e [instrucciones del repositorio](AGENTS.md).

## Licencia

Este repositorio no declara una licencia general de uso. Las dependencias de terceros conservan sus respectivas licencias.
