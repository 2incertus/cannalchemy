"""Tests for the XGBoost effect predictor."""
import numpy as np
import pandas as pd
import pytest

from cannalchemy.models.effect_predictor import EffectPredictor


@pytest.fixture
def synthetic_data():
    """Create synthetic dataset for predictor testing.

    100 samples, 5 features, 3 effects with different correlations.
    """
    rng = np.random.RandomState(42)
    n = 100

    # Features: 5 molecules
    X = pd.DataFrame({
        "myrcene": rng.uniform(0, 1, n),
        "limonene": rng.uniform(0, 1, n),
        "thc": rng.uniform(10, 30, n),
        "cbd": rng.uniform(0, 15, n),
        "pinene": rng.uniform(0, 0.5, n),
    }, index=range(1, n + 1))
    X.index.name = "strain_id"

    # Labels: 3 effects correlated with features
    y = pd.DataFrame(index=X.index)
    y.index.name = "strain_id"
    # relaxed: correlates with high myrcene
    y["relaxed"] = (X["myrcene"] > 0.5).astype(int)
    # energetic: correlates with high limonene
    y["energetic"] = (X["limonene"] > 0.6).astype(int)
    # pain: correlates with high thc + cbd
    y["pain"] = ((X["thc"] + X["cbd"]) > 30).astype(int)

    return X, y


class TestTraining:
    def test_train_returns_summary(self, synthetic_data):
        X, y = synthetic_data
        predictor = EffectPredictor(calibrate=False)
        summary = predictor.train(X, y, n_folds=3)
        assert "per_effect" in summary
        assert "aggregate" in summary
        assert summary["aggregate"]["effects_trained"] == 3

    def test_models_created(self, synthetic_data):
        X, y = synthetic_data
        predictor = EffectPredictor(calibrate=False)
        predictor.train(X, y, n_folds=3)
        assert len(predictor.models) == 3
        assert set(predictor.models.keys()) == {"relaxed", "energetic", "pain"}

    def test_auc_reasonable(self, synthetic_data):
        X, y = synthetic_data
        predictor = EffectPredictor(calibrate=False)
        summary = predictor.train(X, y, n_folds=3)
        # With clear feature-label correlations, AUC should be well above 0.5
        assert summary["aggregate"]["mean_roc_auc"] > 0.7

    def test_calibrated_training(self, synthetic_data):
        X, y = synthetic_data
        predictor = EffectPredictor(calibrate=True)
        predictor.train(X, y, n_folds=3)
        assert len(predictor.models) == 3


class TestPrediction:
    def test_predict_shape(self, synthetic_data):
        X, y = synthetic_data
        predictor = EffectPredictor(calibrate=False)
        predictor.train(X, y, n_folds=3)
        preds = predictor.predict(X)
        assert preds.shape == (100, 3)

    def test_predict_binary(self, synthetic_data):
        X, y = synthetic_data
        predictor = EffectPredictor(calibrate=False)
        predictor.train(X, y, n_folds=3)
        preds = predictor.predict(X)
        assert set(preds.values.flatten()) <= {0, 1}

    def test_predict_proba_range(self, synthetic_data):
        X, y = synthetic_data
        predictor = EffectPredictor(calibrate=False)
        predictor.train(X, y, n_folds=3)
        probs = predictor.predict_proba(X)
        assert (probs.values >= 0).all()
        assert (probs.values <= 1).all()

    def test_predict_with_missing_features(self, synthetic_data):
        X, y = synthetic_data
        predictor = EffectPredictor(calibrate=False)
        predictor.train(X, y, n_folds=3)
        # New data with only 3 of 5 features
        X_new = pd.DataFrame({
            "myrcene": [0.8],
            "thc": [25.0],
            "cbd": [5.0],
        }, index=[999])
        probs = predictor.predict_proba(X_new)
        assert probs.shape == (1, 3)


class TestFeatureImportance:
    def test_importance_returned(self, synthetic_data):
        X, y = synthetic_data
        predictor = EffectPredictor(calibrate=False)
        predictor.train(X, y, n_folds=3)
        imp = predictor.feature_importance(top_n=3)
        assert len(imp) == 3
        for effect, features in imp.items():
            assert len(features) <= 3
            for name, score in features:
                assert isinstance(name, str)
                assert score > 0

    def test_top_feature_plausible(self, synthetic_data):
        X, y = synthetic_data
        predictor = EffectPredictor(calibrate=False)
        predictor.train(X, y, n_folds=3)
        imp = predictor.feature_importance(top_n=1)
        # relaxed should be driven by myrcene
        assert imp["relaxed"][0][0] == "myrcene"


class TestSaveLoad:
    def test_round_trip(self, synthetic_data, tmp_path):
        X, y = synthetic_data
        predictor = EffectPredictor(calibrate=False)
        predictor.train(X, y, n_folds=3)
        original_probs = predictor.predict_proba(X)

        # Save
        save_path = str(tmp_path / "model")
        predictor.save(save_path)

        # Load
        loaded = EffectPredictor.load(save_path)
        loaded_probs = loaded.predict_proba(X)

        # Predictions should be identical
        pd.testing.assert_frame_equal(original_probs, loaded_probs)

    def test_metadata_preserved(self, synthetic_data, tmp_path):
        X, y = synthetic_data
        predictor = EffectPredictor(calibrate=False)
        predictor.train(X, y, n_folds=3)

        save_path = str(tmp_path / "model")
        predictor.save(save_path)
        loaded = EffectPredictor.load(save_path)

        assert loaded.feature_names == predictor.feature_names
        assert loaded.effect_names == predictor.effect_names
        assert len(loaded.eval_results) == len(predictor.eval_results)
