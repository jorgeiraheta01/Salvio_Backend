# Salvio — Backend (SalvioCore)

API backend de Salvio, un SaaS multi-tenant de gestion clinica. Construido con
FastAPI + SQLAlchemy sobre MySQL, con Valkey/Redis para cache y colas.

## Stack

- **FastAPI** — framework de API
- **SQLAlchemy 2.x** — ORM
- **MySQL 8** — base de datos (una base por tenant + base de control)
- **Valkey (Redis-compatible)** — cache / rate limiting / colas
- **Celery** — tareas en background
- **Alembic** — migraciones (control) + migraciones SQL manuales por carpeta (`sql/migrations`)
- **JWT (python-jose)** — autenticacion
- **TOTP (pyotp)** — 2FA para platform_admin y usuarios de clinica
- **ReportLab** — generacion de PDFs de facturacion

## Requisitos previos

- Python 3.11+ (venv incluido en `venv/`)
- Docker (para levantar MySQL y Valkey via `docker-compose.yml`)

## Arranque local

1. Levantar la base de datos y cache:

   ```bash
   docker compose up -d
   ```

2. Copiar el archivo de entorno y completar los valores:

   ```bash
   cp .env.example .env
   ```

3. Activar el entorno virtual e instalar dependencias (si es necesario):

   ```bash
   venv/Scripts/activate      # Windows
   pip install -r requirements.txt
   ```

4. Levantar el servidor:

   ```bash
   venv/Scripts/python.exe -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

   La API queda disponible en `http://localhost:8000`, con docs interactivas en
   `http://localhost:8000/docs`.

## Variables de entorno (`.env`)

| Variable | Descripcion |
|---|---|
| `DATABASE_URL` | Cadena de conexion MySQL (`mysql+pymysql://...`) |
| `REDIS_URL` | Cadena de conexion a Valkey/Redis |
| `JWT_SECRET` | Clave de firma de tokens JWT |
| `TOTP_ENCRYPTION_KEY` | Clave para cifrar los secretos TOTP de 2FA |
| `META_WA_TOKEN` | Token de WhatsApp Business (Meta) |
| `CLOUDFLARE_R2_BUCKET` / `CLOUDFLARE_R2_ACCESS_KEY` / `CLOUDFLARE_R2_SECRET_KEY` | Almacenamiento de PDFs (facturas, etc.) en Cloudflare R2 |

`.env` esta en `.gitignore` y no debe subirse al repositorio.

## Estructura del proyecto

```
app/
  core/            Rate limiting y utilidades transversales
  dependencies/    Auth, module gate (feature flags por tenant)
  middleware/      Aislamiento de tenant, modo mantenimiento
  models/          Modelos SQLAlchemy (clinica, catalogos, tenant, facturacion, horarios)
  modules/
    platform_admin/  Endpoints y logica del owner de la plataforma
    tenants/          Alta, dashboard y administracion de tenants
  routers/         Endpoints por dominio (pacientes, citas, encuentros, lab, imagenologia, etc.)
  schemas/         Schemas Pydantic
  services/        Logica de negocio
  utils/           Helpers (TOTP, etc.)
sql/migrations/
  control/         Migraciones de la base de control (multi-tenant)
  tenant/          Migraciones aplicadas a cada base de tenant
tests/             Suite de pytest (ciclo de vida de paciente/usuario, 2FA, facturacion, smoke tests)
scripts/           Scripts utilitarios (seed de catalogos como CIE-10)
```

## Modulos principales

- **Autenticacion**: login JWT + 2FA (TOTP) tanto para platform_admin como para usuarios de clinica.
- **Multi-tenant**: aislamiento por tenant (`TenantIsolationMiddleware`), estados `active/suspended/archived`, modo mantenimiento y feature flags por tenant.
- **Clinico**: pacientes, citas, encuentros, notas clinicas, diagnosticos, signos vitales, ordenes, prescripciones, laboratorio, imagenologia, referencias.
- **Horarios de medico** (`doctor_schedule`): disponibilidad y agenda por profesional.
- **Facturacion**: facturacion de tenants y facturacion de plataforma (`platform_billing`), con generacion de PDF.
- **Catalogos**: medicamentos, examenes de laboratorio, sistemas clinicos, CIE-10.
- **Auditoria**: bitacora de acciones del owner de la plataforma.

## Tests

```bash
venv/Scripts/python.exe -m pytest
```

## Docker

```bash
docker build -t salvio-core .
```

`docker-compose.yml` en este repo solo levanta MySQL y Valkey; la API se corre
directamente con `uvicorn` (ver arriba) o con el `Dockerfile` incluido.
