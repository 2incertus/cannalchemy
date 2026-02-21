"""Cannalchemy Effect Prediction API.

FastAPI app serving the trained XGBoost effect predictor and strain data.

Usage:
    uvicorn cannalchemy.api.app:app --host 0.0.0.0 --port 8421

Endpoints:
    POST /predict                — Predict effects from a chemical profile
    GET  /effects                — List available effects the model can predict
    GET  /features               — List expected input features (molecules)
    GET  /health                 — Health check
    GET  /strains                — Search/list strains with compositions
    GET  /strains/{name}         — Full strain profile with predictions and pathways
    GET  /strains/{name}/explain — LLM explanation for strain (cached)
    POST /match                  — Find strains matching desired effects
    GET  /graph                  — Knowledge graph nodes and edges
    GET  /graph/{node_id}        — Subgraph centered on a node
    GET  /stats                  — Data quality statistics
"""
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Optional

import networkx as nx
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from cannalchemy.data.graph import build_knowledge_graph, get_molecule_pathways
from cannalchemy.explain.cache import ExplanationCache
from cannalchemy.explain.llm import LLMClient
from cannalchemy.models.effect_predictor import EffectPredictor

logger = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = "data/models/v2"
FALLBACK_MODEL_DIR = "data/models/v1"
DB_PATH = "data/processed/cannalchemy.db"

