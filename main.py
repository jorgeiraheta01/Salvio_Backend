from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.database import engine
from app.middleware.maintenance import MaintenanceModeMiddleware
from app.middleware.tenant import TenantIsolationMiddleware
from app.modules.platform_admin.router import router as platform_admin_router
from app.modules.tenants.router import router as tenants_router
from app.routers import appointments, auth, billing, catalogs, clinical, clinical_notes, diagnoses, encounters, imaging, lab, orders, patients, platform_settings, prescriptions, referrals, users, vital_signs, wa

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"^http://[a-z0-9_-]+\.localhost:3000$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TenantIsolationMiddleware)
app.add_middleware(MaintenanceModeMiddleware)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(users.tenant_router)
app.include_router(patients.router)
app.include_router(appointments.router)
app.include_router(encounters.router)
app.include_router(clinical.router)
app.include_router(clinical_notes.router)
app.include_router(diagnoses.router)
app.include_router(vital_signs.router)
app.include_router(orders.router)
app.include_router(prescriptions.router)
app.include_router(lab.router)
app.include_router(imaging.router)
app.include_router(referrals.router)
app.include_router(billing.router)
app.include_router(wa.router)
app.include_router(catalogs.router)
app.include_router(platform_settings.router)
app.include_router(platform_settings.public_router)
app.include_router(tenants_router)
app.include_router(platform_admin_router)

@app.get("/")
def root():
    return {"message": "Salvio API running", "status": "ok"}
