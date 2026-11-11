# AgriSense AI Irrigation Advisor

AgriSense is a full-stack agricultural intelligence platform for selecting field boundaries, classifying crops, assessing moisture stress, and monitoring weather-driven irrigation conditions. The project combines a FastAPI backend with PostgreSQL + PostGIS, a React + TypeScript frontend, and satellite-based analytics workflows designed around the farmer’s field polygon.

This repository is no longer a simple Phase 1 prototype. It contains the current application flow for:

- user authentication and protected access
- field drawing and geometry validation
- spatial persistence in PostGIS
- crop classification using satellite observations
- moisture stress analysis based on vegetation and thermal indicators
- weather intelligence and agronomic forecasting
- field history and dashboard navigation

---

## Project status

The app currently implements a multi-stage agricultural workflow:

1. Area Selection
   - user registers or logs in
   - user selects a location or draws a field polygon on a map
   - geometry is validated and saved to the database

2. Crop Analysis
   - saved field geometry is used for crop-type classification
   - growth-stage detection is computed from crop temporal behavior

3. Moisture Analysis
   - moisture stress score and trend indicators are generated for the field

4. Weather Intelligence
   - the current field or default Punjab coordinates are used to fetch weather forecasts

5. History and Management
   - saved fields can be viewed, selected, and managed from the dashboard

---

## Architecture overview

```text
crop/
├── backend/                       # FastAPI application
│   ├── app/
│   │   ├── api/                   # Route modules: auth, fields, crop, moisture, weather, analysis
│   │   ├── core/                  # config, database, security, startup settings
│   │   ├── models/                # SQLAlchemy models for users, fields, analysis results
│   │   ├── schemas/               # Pydantic request/response schemas
│   │   ├── services/              # crop, moisture, weather, Bhoonidhi, GEE, validation, geocoding
│   │   ├── utils/                 # geometry helpers and time-window logic
│   │   └── main.py                # FastAPI app + startup checks
│   ├── requirements.txt
│   ├── run_startup_checks.py
│   └── pyrefly.toml
├── frontend/                      # Vite + React app
│   ├── src/
│   │   ├── components/            # dashboard widgets, stage navigation, weather panels
│   │   ├── layouts/               # protected dashboard layout and context
│   │   ├── pages/                 # login, register, dashboard, crop, moisture, history, weather, settings
│   │   ├── services/              # API client
│   │   └── utils/                 # analysis mapping and caching utilities
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.*
├── docker-compose.yml             # PostgreSQL + PostGIS container
├── pyrefly.toml                   # workspace Python config
├── README.md
├── start.md                      # quick start notes
└── backend/requirements.txt
```

---

## Technology stack

Frontend
- React 19
- TypeScript
- Vite
- React Router
- Leaflet + React-Leaflet
- Leaflet Geoman for field drawing
- Recharts for analytical charts
- Lucide icons

Backend
- FastAPI
- SQLAlchemy
- Pydantic + Pydantic Settings
- PostgreSQL 15 + PostGIS 3.3
- GeoAlchemy2
- Shapely
- JWT authentication with bcrypt
- httpx for API integrations

Data and analysis services
- Google Earth Engine integration
- Sentinel-2 and Sentinel-1 workflows
- Landsat thermal time-series retrieval
- Bhoonidhi connectivity and collection checks
- reverse geocoding via Nominatim-style metadata enrichment
- weather forecasting via Open-Meteo

---

## Core features

### Authentication and user management
- registration with email + password
- login returning a JWT access token
- protected routes for authenticated dashboard access
- user session stored in browser local storage

### Field boundary workflow
- map-based polygon drawing
- coordinate validation
- closed polygon detection
- area, perimeter, centroid, and acreage calculations
- reverse-geocoded village, district, and state metadata
- persistence of geometry into PostGIS
- unique field IDs generated per user record

### Crop analysis stage
- uses saved field geometry as the area of interest
- reads Sentinel-2 and Sentinel-1 inputs
- computes crop classification and growth-stage indicators
- stores analysis results in the database cache
- exposes crop summary to the frontend dashboard

### Moisture stress analysis
- ingest multi-date optical metrics and SAR features
- calculates stress score and stress classification
- generates stress map and trend timeline
- uses Landsat LST when available for thermal indicators

### Weather intelligence
- forecast dashboard for current field coordinates
- current conditions, hourly forecast, daily outlook, and agronomic summary
- irrigation outlook, solar, wind, atmospheric details
- weather alerts and field-aware location metadata

### Dashboard and history
- stage-based navigation across area selection, crop analysis, moisture analysis, weather, settings
- saved field list and quick selection from history
- route-protected dashboard layout with active field context

---

## Current application routes

### Frontend route structure
The frontend app is configured in the root router and includes these protected pages:

- /login
- /register
- /
- /area-selection
- /crop-analysis
- /moisture-analysis
- /history
- /weather
- /settings

The dashboard layout wraps all authenticated pages with a field context and stage navigation flow.

### Backend API groups

Authentication
- POST /api/auth/register
- POST /api/auth/login
- GET /api/auth/me
- POST /api/auth/change-password

