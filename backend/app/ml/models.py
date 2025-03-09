import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import joblib
import logging
from pathlib import Path

from sklearn.ensemble import RandomForestRegressor, VotingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
import xgboost as xgb

from app.core.config import settings

logger = logging.getLogger(__name__)


class ModelConfig:
    """Configuration for ML models."""

    # Model hyperparameters
    XGBOOST_PARAMS = {
        "n_estimators": 200,
        "max_depth": 6,
        "learning_rate": 0.1,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "random_state": 42,
        "n_jobs": -1,
    }

    RANDOM_FOREST_PARAMS = {
        "n_estimators": 150,
        "max_depth": 10,
        "min_samples_split": 5,
        "min_samples_leaf": 2,
        "random_state": 42,
        "n_jobs": -1,
    }

    LINEAR_PARAMS = {"fit_intercept": True, "n_jobs": -1}

    # Cross-validation settings
    CV_FOLDS = 5
    MIN_TRAIN_SAMPLES = 100

    # Feature selection
    MAX_FEATURES = 50
    FEATURE_IMPORTANCE_THRESHOLD = 0.001


class MLPredictor:
    """Machine learning predictor for FPL player performance."""

    def __init__(self, model_version: str = None):
        self.model_version = model_version or settings.MODEL_VERSION
        self.models = {}
        self.scalers = {}
        self.feature_columns = None
        self.model_dir = Path("models")
        self.model_dir.mkdir(exist_ok=True)

        # Performance metrics
        self.performance_metrics = {}

    def _create_ensemble_model(self) -> VotingRegressor:
        """Create ensemble model combining multiple algorithms."""

        # Individual models
        xgb_model = xgb.XGBRegressor(**ModelConfig.XGBOOST_PARAMS)
        rf_model = RandomForestRegressor(**ModelConfig.RANDOM_FOREST_PARAMS)
        linear_model = LinearRegression(**ModelConfig.LINEAR_PARAMS)

        # Create voting regressor
        ensemble = VotingRegressor(
            [("xgb", xgb_model), ("rf", rf_model), ("linear", linear_model)], n_jobs=-1
        )

        return ensemble

    def _prepare_features(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare features for training or prediction."""

        # Remove non-feature columns
        feature_df = df.copy()
        non_feature_cols = ["player_id", "gameweek", "season", "total_points", "target"]
        for col in non_feature_cols:
            if col in feature_df.columns:
                feature_df = feature_df.drop(columns=[col])

        # Handle missing values
        feature_df = feature_df.fillna(0)

        # Store feature columns for consistency
        if self.feature_columns is None:
            self.feature_columns = feature_df.columns.tolist()
        else:
            # Ensure consistent feature order
            feature_df = feature_df.reindex(columns=self.feature_columns, fill_value=0)

        X = feature_df.values
        y = df["target"].values if "target" in df.columns else None

        return X, y

    def _feature_selection(self, X: np.ndarray, y: np.ndarray) -> List[int]:
        """Select most important features using Random Forest."""

        logger.info("Performing feature selection...")

        # Use Random Forest for feature importance
        rf = RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=-1)
        rf.fit(X, y)

        # Get feature importances
        importances = rf.feature_importances_

        # Select features above threshold
        selected_indices = np.where(
            importances >= ModelConfig.FEATURE_IMPORTANCE_THRESHOLD
        )[0]

        # Limit to max features
        if len(selected_indices) > ModelConfig.MAX_FEATURES:
            # Sort by importance and take top features
            importance_indices = np.argsort(importances)[::-1]
            selected_indices = importance_indices[: ModelConfig.MAX_FEATURES]

        logger.info(
            f"Selected {len(selected_indices)} features from {len(importances)}"
        )

        return selected_indices.tolist()

    def train_points_predictor(self, training_data: pd.DataFrame) -> Dict[str, float]:
        """Train the main points prediction model."""

        logger.info(f"Training points predictor with {len(training_data)} samples")

        if len(training_data) < ModelConfig.MIN_TRAIN_SAMPLES:
            raise ValueError(
                f"Insufficient training data: {len(training_data)} < {ModelConfig.MIN_TRAIN_SAMPLES}"
            )

        # Prepare data
        training_data["target"] = training_data["total_points"]
        X, y = self._prepare_features(training_data)

        # Feature selection
        selected_features = self._feature_selection(X, y)
        X_selected = X[:, selected_features]

        # Create and train scaler
        scaler = RobustScaler()
        X_scaled = scaler.fit_transform(X_selected)

        # Create and train model
        model = self._create_ensemble_model()

        # Time series cross-validation
        tscv = TimeSeriesSplit(n_splits=ModelConfig.CV_FOLDS)
        cv_scores = cross_val_score(
            model, X_scaled, y, cv=tscv, scoring="neg_mean_absolute_error", n_jobs=-1
        )

        # Train on full dataset
        model.fit(X_scaled, y)

        # Store model components
        self.models["points"] = model
        self.scalers["points"] = scaler
        self.feature_columns = [self.feature_columns[i] for i in selected_features]

        # Calculate performance metrics
        y_pred = model.predict(X_scaled)
        metrics = {
            "mae": float(mean_absolute_error(y, y_pred)),
            "rmse": float(np.sqrt(mean_squared_error(y, y_pred))),
            "r2": float(r2_score(y, y_pred)),
            "cv_mae_mean": float(-cv_scores.mean()),
            "cv_mae_std": float(cv_scores.std()),
        }

        self.performance_metrics["points"] = metrics
        logger.info(
            f"Points predictor training complete. MAE: {metrics['mae']:.2f}, R2: {metrics['r2']:.3f}"
        )

        return metrics

    def train_minutes_predictor(self, training_data: pd.DataFrame) -> Dict[str, float]:
        """Train the minutes/starts prediction model."""

        logger.info(f"Training minutes predictor with {len(training_data)} samples")

        # Prepare data - predict probability of playing >60 minutes
        training_data["target"] = (training_data["minutes"] > 60).astype(float)
        X, y = self._prepare_features(training_data)

        # Use same feature selection as points model
        if self.feature_columns is None:
            raise ValueError("Points model must be trained first")

        # _prepare_features already reindexed to self.feature_columns; use X as-is
        X_selected = X

        # Create and train scaler
        scaler = RobustScaler()
        X_scaled = scaler.fit_transform(X_selected)

        # Create and train model (use same ensemble approach)
        model = self._create_ensemble_model()

        # Cross-validation
        tscv = TimeSeriesSplit(n_splits=ModelConfig.CV_FOLDS)
        cv_scores = cross_val_score(
            model, X_scaled, y, cv=tscv, scoring="neg_mean_absolute_error", n_jobs=-1
        )

        # Train on full dataset
        model.fit(X_scaled, y)

        # Store model components
        self.models["minutes"] = model
        self.scalers["minutes"] = scaler

        # Calculate metrics
        y_pred = model.predict(X_scaled)
        y_pred = np.clip(y_pred, 0, 1)  # Ensure probabilities are in [0,1]

        metrics = {
            "mae": float(mean_absolute_error(y, y_pred)),
            "accuracy": float(np.mean((y_pred > 0.5) == y)),
            "cv_mae_mean": float(-cv_scores.mean()),
            "cv_mae_std": float(cv_scores.std()),
        }

        self.performance_metrics["minutes"] = metrics
        logger.info(
            f"Minutes predictor training complete. Accuracy: {metrics['accuracy']:.3f}"
        )

        return metrics

    def train_quantile_models(
        self, training_data: pd.DataFrame
    ) -> Dict[str, Dict[str, float]]:
        """Train quantile regression models for ceiling/floor predictions."""

        logger.info("Training quantile regression models")

        quantiles = {"ceiling": 0.9, "floor": 0.1}
        metrics = {}

        for quantile_name, quantile_value in quantiles.items():
            logger.info(f"Training {quantile_name} model (quantile={quantile_value})")

            # Prepare data
            training_data["target"] = training_data["total_points"]
            X, y = self._prepare_features(training_data)

            # _prepare_features already aligned to self.feature_columns; use X as-is
            X_selected = X

            # Scale features
            scaler = RobustScaler()
            X_scaled = scaler.fit_transform(X_selected)

            # Create XGBoost model with quantile objective
            model = xgb.XGBRegressor(
                objective="reg:quantileerror",
                quantile_alpha=quantile_value,
                n_estimators=150,
                max_depth=6,
                learning_rate=0.1,
                random_state=42,
            )

            # Train model
            model.fit(X_scaled, y)

            # Store model
            self.models[quantile_name] = model
            self.scalers[quantile_name] = scaler

            # Calculate metrics
            y_pred = model.predict(X_scaled)
            quantile_metrics = {
                "mae": float(mean_absolute_error(y, y_pred)),
                "quantile_loss": float(self._quantile_loss(y, y_pred, quantile_value)),
            }

            metrics[quantile_name] = quantile_metrics
            self.performance_metrics[quantile_name] = quantile_metrics

        logger.info("Quantile models training complete")
        return metrics

    def _quantile_loss(
        self, y_true: np.ndarray, y_pred: np.ndarray, quantile: float
    ) -> float:
        """Calculate quantile loss."""
        errors = y_true - y_pred
        loss = np.where(errors >= 0, quantile * errors, (quantile - 1) * errors)
        return np.mean(loss)

    def predict(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """Make predictions for all trained models."""

        if not self.models:
            raise ValueError("No trained models found. Train models first.")

        logger.info(f"Making predictions for {len(features_df)} players")

        # Prepare features
        X, _ = self._prepare_features(features_df)

        # _prepare_features already aligned to self.feature_columns; use X as-is
        X_selected = X

        predictions = features_df[["player_id", "gameweek"]].copy()

        # Points prediction
        if "points" in self.models:
            X_scaled = self.scalers["points"].transform(X_selected)
            points_pred = self.models["points"].predict(X_scaled)
            predictions["predicted_points"] = np.maximum(
                points_pred, 0
            )  # Ensure non-negative

        # Minutes/start probability
        if "minutes" in self.models:
            X_scaled = self.scalers["minutes"].transform(X_selected)
            start_prob = self.models["minutes"].predict(X_scaled)
            predictions["start_probability"] = np.clip(start_prob, 0, 1)
            predictions["predicted_minutes"] = predictions["start_probability"] * 90

        # Quantile predictions
        for quantile_name in ["ceiling", "floor"]:
            if quantile_name in self.models:
                X_scaled = self.scalers[quantile_name].transform(X_selected)
                quantile_pred = self.models[quantile_name].predict(X_scaled)
                predictions[f"{quantile_name}_points"] = np.maximum(quantile_pred, 0)

        # Calculate confidence intervals and variance
        if (
            "predicted_points" in predictions.columns
            and "ceiling_points" in predictions.columns
        ):
            predictions["confidence_lower"] = predictions["predicted_points"] - (
                predictions["predicted_points"] - predictions.get("floor_points", 0)
            )
            predictions["confidence_upper"] = predictions["predicted_points"] + (
                predictions.get("ceiling_points", predictions["predicted_points"])
                - predictions["predicted_points"]
            )

            # Variance estimate
            predictions["variance"] = (
                (
                    predictions.get("ceiling_points", predictions["predicted_points"])
                    - predictions.get("floor_points", predictions["predicted_points"])
                )
                / 4
            ) ** 2

        # Add model metadata
        predictions["model_version"] = self.model_version
        predictions["created_at"] = datetime.utcnow()

        logger.info("Predictions completed")
        return predictions

    def save_models(self, filepath: Optional[str] = None) -> str:
        """Save trained models to disk."""

        if filepath is None:
            filepath = self.model_dir / f"fpl_predictor_{self.model_version}.joblib"

        model_data = {
            "models": self.models,
            "scalers": self.scalers,
            "feature_columns": self.feature_columns,
            "model_version": self.model_version,
            "performance_metrics": self.performance_metrics,
            "saved_at": datetime.utcnow(),
        }

        joblib.dump(model_data, filepath)
        logger.info(f"Models saved to {filepath}")

        return str(filepath)

    def load_models(self, filepath: str) -> None:
        """Load trained models from disk."""

        logger.info(f"Loading models from {filepath}")

        model_data = joblib.load(filepath)

        self.models = model_data["models"]
        self.scalers = model_data["scalers"]
        self.feature_columns = model_data["feature_columns"]
        self.model_version = model_data["model_version"]
        self.performance_metrics = model_data.get("performance_metrics", {})

        logger.info(
            f"Loaded model version {self.model_version} with {len(self.models)} models"
        )

    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance from the points prediction model."""

        if "points" not in self.models:
            return {}

        model = self.models["points"]

        # Get feature importance from ensemble
        if hasattr(model, "estimators_"):
            # For VotingRegressor, average feature importances across estimators
            importances = []
            for estimator in model.estimators_:
                if hasattr(estimator, "feature_importances_"):
                    importances.append(estimator.feature_importances_)

            if importances:
                avg_importance = np.mean(importances, axis=0)
                return dict(zip(self.feature_columns, avg_importance))

        return {}