app = FastAPI(
    title="Cannalchemy Effect Predictor",
    description="Predict cannabis effects from terpene/cannabinoid profiles",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Globals (lazy-loaded, warmed on startup) ---
_predictor: EffectPredictor | None = None
_db_conn: sqlite3.Connection | None = None
_knowledge_graph: nx.DiGraph | None = None
_prediction_cache: dict | None = None  # {strain_id: (name, type, compositions, probs_dict)}
_cache_ready = threading.Event()  # Set when background cache build completes
_llm_client: LLMClient | None = None
_explanation_cache: ExplanationCache | None = None


@app.on_event("startup")
def _warmup():
    """Start background warmup — API is available immediately, heavy loading happens async."""
    threading.Thread(target=_warmup_all, daemon=True).start()
    print("Warmup: started in background. API accepting requests.")


def _warmup_all():
    """Load model, graph, and prediction cache in background thread."""
    import time
    global _prediction_cache, _llm_client, _explanation_cache
    try:
        t0 = time.time()
        print("Warmup: loading predictor model...")
        _get_predictor()
        print(f"Warmup: model loaded in {time.time()-t0:.1f}s")

        t1 = time.time()
        print("Warmup: building knowledge graph...")
        _get_graph()
        print(f"Warmup: graph built in {time.time()-t1:.1f}s")

        # Initialize LLM client + cache
        _llm_client = LLMClient.from_env()
        if _llm_client:
            print("Warmup: LLM client configured (primary + fallback)")
        else:
            print("Warmup: LLM not configured (no CANNALCHEMY_LLM_PRIMARY_URL)")
        _explanation_cache = ExplanationCache(DB_PATH)

        t2 = time.time()
        print("Warmup: building prediction cache...")
        _prediction_cache = _build_prediction_cache()
        print(f"Warmup: prediction cache ready ({len(_prediction_cache)} strains) in {time.time()-t2:.1f}s")

        print(f"Warmup: all done in {time.time()-t0:.1f}s")
    except Exception as e:
        print(f"Warmup failed (non-fatal): {e}")
        import traceback
        traceback.print_exc()
    finally:
        _cache_ready.set()  # Signal even on failure so endpoints don't hang


def _build_prediction_cache() -> dict:
    """Pre-compute predictions for all ML-ready strains."""
    conn = _get_db()
    predictor = _get_predictor()

    all_comps = conn.execute("""
        SELECT s.id, s.name, s.strain_type,
               m.name as molecule, sc.percentage, m.molecule_type as type
        FROM strains s
        INNER JOIN strain_compositions sc ON sc.strain_id = s.id
        INNER JOIN molecules m ON sc.molecule_id = m.id
        WHERE s.id IN (
            SELECT strain_id FROM strain_compositions
            GROUP BY strain_id HAVING COUNT(DISTINCT molecule_id) >= 3
        )
        ORDER BY s.id
    """).fetchall()

    from itertools import groupby

    strain_data = []
    feature_rows = []
    for sid, group in groupby(all_comps, key=lambda r: r["id"]):
        rows = list(group)
        name = rows[0]["name"]
        strain_type = rows[0]["strain_type"]
        profile_dict = {r["molecule"]: r["percentage"] for r in rows}
        compositions = [
            {"molecule": r["molecule"], "percentage": r["percentage"], "type": r["type"]}
            for r in rows
        ]
        feat_row = _build_feature_row(profile_dict, strain_type, predictor.feature_names)
        feature_rows.append(feat_row)
        strain_data.append((sid, name, strain_type, compositions))

    if not feature_rows:
        return {}

    X_batch = pd.DataFrame(feature_rows)
    probs_df = predictor.predict_proba(X_batch)

    cache = {}
    for i, (sid, name, strain_type, compositions) in enumerate(strain_data):
        probs = {col: float(probs_df.iloc[i][col]) for col in probs_df.columns}
        cache[sid] = (name, strain_type, compositions, probs)

    return cache


def _get_predictor() -> EffectPredictor:
    global _predictor
    if _predictor is None:
        for model_dir in (DEFAULT_MODEL_DIR, FALLBACK_MODEL_DIR):
            if Path(model_dir).exists():
                _predictor = EffectPredictor.load(model_dir)
                logger.info("Loaded model from %s", model_dir)
                break
        if _predictor is None:
            raise RuntimeError(
                f"No model found at {DEFAULT_MODEL_DIR} or {FALLBACK_MODEL_DIR}"
            )
    return _predictor


def _get_db() -> sqlite3.Connection:
    global _db_conn
    if _db_conn is None:
        _db_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    _db_conn.row_factory = sqlite3.Row  # Always restore (graph builder clears it)
    return _db_conn


def _get_graph() -> nx.DiGraph:
    global _knowledge_graph
    if _knowledge_graph is None:
        # Use a separate connection — graph builder expects tuples (no row_factory)
        # and sharing the main conn causes concurrency issues with other endpoints
        graph_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _knowledge_graph = build_knowledge_graph(graph_conn)
        graph_conn.close()
    return _knowledge_graph


# --- Pydantic models ---

class ChemicalProfile(BaseModel):
    """Input chemical profile for prediction."""
    thc: float = Field(0.0, ge=0, le=100, description="THC percentage")
    cbd: float = Field(0.0, ge=0, le=100, description="CBD percentage")
    cbn: float = Field(0.0, ge=0, le=100, description="CBN percentage")
    cbg: float = Field(0.0, ge=0, le=100, description="CBG percentage")
    thcv: float = Field(0.0, ge=0, le=100, description="THCV percentage")
    cbc: float = Field(0.0, ge=0, le=100, description="CBC percentage")
    myrcene: float = Field(0.0, ge=0, le=10, description="Myrcene percentage")
    limonene: float = Field(0.0, ge=0, le=10, description="Limonene percentage")
    caryophyllene: float = Field(0.0, ge=0, le=10, description="Caryophyllene percentage")
    humulene: float = Field(0.0, ge=0, le=10, description="Humulene percentage")
    linalool: float = Field(0.0, ge=0, le=10, description="Linalool percentage")
    pinene: float = Field(0.0, ge=0, le=10, description="Pinene percentage")
    bisabolol: float = Field(0.0, ge=0, le=10, description="Bisabolol percentage")
    terpinolene: float = Field(0.0, ge=0, le=10, description="Terpinolene percentage")
    ocimene: float = Field(0.0, ge=0, le=10, description="Ocimene percentage")
    terpineol: float = Field(0.0, ge=0, le=10, description="Terpineol percentage")
    camphene: float = Field(0.0, ge=0, le=10, description="Camphene percentage")
    fenchol: float = Field(0.0, ge=0, le=10, description="Fenchol percentage")
    borneol: float = Field(0.0, ge=0, le=10, description="Borneol percentage")
    nerolidol: float = Field(0.0, ge=0, le=10, description="Nerolidol percentage")
    farnesene: float = Field(0.0, ge=0, le=10, description="Farnesene percentage")
    valencene: float = Field(0.0, ge=0, le=10, description="Valencene percentage")
    geraniol: float = Field(0.0, ge=0, le=10, description="Geraniol percentage")
    guaiol: float = Field(0.0, ge=0, le=10, description="Guaiol percentage")
    phellandrene: float = Field(0.0, ge=0, le=10, description="Phellandrene percentage")
    carene: float = Field(0.0, ge=0, le=10, description="Carene percentage")
    eucalyptol: float = Field(0.0, ge=0, le=10, description="Eucalyptol percentage")
    strain_type: str = Field("hybrid", description="Strain type: indica, sativa, or hybrid")


class EffectPrediction(BaseModel):
    """Single effect prediction."""
    name: str
    category: str
    probability: float
    predicted: bool
    confidence: str = "medium"  # high/medium/low based on model AUC


class PredictionResponse(BaseModel):
    """Full prediction response."""
    effects: list[EffectPrediction]
    model_version: str
    n_features_used: int


class MatchRequest(BaseModel):
    """Request body for effect matching."""
    effects: list[str]
    type: str = "any"
    limit: int = 50
    explain: bool = False


# Effect category lookup (built from taxonomy at import time)
EFFECT_CATEGORIES: dict[str, str] = {}
try:
    from cannalchemy.data.taxonomy import CANONICAL_EFFECTS
    EFFECT_CATEGORIES = {e["name"]: e["category"] for e in CANONICAL_EFFECTS}
except ImportError:
    pass


def _confidence_label(effect_name: str, predictor: EffectPredictor) -> str:
    """Return 'high', 'medium', or 'low' based on model AUC for this effect."""
    auc = predictor.eval_results.get(effect_name, {}).get("roc_auc", 0)
    if auc >= 0.85:
        return "high"
    elif auc >= 0.75:
        return "medium"
    return "low"


# --- Helper: build prediction from composition dict ---

def _predict_for_composition(
    compositions: list[dict], strain_type: str, predictor: EffectPredictor
) -> list[dict]:
    """Build a ChemicalProfile from DB compositions and predict effects."""
    profile_dict = {}
    for comp in compositions:
        mol_name = comp["molecule"] if isinstance(comp, dict) else comp[0]
        pct = comp["percentage"] if isinstance(comp, dict) else comp[1]
        profile_dict[mol_name] = pct

    row = _build_feature_row(profile_dict, strain_type, predictor.feature_names)
    X_input = pd.DataFrame([row])
    probs = predictor.predict_proba(X_input)

    effects = []
    for effect_name in probs.columns:
        prob = float(probs.iloc[0][effect_name])
        effects.append({
            "name": effect_name,
            "category": EFFECT_CATEGORIES.get(effect_name, "unknown"),
            "probability": round(prob, 3),
            "predicted": prob >= 0.5,
            "confidence": _confidence_label(effect_name, predictor),
        })
    effects.sort(key=lambda e: e["probability"], reverse=True)
    return effects


# --- Existing endpoints ---

@app.post("/predict", response_model=PredictionResponse)
def predict_effects(
    profile: ChemicalProfile,
    threshold: float = 0.3,
    top_n: int = 0,
):
    """Predict effects from a chemical profile."""
    predictor = _get_predictor()
    profile_dict = profile.model_dump()
    strain_type = profile_dict.pop("strain_type", "hybrid")

    row = {}
    for feat in predictor.feature_names:
        if feat in profile_dict:
            row[feat] = profile_dict[feat]
        elif feat == "is_indica":
            row[feat] = 1.0 if strain_type == "indica" else 0.0
        elif feat == "is_sativa":
            row[feat] = 1.0 if strain_type == "sativa" else 0.0
        elif feat == "is_hybrid":
            row[feat] = 1.0 if strain_type == "hybrid" else 0.0
        elif feat == "total_terpenes":
            terp_keys = [
                "bisabolol", "borneol", "camphene", "carene", "caryophyllene",
                "eucalyptol", "farnesene", "fenchol", "geraniol", "guaiol",
                "humulene", "limonene", "linalool", "myrcene", "nerolidol",
                "ocimene", "phellandrene", "pinene", "terpineol", "terpinolene",
                "valencene",
            ]
            row[feat] = sum(profile_dict.get(k, 0) for k in terp_keys)
        elif feat == "total_cannabinoids":
            cann_keys = ["cbc", "cbd", "cbg", "cbn", "thc", "thcv"]
            row[feat] = sum(profile_dict.get(k, 0) for k in cann_keys)
        elif feat == "terpene_diversity":
            terp_keys = [
                "bisabolol", "borneol", "camphene", "carene", "caryophyllene",
                "eucalyptol", "farnesene", "fenchol", "geraniol", "guaiol",
                "humulene", "limonene", "linalool", "myrcene", "nerolidol",
                "ocimene", "phellandrene", "pinene", "terpineol", "terpinolene",
                "valencene",
            ]
            row[feat] = sum(1 for k in terp_keys if profile_dict.get(k, 0) > 0)
        elif feat == "dominant_terpene_pct":
            terp_keys = [
                "bisabolol", "borneol", "camphene", "carene", "caryophyllene",
                "eucalyptol", "farnesene", "fenchol", "geraniol", "guaiol",
                "humulene", "limonene", "linalool", "myrcene", "nerolidol",
                "ocimene", "phellandrene", "pinene", "terpineol", "terpinolene",
                "valencene",
            ]
            row[feat] = max((profile_dict.get(k, 0) for k in terp_keys), default=0)
        elif feat == "thc_cbd_ratio":
            cbd_val = max(profile_dict.get("cbd", 0), 0.01)
            row[feat] = profile_dict.get("thc", 0) / cbd_val
        else:
            row[feat] = 0.0

    X_input = pd.DataFrame([row])
    probs = predictor.predict_proba(X_input)

    effects = []
    for effect_name in probs.columns:
        prob = float(probs.iloc[0][effect_name])
        if prob >= threshold:
            effects.append(EffectPrediction(
                name=effect_name,
                category=EFFECT_CATEGORIES.get(effect_name, "unknown"),
                probability=round(prob, 3),
                predicted=prob >= 0.5,
                confidence=_confidence_label(effect_name, predictor),
            ))

    effects.sort(key=lambda e: e.probability, reverse=True)
    if top_n > 0:
        effects = effects[:top_n]

    model_dir = DEFAULT_MODEL_DIR if Path(DEFAULT_MODEL_DIR).exists() else FALLBACK_MODEL_DIR
    return PredictionResponse(
        effects=effects,
        model_version=Path(model_dir).name,
        n_features_used=len(predictor.feature_names),
    )


@app.get("/effects")
def list_effects():
    """List all effects the model can predict."""
    predictor = _get_predictor()
    effects = []
    for name in sorted(predictor.effect_names):
        cat = EFFECT_CATEGORIES.get(name, "unknown")
        auc = predictor.eval_results.get(name, {}).get("roc_auc")
        effects.append({"name": name, "category": cat, "auc": auc})
    return {"effects": effects, "count": len(effects)}


@app.get("/features")
def list_features():
    """List expected input features."""
    predictor = _get_predictor()
    return {"features": predictor.feature_names, "count": len(predictor.feature_names)}


@app.get("/health")
def health_check():
    """Health check endpoint."""
    try:
        predictor = _get_predictor()
        return {
            "status": "healthy",
            "model_effects": len(predictor.models),
            "model_features": len(predictor.feature_names),
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


# --- New Phase 3 endpoints ---

@app.get("/strains")
def list_strains(
    q: Optional[str] = Query(None, description="Search query (name substring)"),
    type: Optional[str] = Query(None, description="Filter by strain type"),
    limit: int = Query(50, ge=1, le=500, description="Max results"),
):
    """Search and list strains with their chemical compositions."""
    conn = _get_db()

    where_clauses = []
    params = []

    if q:
        where_clauses.append("s.name LIKE ?")
        params.append(f"%{q}%")
    if type and type != "any":
        where_clauses.append("s.strain_type = ?")
        params.append(type)

    # Only include strains that have compositions
    where_clauses.append(
        "s.id IN (SELECT DISTINCT strain_id FROM strain_compositions)"
    )

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    rows = conn.execute(
        f"""SELECT s.id, s.name, s.strain_type, s.description,
                   COALESCE(SUM(er.report_count), 0) as popularity
            FROM strains s
            LEFT JOIN effect_reports er ON er.strain_id = s.id
            WHERE {where_sql}
            GROUP BY s.id
            ORDER BY popularity DESC, s.name
            LIMIT ?""",
        params + [limit],
    ).fetchall()

    strains = []
    for row in rows:
        sid = row["id"]
        comps = conn.execute(
            "SELECT m.name as molecule, sc.percentage, m.molecule_type as type "
            "FROM strain_compositions sc "
            "JOIN molecules m ON sc.molecule_id = m.id "
            "WHERE sc.strain_id = ? ORDER BY sc.percentage DESC",
            (sid,),
        ).fetchall()

        strains.append({
            "id": sid,
            "name": row["name"],
            "strain_type": row["strain_type"],
            "description": row["description"] or "",
            "compositions": [
                {"molecule": c["molecule"], "percentage": c["percentage"], "type": c["type"]}
                for c in comps
            ],
        })

    return {"strains": strains, "count": len(strains)}


@app.get("/strains/{name}")
def get_strain(name: str):
    """Get full strain profile with compositions, predicted effects, and pathways."""
    conn = _get_db()

    row = conn.execute(
        "SELECT id, name, strain_type, description FROM strains WHERE name = ?",
        (name,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Strain '{name}' not found")

    sid = row["id"]

    # Get compositions
    comps = conn.execute(
        "SELECT m.name as molecule, sc.percentage, m.molecule_type as type "
        "FROM strain_compositions sc "
        "JOIN molecules m ON sc.molecule_id = m.id "
        "WHERE sc.strain_id = ? ORDER BY sc.percentage DESC",
        (sid,),
    ).fetchall()

    compositions = [
        {"molecule": c["molecule"], "percentage": c["percentage"], "type": c["type"]}
        for c in comps
    ]

    # Predict effects from compositions
    predicted_effects = []
    try:
        predictor = _get_predictor()
        predicted_effects = _predict_for_composition(
            compositions, row["strain_type"], predictor
        )
    except Exception:
        pass

    # Get pathways for this strain's molecules
    pathways = []
    G = _get_graph()
    for comp in compositions:
        mol_pathways = get_molecule_pathways(G, comp["molecule"])
        pathways.extend(mol_pathways)

    # Get reported effects
    reported_effects = conn.execute(
        "SELECT e.name, e.category, er.report_count "
        "FROM effect_reports er JOIN effects e ON er.effect_id = e.id "
        "WHERE er.strain_id = ? ORDER BY er.report_count DESC",
        (sid,),
    ).fetchall()

    return {
        "name": row["name"],
        "strain_type": row["strain_type"],
        "description": row["description"] or "",
        "compositions": compositions,
        "predicted_effects": predicted_effects,
        "reported_effects": [
            {"name": e["name"], "category": e["category"], "report_count": e["report_count"]}
            for e in reported_effects
        ],
        "pathways": [
            {
                "molecule": p["molecule"],
                "receptor": p["receptor"],
                "ki_nm": p.get("ki_nm"),
                "affinity_score": p.get("affinity_score"),
                "action_type": p.get("action_type", ""),
            }
            for p in pathways
        ],
    }


def _get_model_version() -> str:
    """Get current model version string for cache keying."""
    return Path(DEFAULT_MODEL_DIR).name if Path(DEFAULT_MODEL_DIR).exists() else Path(FALLBACK_MODEL_DIR).name


@app.get("/strains/{name}/explain")
def explain_strain(name: str):
    """Get LLM-generated explanation for a strain's predicted effects."""
    conn = _get_db()
    row = conn.execute(
        "SELECT id, name, strain_type FROM strains WHERE name = ?", (name,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Strain '{name}' not found")

    if not _llm_client:
        return {"explanation": None, "provider": None, "cached": False}

    strain_id = row["id"]
    model_version = _get_model_version()

    # Check cache
    if _explanation_cache:
        cached = _explanation_cache.get(strain_id, "full", model_version)
        if cached:
            return {
                "explanation": cached["content"],
                "provider": cached["llm_provider"],
                "cached": True,
            }

    # Build strain data for prompt
    comps = conn.execute(
        "SELECT m.name as molecule, sc.percentage, m.molecule_type as type "
        "FROM strain_compositions sc JOIN molecules m ON sc.molecule_id = m.id "
        "WHERE sc.strain_id = ? ORDER BY sc.percentage DESC",
        (strain_id,),
    ).fetchall()
    compositions = [{"molecule": c["molecule"], "percentage": c["percentage"], "type": c["type"]} for c in comps]

    predicted_effects = []
    try:
        predictor = _get_predictor()
        predicted_effects = _predict_for_composition(compositions, row["strain_type"], predictor)
    except Exception:
        pass

    G = _get_graph()
    pathways = []
    for comp in compositions:
        pathways.extend(get_molecule_pathways(G, comp["molecule"]))

    strain_data = {
        "name": row["name"],
        "strain_type": row["strain_type"],
        "compositions": compositions,
        "predicted_effects": predicted_effects[:5],
        "pathways": [
            {"molecule": p["molecule"], "receptor": p["receptor"], "ki_nm": p.get("ki_nm")}
            for p in pathways[:5]
        ],
    }

    text, provider = _llm_client.explain_strain(strain_data)
    if text and _explanation_cache:
        _explanation_cache.put(strain_id, "full", model_version, text, provider)

    return {"explanation": text, "provider": provider, "cached": False}


def _build_feature_row(profile_dict: dict, strain_type: str, feature_names: list[str]) -> dict:
    """Build a single feature row dict from a composition dict."""
    row = {}
    cannabinoids = {"thc", "cbd", "cbn", "cbg", "thcv", "cbc"}
    for feat in feature_names:
        if feat in profile_dict:
            row[feat] = profile_dict[feat]
        elif feat == "is_indica":
            row[feat] = 1.0 if strain_type == "indica" else 0.0
        elif feat == "is_sativa":
            row[feat] = 1.0 if strain_type == "sativa" else 0.0
        elif feat == "is_hybrid":
            row[feat] = 1.0 if strain_type == "hybrid" else 0.0
        elif feat == "total_terpenes":
            row[feat] = sum(v for k, v in profile_dict.items() if k not in cannabinoids)
        elif feat == "total_cannabinoids":
            row[feat] = sum(profile_dict.get(k, 0) for k in cannabinoids)
        elif feat == "terpene_diversity":
            row[feat] = sum(1 for k, v in profile_dict.items() if k not in cannabinoids and v > 0)
        elif feat == "dominant_terpene_pct":
            terp_vals = [v for k, v in profile_dict.items() if k not in cannabinoids]
            row[feat] = max(terp_vals, default=0)
        elif feat == "thc_cbd_ratio":
            row[feat] = profile_dict.get("thc", 0) / max(profile_dict.get("cbd", 0), 0.01)
        else:
            row[feat] = 0.0
    return row


@app.post("/match")
def match_strains(request: MatchRequest):
    """Find strains whose predicted effects best match desired effects (uses pre-computed cache)."""
    global _prediction_cache
    if _prediction_cache is None:
        # Wait briefly for background warmup, then fall back to synchronous build
        _cache_ready.wait(timeout=10)
        if _prediction_cache is None:
            _prediction_cache = _build_prediction_cache()
            _cache_ready.set()

    predictor = _get_predictor()
    results = []
    for sid, (name, strain_type, compositions, probs) in _prediction_cache.items():
        if request.type and request.type != "any" and strain_type != request.type:
            continue

        matching_probs = [probs.get(eff, 0) for eff in request.effects]
        score = sum(matching_probs) / len(matching_probs) if matching_probs else 0
        top_effects = []
        for effect_name, p in probs.items():
            if p >= 0.3:
                top_effects.append({
                    "name": effect_name,
                    "category": EFFECT_CATEGORIES.get(effect_name, "unknown"),
                    "probability": round(p, 3),
                    "predicted": p >= 0.5,
                    "confidence": _confidence_label(effect_name, predictor),
                })
        top_effects.sort(key=lambda e: e["probability"], reverse=True)

        results.append({
            "name": name,
            "strain_type": strain_type,
            "score": round(score, 3),
            "compositions": compositions,
            "top_effects": top_effects[:5],
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    results = results[: request.limit]

    # Generate summaries if requested
    if request.explain and _llm_client:
        conn = _get_db()
        model_version = _get_model_version()
        for result in results:
            # Look up strain_id from name
            strain_row = conn.execute(
                "SELECT id FROM strains WHERE name = ?", (result["name"],)
            ).fetchone()
            if not strain_row:
                continue
            sid = strain_row["id"]

            # Check cache first
            if _explanation_cache:
                cached = _explanation_cache.get(sid, "summary", model_version)
                if cached:
                    result["summary"] = cached["content"]
                    continue

            # Generate summary
            strain_data = {
                "name": result["name"],
                "strain_type": result["strain_type"],
                "compositions": result["compositions"],
                "predicted_effects": result["top_effects"][:3],
                "pathways": [],
            }
            text, provider = _llm_client.summarize_strain(strain_data)
            if text:
                result["summary"] = text
                if _explanation_cache:
                    _explanation_cache.put(sid, "summary", model_version, text, provider)

    return {"strains": results, "count": len(results)}


@app.get("/graph")
def get_graph():
    """Get the knowledge graph as nodes and edges (excludes strain nodes)."""
    G = _get_graph()

    nodes = []
    for node_id, data in G.nodes(data=True):
        node_type = data.get("node_type", "unknown")
        # Exclude strain nodes (too many for visualization)
        if node_type == "strain":
            continue
        nodes.append({
            "id": node_id,
            "name": data.get("name", ""),
            "type": node_type,
            **{k: v for k, v in data.items() if k not in ("node_type", "db_id")},
        })

    edges = []
    for source, target, data in G.edges(data=True):
        src_type = G.nodes[source].get("node_type", "")
        tgt_type = G.nodes[target].get("node_type", "")
        # Exclude edges involving strain nodes
        if src_type == "strain" or tgt_type == "strain":
            continue
        edges.append({
            "source": source,
            "target": target,
            "type": data.get("edge_type", ""),
            **{k: v for k, v in data.items() if k != "edge_type"},
        })

    return {"nodes": nodes, "edges": edges}


@app.get("/graph/{node_id:path}")
def get_graph_node(node_id: str):
    """Get a specific node and its connections."""
    G = _get_graph()

    if not G.has_node(node_id):
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")

    data = G.nodes[node_id]
    node = {
        "id": node_id,
        "name": data.get("name", ""),
        "type": data.get("node_type", ""),
        **{k: v for k, v in data.items() if k not in ("node_type", "db_id")},
    }

    connected = []
    # Outgoing edges
    for _, target, edge_data in G.edges(node_id, data=True):
        target_data = G.nodes[target]
        connected.append({
            "node": {
                "id": target,
                "name": target_data.get("name", ""),
                "type": target_data.get("node_type", ""),
            },
            "edge_type": edge_data.get("edge_type", ""),
            "direction": "outgoing",
        })
    # Incoming edges
    for source, _, edge_data in G.in_edges(node_id, data=True):
        source_data = G.nodes[source]
        connected.append({
            "node": {
                "id": source,
                "name": source_data.get("name", ""),
                "type": source_data.get("node_type", ""),
            },
            "edge_type": edge_data.get("edge_type", ""),
            "direction": "incoming",
        })

    return {"node": node, "connected": connected}


@app.get("/stats")
def get_stats():
    """Get data quality statistics."""
    conn = _get_db()

    total_strains = conn.execute("SELECT COUNT(*) FROM strains").fetchone()[0]
    ml_ready = conn.execute(
        "SELECT COUNT(DISTINCT s.id) FROM strains s "
        "JOIN strain_compositions sc ON s.id = sc.strain_id "
        "JOIN effect_reports er ON s.id = er.strain_id"
    ).fetchone()[0]
    molecules = conn.execute("SELECT COUNT(*) FROM molecules").fetchone()[0]
    effects = conn.execute("SELECT COUNT(*) FROM effects").fetchone()[0]
    receptors = conn.execute("SELECT COUNT(*) FROM receptors").fetchone()[0]

    # Source breakdown
    sources = conn.execute(
        "SELECT source, COUNT(*) as count FROM effect_reports GROUP BY source"
    ).fetchall()

    # Effect report counts per effect
    effect_counts = conn.execute(
        "SELECT e.name, e.category, SUM(er.report_count) as total_reports "
        "FROM effect_reports er JOIN effects e ON er.effect_id = e.id "
        "GROUP BY e.name ORDER BY total_reports DESC"
    ).fetchall()

    # Model performance (if available)
    model_performance = []
    try:
        predictor = _get_predictor()
        for name in sorted(predictor.effect_names):
            auc = predictor.eval_results.get(name, {}).get("roc_auc")
            if auc:
                model_performance.append({
                    "name": name,
                    "category": EFFECT_CATEGORIES.get(name, "unknown"),
                    "auc": round(auc, 3),
                })
    except Exception:
        pass

    return {
        "total_strains": total_strains,
        "ml_ready_strains": ml_ready,
        "molecules": molecules,
        "effects": effects,
        "receptors": receptors,
        "sources": [{"source": s["source"], "count": s["count"]} for s in sources],
        "effect_counts": [
            {"name": e["name"], "category": e["category"], "total_reports": e["total_reports"]}
            for e in effect_counts
        ],
        "model_performance": model_performance,
    }
