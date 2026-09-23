from pathlib import Path
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "processed"


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="DBLP Dashboard API",
    description="Backend API for the DBLP publication dashboard",
    version="1.0.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# HELPER
# ============================================================

def load_json(filename: str):

    path = PROCESSED_DIR / filename

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Processed data file not found: {filename}"
        )

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "message": "DBLP Dashboard API is running"
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/api/health")
def health():

    return {
        "status": "healthy"
    }


# ============================================================
# KPIs
# ============================================================

@app.get("/api/kpis")
def get_kpis():

    return load_json("kpis.json")


# ============================================================
# PUBLICATIONS BY YEAR
# ============================================================

@app.get("/api/publications/yearly")
def get_yearly_publications():

    return load_json("yearly_publications.json")


# ============================================================
# PUBLICATION TYPES
# ============================================================

@app.get("/api/publications/types")
def get_publication_types():

    return load_json("publication_types.json")


# ============================================================
# PUBLICATION TYPES BY YEAR
# ============================================================

@app.get("/api/publications/types-by-year")
def get_publication_types_by_year():

    return load_json("publication_types_by_year.json")


# ============================================================
# AUTHOR DISTRIBUTION
# ============================================================

@app.get("/api/authors/distribution")
def get_author_distribution():

    return load_json("author_distribution.json")


# ============================================================
# COLLABORATION
# ============================================================

@app.get("/api/collaboration")
def get_collaboration():

    return load_json("collaboration.json")


# ============================================================
# VENUES
# ============================================================

@app.get("/api/venues")
def get_venues():

    return load_json("venues.json")


# ============================================================
# DATA QUALITY
# ============================================================

@app.get("/api/data-quality")
def get_data_quality():

    return load_json("missing_data.json")