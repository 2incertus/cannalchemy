"""Cannalchemy Effect Prediction API.

FastAPI app serving the trained XGBoost effect predictor.

Usage:
    uvicorn cannalchemy.api.app:app --host 0.0.0.0 --port 8421

Endpoints:
    POST /predict      — Predict effects from a chemical profile
    GET  /effects      — List available effects the model can predict
    GET  /features     — List expected input features (molecules)
    GET  /health       — Health check
"""
import logging
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from cannalchemy.models.effect_predictor import EffectPredictor

logger = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = "data/models/v2"
FALLBACK_MODEL_DIR = "data/models/v1"

app = FastAPI(
    title="Cannalchemy Effect Predictor",
    description="Predict cannabis effects from terpene/cannabinoid profiles",
    version="1.0.0",
)

# Global predictor — loaded on startup
_predictor: EffectPredictor | None = None


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


class PredictionResponse(BaseModel):
    """Full prediction response."""
    effects: list[EffectPrediction]
    model_version: str
    n_features_used: int


# Effect category lookup (built from taxonomy at import time)
EFFECT_CATEGORIES: dict[str, str] = {}
try:
    from cannalchemy.data.taxonomy import CANONICAL_EFFECTS
    EFFECT_CATEGORIES = {e["name"]: e["category"] for e in CANONICAL_EFFECTS}
except ImportError:
    pass


@app.post("/predict", response_model=PredictionResponse)
def predict_effects(
    profile: ChemicalProfile,
    threshold: float = 0.3,
    top_n: int = 0,
):
    """Predict effects from a chemical profile.

    Args:
        profile: Chemical composition (terpene/cannabinoid percentages).
        threshold: Minimum probability to include in results (default 0.3).
        top_n: Return only top N effects by probability (0 = all above threshold).
    """
    predictor = _get_predictor()

    # Build feature row matching model's expected columns
    profile_dict = profile.model_dump()
    strain_type = profile_dict.pop("strain_type", "hybrid")

    # Start with chemical features
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

    # Predict
    probs = predictor.predict_proba(X_input)

    # Build response
    effects = []
    for effect_name in probs.columns:
        prob = float(probs.iloc[0][effect_name])
        if prob >= threshold:
            effects.append(EffectPrediction(
                name=effect_name,
                category=EFFECT_CATEGORIES.get(effect_name, "unknown"),
                probability=round(prob, 3),
                predicted=prob >= 0.5,
            ))

    # Sort by probability descending
    effects.sort(key=lambda e: e.probability, reverse=True)

    if top_n > 0:
        effects = effects[:top_n]

    # Determine model version
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
    return {
        "features": predictor.feature_names,
        "count": len(predictor.feature_names),
    }


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
