"""
Model Loading and Caching

Manages loading and caching of trained models to avoid reloading on every request.
"""

import pickle
import os

# Optional imports - these may not be available in all deployments
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

try:
    from keras.models import load_model as keras_load_model
    KERAS_AVAILABLE = True
except ImportError:
    try:
        from tensorflow.keras.models import load_model as keras_load_model
        KERAS_AVAILABLE = True
    except ImportError:
        KERAS_AVAILABLE = False


class ModelManager:
    """
    Manages loading and caching of trained models.

    Loads models once at startup and keeps them in memory for fast predictions.
    """

    def __init__(self):
        self.meta_model = None
        self.trend_model = None
        self.metadata = None
        self._loaded = False

    def load_models(self):
        """Load all trained models into memory."""
        if self._loaded:
            return

        # Import here to avoid circular imports
        from flask import current_app

        try:
            # Load meta-learning model (Keras) - optional
            if KERAS_AVAILABLE:
                meta_path = current_app.config.get('META_MODEL_PATH', 'models/indicator_reliability_model.h5')
                if os.path.exists(meta_path):
                    self.meta_model = keras_load_model(meta_path)
                    current_app.logger.info(f'Loaded meta-learning model from {meta_path}')
                else:
                    current_app.logger.warning(f'Meta model not found at {meta_path}')
            else:
                current_app.logger.warning('Keras not available - skipping meta model')

            # Load trend break model (XGBoost)
            if XGBOOST_AVAILABLE:
                trend_path = current_app.config.get('TREND_MODEL_PATH', 'models/trend_break_model.json')
                if os.path.exists(trend_path):
                    self.trend_model = xgb.XGBClassifier()
                    self.trend_model.load_model(trend_path)
                    current_app.logger.info(f'Loaded trend break model from {trend_path}')
                else:
                    current_app.logger.warning(f'Trend model not found at {trend_path}')
            else:
                current_app.logger.warning('XGBoost not available - skipping trend model')

            # Load metadata
            metadata_path = current_app.config.get('METADATA_PATH', 'models/model_metadata.pkl')
            if os.path.exists(metadata_path):
                with open(metadata_path, 'rb') as f:
                    self.metadata = pickle.load(f)
                current_app.logger.info(f'Loaded model metadata from {metadata_path}')
            else:
                current_app.logger.warning(f'Metadata not found at {metadata_path}')

            self._loaded = True
            current_app.logger.info('Model loading complete')

        except Exception as e:
            current_app.logger.error(f'Error loading models: {e}')
            self._loaded = True  # Mark as loaded to prevent retry loops
            # Don't raise - allow app to start without models

    def get_meta_model(self):
        """Get the meta-learning model (lazy load if needed)."""
        if not self._loaded:
            self.load_models()
        return self.meta_model

    def get_trend_model(self):
        """Get the trend break model (lazy load if needed)."""
        if not self._loaded:
            self.load_models()
        return self.trend_model

    def get_metadata(self):
        """Get model metadata (lazy load if needed)."""
        if not self._loaded:
            self.load_models()
        return self.metadata


# Global model manager instance
model_manager = ModelManager()
