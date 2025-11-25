# Getting Started - Data Analysis Microservice

Esta guía te ayudará a configurar y ejecutar el microservicio de análisis de datos diario con orquestador Saga.

## 📋 Tabla de Contenidos

- [Requisitos Previos](#requisitos-previos)
- [Configuración del Entorno Local](#configuración-del-entorno-local)
- [Configuración de Google Cloud](#configuración-de-google-cloud)
- [Ejecución Local](#ejecución-local)
- [Despliegue a Cloud Run](#despliegue-a-cloud-run)
- [Configuración del Cron Job](#configuración-del-cron-job)
- [Pruebas](#pruebas)
- [Arquitectura](#arquitectura)
- [Solución de Problemas](#solución-de-problemas)

---

## 🔧 Requisitos Previos

### Software Necesario

- **Python 3.10+** - [Descargar](https://www.python.org/downloads/)
- **Google Cloud SDK** - [Instalar gcloud CLI](https://cloud.google.com/sdk/docs/install)
- **Docker** (opcional, para testing local) - [Descargar](https://www.docker.com/get-started)
- **Git** - [Descargar](https://git-scm.com/downloads)

### Cuenta de Google Cloud

- Proyecto de GCP activo
- Facturación habilitada
- APIs habilitadas:
  - Cloud Run API
  - Cloud Scheduler API
  - Firestore API
  - Secret Manager API
  - Cloud Storage API (opcional)
  - BigQuery API (opcional)

---

## 🚀 Configuración del Entorno Local

### 1. Clonar el Repositorio

```bash
git clone <repository-url>
cd AnalistsDIARIO
```

### 2. Configurar el Entorno Virtual

**Opción A: Usando el script automático**

```bash
./scripts/local-setup.sh
```

**Opción B: Manual**

```bash
# Crear entorno virtual
python3 -m venv venv

# Activar entorno virtual
# En macOS/Linux:
source venv/bin/activate

# En Windows:
# venv\Scripts\activate

# Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configurar Variables de Entorno

```bash
# Copiar archivo de ejemplo
cp .env.example .env

# Editar .env con tu configuración
nano .env  # o usa tu editor preferido
```

**Configuración mínima requerida en `.env`:**

```env
# GCP Configuration
GCP_PROJECT_ID=tu-proyecto-id
GOOGLE_APPLICATION_CREDENTIALS=/ruta/a/service-account-key.json

# Workflow Configuration
WORKFLOW_NAME=daily_data_analysis
ENVIRONMENT=development

# Server Configuration
PORT=8080
```

---

## ☁️ Configuración de Google Cloud

### 1. Autenticación

```bash
# Iniciar sesión en GCP
gcloud auth login

# Configurar proyecto por defecto
gcloud config set project TU_PROJECT_ID

# Autenticar Docker (si usarás Container Registry)
gcloud auth configure-docker
```

### 2. Crear Service Account

```bash
# Crear service account
gcloud iam service-accounts create data-analysis-service \
    --display-name="Data Analysis Service" \
    --project=TU_PROJECT_ID

# Asignar roles necesarios
gcloud projects add-iam-policy-binding TU_PROJECT_ID \
    --member="serviceAccount:data-analysis-service@TU_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/datastore.user"

gcloud projects add-iam-policy-binding TU_PROJECT_ID \
    --member="serviceAccount:data-analysis-service@TU_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

# Descargar clave de service account
gcloud iam service-accounts keys create service-account-key.json \
    --iam-account=data-analysis-service@TU_PROJECT_ID.iam.gserviceaccount.com
```

### 3. Habilitar APIs Necesarias

```bash
gcloud services enable run.googleapis.com
gcloud services enable cloudscheduler.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

### 4. Configurar Firestore

```bash
# Crear base de datos Firestore en modo nativo
gcloud firestore databases create --region=us-central1
```

### 5. Crear Secretos (Opcional)

```bash
# Ejemplo: Crear secreto para configuración
echo '{"api_key": "tu-api-key"}' | \
gcloud secrets create workflow-config \
    --data-file=- \
    --replication-policy="automatic"
```

---

## 💻 Ejecución Local

### 1. Activar Entorno Virtual

```bash
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows
```

### 2. Configurar Variables de Entorno

```bash
# Cargar variables desde .env
export $(cat .env | xargs)

# O manualmente:
export GCP_PROJECT_ID=tu-proyecto-id
export GOOGLE_APPLICATION_CREDENTIALS=/ruta/a/service-account-key.json
```

### 3. Ejecutar el Servidor

```bash
# Modo desarrollo
python main.py

# O usando uvicorn directamente
uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

### 4. Verificar que Funciona

Abre tu navegador en `http://localhost:8080` o usa curl:

```bash
# Health check
curl http://localhost:8080/health

# Ver información del servicio
curl http://localhost:8080/

# Ver estado del workflow
curl http://localhost:8080/status
```

### 5. Ejecutar el Workflow Manualmente

```bash
# Ejecución síncrona
curl -X POST http://localhost:8080/run-analysis

# Ejecución asíncrona (background)
curl -X POST "http://localhost:8080/run-analysis?async_execution=true"

# Con retry
curl -X POST "http://localhost:8080/run-analysis?retry=true"
```

---

## 🌐 Despliegue a Cloud Run

### Opción A: Usando el Script de Despliegue

```bash
# Configurar variables de entorno
export GCP_PROJECT_ID=tu-proyecto-id
export GCP_REGION=us-central1

# Ejecutar despliegue
./scripts/deploy.sh production
```

### Opción B: Despliegue Manual

```bash
# 1. Build de la imagen
gcloud builds submit --tag gcr.io/TU_PROJECT_ID/data-analysis-service

# 2. Deploy a Cloud Run
gcloud run deploy data-analysis-service \
    --image gcr.io/TU_PROJECT_ID/data-analysis-service \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --timeout 3600 \
    --max-instances 10 \
    --set-env-vars "ENVIRONMENT=production,GCP_PROJECT_ID=TU_PROJECT_ID,WORKFLOW_NAME=daily_data_analysis"

# 3. Obtener URL del servicio
gcloud run services describe data-analysis-service \
    --platform managed \
    --region us-central1 \
    --format 'value(status.url)'
```

### Configurar Variables de Entorno en Cloud Run

```bash
gcloud run services update data-analysis-service \
    --region us-central1 \
    --set-env-vars "GCP_PROJECT_ID=TU_PROJECT_ID,WORKFLOW_NAME=daily_data_analysis"
```

### Configurar Secretos en Cloud Run

```bash
gcloud run services update data-analysis-service \
    --region us-central1 \
    --update-secrets CONFIG_SECRET_NAME=workflow-config:latest
```

---

## ⏰ Configuración del Cron Job

### Opción A: Usando el Script

```bash
export GCP_PROJECT_ID=tu-proyecto-id
export GCP_REGION=us-central1

./scripts/setup-scheduler.sh
```

### Opción B: Manual

```bash
# Obtener URL del servicio
SERVICE_URL=$(gcloud run services describe data-analysis-service \
    --platform managed \
    --region us-central1 \
    --format 'value(status.url)')

# Crear Cloud Scheduler job
gcloud scheduler jobs create http daily-data-analysis-job \
    --location=us-central1 \
    --schedule="0 3 * * *" \
    --uri="${SERVICE_URL}/run-analysis" \
    --http-method=POST \
    --oidc-service-account-email=data-analysis-service@TU_PROJECT_ID.iam.gserviceaccount.com \
    --time-zone="America/New_York"
```

### Probar el Cron Job Manualmente

```bash
gcloud scheduler jobs run daily-data-analysis-job \
    --location=us-central1
```

### Modificar el Schedule

```bash
# Formato cron: "minuto hora día mes día_semana"
# Ejemplos:
# - "0 3 * * *"      -> Diario a las 3 AM
# - "0 */6 * * *"    -> Cada 6 horas
# - "0 9 * * 1"      -> Lunes a las 9 AM
# - "30 2 * * 1-5"   -> Lunes-Viernes a las 2:30 AM

gcloud scheduler jobs update http daily-data-analysis-job \
    --location=us-central1 \
    --schedule="0 2 * * *"  # Cambiar a 2 AM
```

---

## 🧪 Pruebas

### Testing Local

```bash
# Usar el script de testing
./scripts/test-service.sh http://localhost:8080
```

### Testing en Cloud Run

```bash
# Obtener URL del servicio
SERVICE_URL=$(gcloud run services describe data-analysis-service \
    --platform managed \
    --region us-central1 \
    --format 'value(status.url)')

# Ejecutar tests
./scripts/test-service.sh $SERVICE_URL
```

### Tests Manuales de Endpoints

```bash
# 1. Health Check
curl $SERVICE_URL/health

# 2. Estado del workflow
curl $SERVICE_URL/status

# 3. Ejecutar análisis (async)
curl -X POST "$SERVICE_URL/run-analysis?async_execution=true"

# 4. Ver historial de ejecuciones
curl "$SERVICE_URL/history?limit=5"

# 5. Resetear workflow
curl -X POST $SERVICE_URL/reset
```

---

## 🏗️ Arquitectura

### Componentes Principales

```
┌─────────────────────┐
│  Cloud Scheduler    │  ← Trigger diario (3 AM)
│    (Cron Job)       │
└──────────┬──────────┘
           │ POST /run-analysis
           ▼
┌─────────────────────┐
│    Cloud Run        │
│  (FastAPI Service)  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Saga Orchestrator  │  ← Maneja el flujo y compensaciones
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│  Workflow Steps (en orden):             │
│  1. ExtractStep    → Extrae datos       │
│  2. TransformStep  → Limpia/normaliza   │
│  3. AnalyzeStep    → Calcula métricas   │
│  4. StoreStep      → Guarda resultados  │
└─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────┐
│     Firestore       │  ← Estado del workflow
│  - workflow_runs    │
│  - history          │
└─────────────────────┘
```

### Flujo de Ejecución

1. **Cloud Scheduler** dispara el workflow enviando POST a `/run-analysis`
2. **SagaOrchestrator** lee el estado desde Firestore
3. Ejecuta cada step en orden:
   - Si un step falla, ejecuta compensaciones en orden inverso
   - Guarda estado después de cada step exitoso
4. Al completar, guarda resultados y actualiza historial

### Patrón Saga

Cada step implementa:
- `run()`: Lógica principal del paso
- `compensate()`: Lógica de rollback/compensación

Si el paso 3 falla, se ejecutan compensaciones de los pasos 2 y 1.

---

## 🔍 Solución de Problemas

### Error: "Module not found"

```bash
# Asegúrate de que el entorno virtual esté activado
source venv/bin/activate

# Reinstala dependencias
pip install -r requirements.txt
```

### Error: "Permission denied" en Firestore

```bash
# Verifica roles del service account
gcloud projects get-iam-policy TU_PROJECT_ID \
    --flatten="bindings[].members" \
    --filter="bindings.members:serviceAccount:data-analysis-service@*"

# Asignar rol necesario
gcloud projects add-iam-policy-binding TU_PROJECT_ID \
    --member="serviceAccount:data-analysis-service@TU_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/datastore.user"
```

### Error: "Secret not found"

```bash
# Listar secretos disponibles
gcloud secrets list

# Verificar permisos
gcloud secrets get-iam-policy workflow-config
```

### El workflow no se ejecuta desde Cloud Scheduler

```bash
# Ver logs del scheduler
gcloud scheduler jobs describe daily-data-analysis-job \
    --location=us-central1

# Ver logs de Cloud Run
gcloud logs read --service=data-analysis-service \
    --limit=50 \
    --format=json
```

### Debugging Local

```bash
# Activar modo debug en main.py
export LOG_LEVEL=DEBUG

# Ver logs detallados
python main.py
```

### Ver Estado del Workflow

```bash
# Consultar Firestore directamente
gcloud firestore databases export gs://TU_BUCKET/backup \
    --collection-ids=workflow_runs

# O usar la API
curl http://localhost:8080/status | jq '.'
```

### Resetear Workflow Bloqueado

```bash
# Via API
curl -X POST http://localhost:8080/reset

# O manualmente en Firestore Console
# Ir a: Firestore > workflow_runs > daily_data_analysis
# Editar status a "NOT_STARTED"
```

---

## 📚 Recursos Adicionales

### Documentación

- [Documentación de FastAPI](https://fastapi.tiangolo.com/)
- [Cloud Run Docs](https://cloud.google.com/run/docs)
- [Cloud Scheduler Docs](https://cloud.google.com/scheduler/docs)
- [Firestore Docs](https://cloud.google.com/firestore/docs)

### Monitoreo

```bash
# Ver logs en tiempo real
gcloud logs tail --service=data-analysis-service

# Métricas de Cloud Run
gcloud monitoring dashboards list
```

### Estructura del Proyecto

```
AnalistsDIARIO/
├── main.py                 # Entry point FastAPI
├── saga_orchestrator.py    # Orquestador Saga
├── firestore_repo.py       # Repositorio Firestore
├── secrets_manager.py      # Manejo de secretos
├── requirements.txt        # Dependencias Python
├── Dockerfile             # Containerización
├── .env.example           # Template de variables
├── steps/                 # Pasos del workflow
│   ├── __init__.py
│   ├── extract.py         # Extracción de datos
│   ├── transform.py       # Transformación
│   ├── analyze.py         # Análisis
│   └── store.py           # Almacenamiento
└── scripts/               # Scripts de deployment
    ├── deploy.sh
    ├── setup-scheduler.sh
    ├── local-setup.sh
    └── test-service.sh
```

---

## 🤝 Contribuciones

Para contribuir al proyecto:

1. Fork el repositorio
2. Crea una rama: `git checkout -b feature/nueva-funcionalidad`
3. Commit cambios: `git commit -am 'Agregar nueva funcionalidad'`
4. Push: `git push origin feature/nueva-funcionalidad`
5. Crear Pull Request

---

## 📄 Licencia

[Especifica tu licencia aquí]

---

## 💬 Soporte

Para preguntas o problemas:
- Crear un issue en GitHub
- Contactar al equipo de desarrollo

---

**¡Listo para comenzar! 🚀**
