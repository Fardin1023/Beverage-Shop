import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.routers import customer, shopkeeper, supplier, company, db_viewer, catalog

app = FastAPI(
    title="Daily Drop Beverage Shop API",
    description="High-performance backend API with MySQL 8.0 connection pooling for Daily Drop counter, suppliers, and loyalty system.",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(customer.router)
app.include_router(shopkeeper.router)
app.include_router(supplier.router)
app.include_router(company.router)
app.include_router(db_viewer.router)
app.include_router(catalog.router)

# Mount frontend static directory if exists
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="frontend_static")

@app.get("/")
def root():
    return {
        "service": "Daily Drop Beverage Shop API",
        "status": "online",
        "docs_url": "/docs",
        "frontend_portals": {
            "counter": "/static/counter/index.html",
            "supplier": "/static/supplier/index.html",
            "customer": "/static/customer/index.html",
            "portal": "/static/index.html"
        }
    }
