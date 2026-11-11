# AgriSense Quick Start Guide

Follow these steps to run the complete AgriSense AI Irrigation Advisor application on your local machine.

---

## 🛠️ Step 1: Start the Database (PostgreSQL + PostGIS)

Ensure you have **Docker Desktop** running, then execute the following command from the project root:

```bash
docker compose up -d
```

*This spins up a containerized PostgreSQL database configured with the PostGIS spatial extensions, mapped to host port `5432`.*

---

## 🐍 Step 2: Start the FastAPI Backend

1. Navigate to the `backend` folder:
   ```bash
   cd backend
   ```
2. Activate the pre-configured virtual environment:
   * **Windows (PowerShell)**:
     ```powershell
     .venv\Scripts\Activate.ps1
     ```
   * **Linux / MacOS**:
     ```bash
     source .venv/bin/activate
     ```
3. Install backend dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the ASGI web server:
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```



*The backend will automatically initialize database tables and PostGIS extensions. It runs on `http://localhost:8000` (or the custom port you configured).*
* **Swagger API Documentation**: `http://localhost:8000/docs`

---

## 🔍 Editor & Linting Support (Pyrefly)

If you are using the **Pyrefly** type checker / language server in your IDE, it may fail to resolve package imports (such as `import ee` for Google Earth Engine) if it defaults to your system Python interpreter.

To fix this, we use config files to instruct Pyrefly to use the python interpreter inside your local virtual environment (`.venv`):
- [Workspace Root pyrefly.toml](file:///c:/Projects/crop/pyrefly.toml)
- [Backend pyrefly.toml](file:///c:/Projects/crop/backend/pyrefly.toml)

If your IDE doesn't pick up the environment automatically, ensure these files are present, or restart the language server.

---

## ⚡ Step 3: Start the Vite + React Frontend

1. Open a new terminal window and navigate to the `frontend` folder:
   ```bash
   cd frontend
   ```
2. Run the Vite development server:
   ```bash
   npm run dev
   ```

*The frontend web client will start on `http://localhost:5173/`.*

---

## 🧪 Testing the Phase 1 Workflow

1. Open **`http://localhost:5173/`** in your browser.
2. You will be redirected to the Login page. Click **Register here** to create an account.
3. Once registered, log in to access the AgriSense Dashboard.
4. Use the search bar to find a location or click **Use My Location** (GPS).
5. Draw a field boundary using the **Draw polygon** tool on the Leaflet Map.
6. Verify that spatial attributes (Area, Centroid Coordinates, Perimeter, and Location details) are successfully calculated and geocoded.
7. Click **Confirm Field** to persist your field boundary in the database and generate a unique Field ID (e.g. `FLD-2026-000001`).
8. Navigate to the **History** tab to retrieve your registered fields.