Fields
- POST /api/fields/validate
- POST /api/fields
- GET /api/fields
- GET /api/fields/{field_id}
- PUT /api/fields/{field_id}
- DELETE /api/fields/{field_id}

Crop and moisture analysis
- POST /api/crop/classify
- POST /api/moisture/analyze

Analysis wrapper routes
- POST /api/analysis/crop
- POST /api/analysis/moisture

Weather
- GET /api/weather/forecast

Bhoonidhi status
- GET /api/bhoonidhi/health

API docs
- http://localhost:8000/docs
- http://localhost:8000/redoc

---

## Data model summary

### users
Stores user identity and authentication metadata.

### fields
Stores the validated field boundary and its metadata:
- field_id
- user_id
- geometry (PostGIS polygon in EPSG:4326)
- centroid
- area_m2, area_hectares, area_acres
- perimeter_m
- latitude, longitude
- village, district, state, country, postal_code
- created_at, updated_at

### analysis_results
Stores crop and stress analysis outputs keyed by field and date window.
Fields include crop, growth stage, stress score, stress class, time series, stress map, classification map, and model version.

---

## Local setup

### Prerequisites
- Docker Desktop or Docker Engine
- Python 3.10+
- Node.js 18+
- npm

### 1) Start PostgreSQL + PostGIS
From the project root:

```bash
docker compose up -d
```

This starts a PostgreSQL container named agrisense-db on port 5432 using the database named agrisense.

### 2) Prepare the backend
```bash
cd backend
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Then launch the API:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

On startup, the backend creates PostGIS extension and initializes database tables automatically.

### 3) Prepare the frontend
In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The React app serves at:

- http://localhost:5173/

---

## Environment variables

A backend .env file is loaded by the app through pydantic-settings. The project includes defaults in code, but production/local configuration should be kept in environment files.

### Backend settings
```ini
PROJECT_NAME="AgriSense AI Irrigation Advisor"
API_V1_STR="/api"
JWT_SECRET="replace-with-strong-secret"
ACCESS_TOKEN_EXPIRE_MINUTES=10080
DATABASE_URL="postgresql://postgres:postgres@localhost:5432/agrisense"
CORS_ORIGINS=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000"]
GEE_PROJECT_ID="your-gee-project-id"
GEE_CROP_TRAINING_ASSET="your-training-asset-path"
CROP_TRAINING_CSV_PATH="/path/to/training.csv"
BHOONIDHI_USER_ID="your-bhoonidhi-user"
BHOONIDHI_PASSWORD="your-bhoonidhi-password"
```

### Frontend settings
```ini
VITE_API_BASE_URL=http://localhost:8000/api
```

> Notes: crop and moisture analysis depend on external satellite and remote-service configuration. If GEE or Bhoonidhi credentials are not set, those services may fail or degrade gracefully at runtime.

---

## Typical user workflow

1. Open the app at http://localhost:5173/
2. Register a new account or log in
3. Go to Area Selection
4. Use the map to search for a place or select your GPS location
5. Draw a field polygon
6. Validate the field geometry and confirm it
7. Save the field to the database
8. Select the saved field from history or active context
9. Run crop analysis
10. Run moisture stress analysis
11. Review weather insights for that field
12. Continue to irrigation planning based on the combined signals

---

## Operational notes

### Startup checks
The backend runs startup checks for external services in app.main. These include Google Earth Engine status and Bhoonidhi connectivity diagnostics.

### Weather and geospatial service dependency
The app expects weather and satellite data sources to be reachable. In local development, the project will work with the database and UI, but analysis endpoints may require valid remote service configuration to produce full results.

### Geometry validation
Field validation includes checks for:
- coordinate structure validity
- latitude/longitude boundaries
- closed polygons
- self-intersecting or invalid polygons
- PostGIS validation
- area and perimeter calculations
- allowed agricultural extent ranges

---

## Troubleshooting

### Database connection issues
- ensure Docker is running
- run docker compose up -d
- verify that the agrisense database is reachable at localhost:5432

### Backend import or dependency issues
- activate the backend virtual environment
- reinstall dependencies from backend/requirements.txt

### Frontend not loading API calls
- confirm the frontend .env file includes the correct VITE_API_BASE_URL
- ensure the FastAPI backend is running on port 8000

### Crop or moisture analysis failures
- verify valid GEE credentials and configured datasets
- verify Bhoonidhi access configuration if relevant
- check backend logs for external service exceptions

---

## Repository purpose

This repository is intended to serve as a working agricultural intelligence dashboard for field-level geospatial decision support. It combines mapping, validation, persistence, classification, moisture stress modeling, and weather-driven irrigation planning in one project.

The codebase is structured so each stage can be developed and expanded independently while reusing the user and field context saved in the shared PostGIS database.

---

## Development notes

This project is a monorepo with two active application layers:

- backend/ for geospatial modeling and API logic
- frontend/ for user experience and dashboard workflows

The app is designed for iterative development, where additional analysis modules can be added without rewriting the foundation field model or authentication system.
