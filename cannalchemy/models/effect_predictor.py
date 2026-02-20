"""XGBoost multi-label effect predictor.

Trains one XGBoost classifier per effect (binary relevance approach),
evaluates with stratified cross-validation, and provides calibrated
probability predictions + feature importance.

Usage:
    from cannalchemy.models.dataset import build_dataset
    from cannalchemy.models.effect_predictor import EffectPredictor

    X, y, meta = build_dataset("data/processed/cannalchemy.db")
    predictor = EffectPredictor()
    results = predictor.train(X, y)
    predictions = predictor.predict(X_new)
"""
import json
import logging
import pickle  # Required: XGBoost/sklearn models need binary serialization
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold
from xgboost import XGBClassifier

logger = logging.getLogger(__name__)

DEFAULT_XGB_PARAMS = {
    "n_estimators": 200,
    "max_depth": 5,
    "learning_rate": 0.1,
    "min_child_weight": 5,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "random_state": 42,
    "n_jobs": -1,
    "eval_metric": "logloss",
}


class EffectPredictor:
    """Multi-label effect predictor using per-effect XGBoost classifiers."""

    def __init__(self, xgb_params: dict | None = None, calibrate: bool = True):
        """Initialize predictor.

        Args:
            xgb_params: Override XGBoost hyperparameters.
            calibrate: Apply Platt scaling for calibrated probabilities.
        """
        self.xgb_params = {**DEFAULT_XGB_PARAMS, **(xgb_params or {})}
        self.calibrate = calibrate
        self.models: dict[str, XGBClassifier | CalibratedClassifierCV] = {}
        self.feature_names: list[str] = []
        self.effect_names: list[str] = []
        self.eval_results: dict[str, dict] = {}

    def train(
        self,
        X: pd.DataFrame,
        y: pd.DataFrame,
        n_folds: int = 5,
    ) -> dict:
        """Train per-effect classifiers with cross-validation evaluation.

        Args:
            X: Feature matrix (strain_id x molecule).
            y: Label matrix (strain_id x effect), binary 0/1.
            n_folds: Number of CV folds for evaluation.

        Returns:
            Summary dict with per-effect and aggregate metrics.
        """
        self.feature_names = list(X.columns)
        self.effect_names = list(y.columns)

        X_arr = X.values.astype(np.float32)
        summary = {"per_effect": {}, "aggregate": {}}
        all_aucs = []

        for effect_name in self.effect_names:
            y_col = y[effect_name].values
            n_pos = int(y_col.sum())
            n_neg = len(y_col) - n_pos

            if n_pos < n_folds:
                logger.warning(
                    "Skipping %s: only %d positive samples (need >= %d for CV)",
                    effect_name, n_pos, n_folds,
                )
                continue

            # Cross-validation evaluation
            cv_metrics = self._cross_validate(X_arr, y_col, n_folds, n_pos, n_neg)

            # Train final model on all data
            scale = n_neg / max(n_pos, 1)
            params = {**self.xgb_params, "scale_pos_weight": scale}
            model = XGBClassifier(**params)
            model.fit(X_arr, y_col)

            if self.calibrate and n_pos >= 2 * n_folds:
                cal_model = CalibratedClassifierCV(model, cv=n_folds, method="sigmoid")
                cal_model.fit(X_arr, y_col)
                self.models[effect_name] = cal_model
            else:
                self.models[effect_name] = model

            self.eval_results[effect_name] = cv_metrics
            summary["per_effect"][effect_name] = cv_metrics
            if cv_metrics.get("roc_auc") is not None:
                all_aucs.append(cv_metrics["roc_auc"])

            logger.info(
                "%-20s  AUC=%.3f  F1=%.3f  P=%.3f  R=%.3f  (pos=%d)",
                effect_name,
                cv_metrics.get("roc_auc", 0),
                cv_metrics.get("f1", 0),
                cv_metrics.get("precision", 0),
                cv_metrics.get("recall", 0),
                n_pos,
            )

        # Aggregate metrics
        trained = [e for e in self.effect_names if e in self.models]
        summary["aggregate"] = {
            "effects_trained": len(trained),
            "effects_skipped": len(self.effect_names) - len(trained),
            "mean_roc_auc": float(np.mean(all_aucs)) if all_aucs else 0.0,
            "median_roc_auc": float(np.median(all_aucs)) if all_aucs else 0.0,
            "min_roc_auc": float(np.min(all_aucs)) if all_aucs else 0.0,
            "max_roc_auc": float(np.max(all_aucs)) if all_aucs else 0.0,
        }

        logger.info(
            "Training complete: %d effects | mean AUC=%.3f | median AUC=%.3f",
            len(trained), summary["aggregate"]["mean_roc_auc"],
            summary["aggregate"]["median_roc_auc"],
        )

        return summary

    def _cross_validate(
        self,
        X: np.ndarray,
        y: np.ndarray,
        n_folds: int,
        n_pos: int,
        n_neg: int,
    ) -> dict:
        """Run stratified k-fold cross-validation for one effect."""
        skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
        scale = n_neg / max(n_pos, 1)

        fold_preds = np.zeros(len(y), dtype=np.float64)
        fold_binary = np.zeros(len(y), dtype=int)

        for train_idx, val_idx in skf.split(X, y):
            params = {**self.xgb_params, "scale_pos_weight": scale}
            fold_model = XGBClassifier(**params)
            fold_model.fit(X[train_idx], y[train_idx])
            fold_preds[val_idx] = fold_model.predict_proba(X[val_idx])[:, 1]
            fold_binary[val_idx] = fold_model.predict(X[val_idx])

        metrics = {
            "n_positive": n_pos,
            "n_negative": n_neg,
            "f1": float(f1_score(y, fold_binary, zero_division=0)),
            "precision": float(precision_score(y, fold_binary, zero_division=0)),
            "recall": float(recall_score(y, fold_binary, zero_division=0)),
        }

        # ROC AUC needs both classes in predictions
        if len(np.unique(y)) > 1:
            metrics["roc_auc"] = float(roc_auc_score(y, fold_preds))
        else:
            metrics["roc_auc"] = None

        return metrics

    def predict(self, X: pd.DataFrame, threshold: float = 0.5) -> pd.DataFrame:
        """Predict effects for new strains.

        Args:
            X: Feature matrix with same columns as training data.
            threshold: Probability threshold for binary predictions.

        Returns:
            DataFrame with effect names as columns, values 0/1.
        """
        probs = self.predict_proba(X)
        return (probs >= threshold).astype(int)

    def predict_proba(self, X: pd.DataFrame) -> pd.DataFrame:
        """Predict effect probabilities for new strains.

        Args:
            X: Feature matrix with same columns as training data.

        Returns:
            DataFrame with effect names as columns, values [0, 1].
        """
        # Align columns
        X_aligned = X.reindex(columns=self.feature_names, fill_value=0.0)
        X_arr = X_aligned.values.astype(np.float32)

        probs = {}
        for effect_name, model in self.models.items():
            probs[effect_name] = model.predict_proba(X_arr)[:, 1]

        return pd.DataFrame(probs, index=X.index)

    def feature_importance(self, top_n: int = 10) -> dict[str, list[tuple[str, float]]]:
        """Get top feature importances per effect.

        Args:
            top_n: Number of top features to return per effect.

        Returns:
            Dict mapping effect name -> list of (feature_name, importance) tuples.
        """
        result = {}
        for effect_name, model in self.models.items():
            # Unwrap calibrated model if needed
            if isinstance(model, CalibratedClassifierCV):
                base = model.estimator
            else:
                base = model

            importances = base.feature_importances_
            indices = np.argsort(importances)[::-1][:top_n]
            result[effect_name] = [
                (self.feature_names[i], float(importances[i]))
                for i in indices
                if importances[i] > 0
            ]

        return result

    def save(self, path: str) -> None:
        """Save trained predictor to disk.

        Pickle is required for XGBoost/sklearn model serialization -
        these objects cannot be represented in JSON or other text formats.

        Args:
            path: Directory path to save model files.
        """
        save_dir = Path(path)
        save_dir.mkdir(parents=True, exist_ok=True)

        # Save models (pickle required for sklearn/xgboost objects)
        with open(save_dir / "models.pkl", "wb") as f:
            pickle.dump(self.models, f)

        # Save metadata as JSON
        meta = {
            "feature_names": self.feature_names,
            "effect_names": self.effect_names,
            "xgb_params": {
                k: v for k, v in self.xgb_params.items()
                if isinstance(v, (str, int, float, bool, type(None)))
            },
            "calibrate": self.calibrate,
            "eval_results": self.eval_results,
        }
        with open(save_dir / "metadata.json", "w") as f:
            json.dump(meta, f, indent=2)

        logger.info("Saved predictor to %s (%d effects)", path, len(self.models))

    @classmethod
    def load(cls, path: str) -> "EffectPredictor":
        """Load a trained predictor from disk.

        Only load models from trusted sources - pickle deserialization
        can execute arbitrary code.

        Args:
            path: Directory path containing saved model files.

        Returns:
            Loaded EffectPredictor instance.
        """
        load_dir = Path(path)

        with open(load_dir / "metadata.json") as f:
            meta = json.load(f)

        predictor = cls(
            xgb_params=meta.get("xgb_params"),
            calibrate=meta.get("calibrate", True),
        )
        predictor.feature_names = meta["feature_names"]
        predictor.effect_names = meta["effect_names"]
        predictor.eval_results = meta.get("eval_results", {})

        with open(load_dir / "models.pkl", "rb") as f:
            predictor.models = pickle.load(f)

        logger.info("Loaded predictor from %s (%d effects)", path, len(predictor.models))
        return predictor
