"""
ML Models Module
=================
Machine learning models for securities prediction.

MODEL SELECTION GUIDE:
═══════════════════════════════════════════════════════════════════════════════
Prediction Goal              | Recommended Model      | Why
═══════════════════════════════════════════════════════════════════════════════
Price direction (up/down)    | XGBoost or LightGBM   | Handles tabular data, feature importance
Trend break probability      | XGBoost or LightGBM   | Classification, good with indicators
Future price value           | LSTM/GRU              | Time series regression
Indicator reliability        | Dense NN (Keras)       | Multi-output regression
═══════════════════════════════════════════════════════════════════════════════

GRADIENT BOOSTING (XGBoost/LightGBM) - RECOMMENDED FOR INDICATOR-BASED PREDICTION:
- Best for tabular financial data
- Less sensitive to feature scaling than neural networks
- Provides feature importance for indicator evaluation
- Usually outperforms RandomForest for financial data

NEURAL NETWORKS (LSTM/Dense):
- LSTM: Best for pure time-series with temporal dependencies
- Dense: Good for meta-learning (predicting indicator accuracy)
- Requires more data and careful tuning

This module contains:
- XGBoost model (recommended for trend/direction prediction)
- LightGBM model (faster, often comparable to XGBoost)
- LSTM model for time series
- Dense neural network for indicator accuracy prediction
- Model training and evaluation functions

Usage:
    from src.models import create_xgboost_model, create_lightgbm_model, train_trend_model

    # For trend break prediction (RECOMMENDED)
    model, metrics = train_xgboost_model(X_train, y_train, X_test, y_test)

    # Or use LightGBM (faster training)
    model, metrics = train_lightgbm_model(X_train, y_train, X_test, y_test)

    # For time series
    model = create_lstm_model(input_shape=(60, 10))
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional, Dict, Any
import os
import warnings

# Suppress TensorFlow warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
warnings.filterwarnings('ignore')


# ════════════════════════════════════════════════════════════════════════════
# KERAS/TENSORFLOW MODELS
# ════════════════════════════════════════════════════════════════════════════

def create_lstm_model(
    input_shape: Tuple[int, int],
    units: int = 50,
    dropout: float = 0.2
):
    """
    Create LSTM model for time series prediction.

    Args:
        input_shape: Shape of input data (timesteps, features)
        units: Number of LSTM units (default: 50)
        dropout: Dropout rate (default: 0.2)

    Returns:
        Compiled Keras model

    Example:
        >>> model = create_lstm_model(input_shape=(60, 10))
        >>> model.summary()
    """
    try:
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import LSTM, Dense, Dropout
        from tensorflow.keras.optimizers import Adam
    except ImportError:
        raise ImportError("TensorFlow not installed. Run: pip install tensorflow")

    model = Sequential([
        LSTM(units, activation='relu', return_sequences=True, input_shape=input_shape),
        Dropout(dropout),
        LSTM(units, activation='relu'),
        Dropout(dropout),
        Dense(25, activation='relu'),
        Dense(1)
    ])

    model.compile(optimizer=Adam(learning_rate=0.001), loss='mse', metrics=['mae'])

    return model


def create_dense_model(
    input_dim: int,
    hidden_layers: list = [64, 32],
    dropout: float = 0.2,
    output_activation: str = 'sigmoid'
):
    """
    Create dense neural network for classification/regression.

    Args:
        input_dim: Number of input features
        hidden_layers: List of hidden layer sizes
        dropout: Dropout rate
        output_activation: Output layer activation ('sigmoid' for binary, 'linear' for regression)

    Returns:
        Compiled Keras model

    Example:
        >>> model = create_dense_model(input_dim=20, hidden_layers=[64, 32])
    """
    try:
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import Dense, Dropout
        from tensorflow.keras.optimizers import Adam
    except ImportError:
        raise ImportError("TensorFlow not installed. Run: pip install tensorflow")

    model = Sequential()

    # First hidden layer
    model.add(Dense(hidden_layers[0], input_dim=input_dim, activation='relu'))
    model.add(Dropout(dropout))

    # Additional hidden layers
    for units in hidden_layers[1:]:
        model.add(Dense(units, activation='relu'))
        model.add(Dropout(dropout))

    # Output layer
    model.add(Dense(1, activation=output_activation))

    # Compile
    if output_activation == 'sigmoid':
        model.compile(
            loss='binary_crossentropy',
            optimizer=Adam(learning_rate=0.001),
            metrics=['accuracy']
        )
    else:
        model.compile(
            loss='mse',
            optimizer=Adam(learning_rate=0.001),
            metrics=['mae']
        )

    return model


def create_trend_break_model(input_dim: int):
    """
    Create model specifically for trend break prediction.

    This model predicts whether a trend break will occur soon.

    Args:
        input_dim: Number of input features (technical indicators)

    Returns:
        Compiled Keras model

    Example:
        >>> model = create_trend_break_model(input_dim=15)
    """
    try:
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import Dense, Dropout, BatchNormalization
        from tensorflow.keras.optimizers import Adam
    except ImportError:
        raise ImportError("TensorFlow not installed. Run: pip install tensorflow")

    model = Sequential([
        Dense(128, input_dim=input_dim, activation='relu'),
        BatchNormalization(),
        Dropout(0.3),

        Dense(64, activation='relu'),
        BatchNormalization(),
        Dropout(0.3),

        Dense(32, activation='relu'),
        BatchNormalization(),
        Dropout(0.2),

        Dense(16, activation='relu'),
        Dense(1, activation='sigmoid')
    ])

    model.compile(
        optimizer=Adam(learning_rate=0.001),
        loss='binary_crossentropy',
        metrics=['accuracy', 'AUC']
    )

    return model


# ════════════════════════════════════════════════════════════════════════════
# TRAINING FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def train_model(
    model,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: Optional[np.ndarray] = None,
    y_val: Optional[np.ndarray] = None,
    epochs: int = 50,
    batch_size: int = 32,
    early_stopping: bool = True,
    patience: int = 10,
    verbose: int = 1
) -> Tuple[Any, Dict]:
    """
    Train a Keras model with optional early stopping.

    Args:
        model: Keras model to train
        X_train: Training features
        y_train: Training labels
        X_val: Validation features (optional)
        y_val: Validation labels (optional)
        epochs: Maximum epochs
        batch_size: Batch size
        early_stopping: Use early stopping callback
        patience: Early stopping patience
        verbose: Verbosity level

    Returns:
        Tuple of (trained model, training history)

    Example:
        >>> model, history = train_model(model, X_train, y_train, X_val, y_val)
    """
    try:
        from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
    except ImportError:
        raise ImportError("TensorFlow not installed")

    callbacks = []

    if early_stopping:
        callbacks.append(
            EarlyStopping(
                monitor='val_loss' if X_val is not None else 'loss',
                patience=patience,
                restore_best_weights=True
            )
        )

    validation_data = (X_val, y_val) if X_val is not None else None

    history = model.fit(
        X_train, y_train,
        validation_data=validation_data,
        epochs=epochs,
        batch_size=batch_size,
        callbacks=callbacks,
        verbose=verbose
    )

    return model, history.history


def train_trend_model(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    model_type: str = 'dense',
    epochs: int = 50,
    batch_size: int = 32
) -> Tuple[Any, Dict]:
    """
    Train a trend prediction model.

    Args:
        X_train: Training features
        y_train: Training labels (1 for trend break, 0 for no break)
        X_test: Test features
        y_test: Test labels
        model_type: 'dense', 'lstm', or 'trend_break'
        epochs: Number of epochs
        batch_size: Batch size

    Returns:
        Tuple of (trained model, training history)

    Example:
        >>> model, history = train_trend_model(X_train, y_train, X_test, y_test)
    """
    if model_type == 'lstm':
        # Reshape for LSTM (samples, timesteps, features)
        if len(X_train.shape) == 2:
            X_train = X_train.reshape((X_train.shape[0], 1, X_train.shape[1]))
            X_test = X_test.reshape((X_test.shape[0], 1, X_test.shape[1]))
        model = create_lstm_model(input_shape=(X_train.shape[1], X_train.shape[2]))
    elif model_type == 'trend_break':
        model = create_trend_break_model(input_dim=X_train.shape[1])
    else:
        model = create_dense_model(input_dim=X_train.shape[1])

    model, history = train_model(
        model, X_train, y_train, X_test, y_test,
        epochs=epochs, batch_size=batch_size
    )

    return model, history


# ════════════════════════════════════════════════════════════════════════════
# XGBOOST MODEL (RECOMMENDED for trend/direction prediction)
# ════════════════════════════════════════════════════════════════════════════

def create_xgboost_model(
    n_estimators: int = 100,
    max_depth: int = 6,
    learning_rate: float = 0.1,
    objective: str = 'binary:logistic',
    task_type: str = 'classification'
):
    """
    Create XGBoost model for trend prediction.

    RECOMMENDED for:
    - Price direction prediction (up/down/neutral)
    - Trend break probability
    - Indicator-based features

    Args:
        n_estimators: Number of trees (default: 100)
        max_depth: Maximum tree depth (default: 6)
        learning_rate: Learning rate (default: 0.1)
        objective: Objective function
        task_type: 'classification' or 'regression'

    Returns:
        XGBoost classifier or regressor

    Example:
        >>> model = create_xgboost_model()
        >>> model = create_xgboost_model(task_type='regression')
    """
    try:
        import xgboost as xgb
    except ImportError:
        raise ImportError("XGBoost not installed. Run: pip install xgboost")

    if task_type == 'regression':
        model = xgb.XGBRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            objective='reg:squarederror'
        )
    else:
        model = xgb.XGBClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            objective=objective,
            use_label_encoder=False,
            eval_metric='logloss'
        )

    return model


def train_xgboost_model(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    n_estimators: int = 100,
    max_depth: int = 6,
    feature_names: Optional[list] = None
) -> Tuple[Any, Dict]:
    """
    Train XGBoost model for trend prediction.

    Args:
        X_train: Training features
        y_train: Training labels
        X_test: Test features
        y_test: Test labels
        n_estimators: Number of trees
        max_depth: Maximum tree depth
        feature_names: Optional list of feature names for importance

    Returns:
        Tuple of (trained model, evaluation metrics with feature importance)

    Example:
        >>> model, metrics = train_xgboost_model(X_train, y_train, X_test, y_test)
        >>> print(metrics['feature_importance'])
    """
    try:
        import xgboost as xgb
        from sklearn.metrics import accuracy_score, roc_auc_score, classification_report
    except ImportError:
        raise ImportError("XGBoost or sklearn not installed")

    model = create_xgboost_model(n_estimators=n_estimators, max_depth=max_depth)

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False
    )

    # Evaluate
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    metrics = {
        'accuracy': accuracy_score(y_test, y_pred),
        'roc_auc': roc_auc_score(y_test, y_proba),
        'classification_report': classification_report(y_test, y_pred)
    }

    # Feature importance
    importance = model.feature_importances_
    if feature_names is not None:
        metrics['feature_importance'] = dict(zip(feature_names, importance))
    else:
        metrics['feature_importance'] = importance

    print(f"Accuracy: {metrics['accuracy']:.4f}")
    print(f"ROC AUC: {metrics['roc_auc']:.4f}")

    return model, metrics


# ════════════════════════════════════════════════════════════════════════════
# LIGHTGBM MODEL (Faster alternative to XGBoost)
# ════════════════════════════════════════════════════════════════════════════

def create_lightgbm_model(
    n_estimators: int = 100,
    max_depth: int = 6,
    learning_rate: float = 0.1,
    task_type: str = 'classification'
):
    """
    Create LightGBM model for trend prediction.

    LightGBM advantages over XGBoost:
    - Faster training (especially with large datasets)
    - Lower memory usage
    - Often comparable or better accuracy

    Args:
        n_estimators: Number of trees
        max_depth: Maximum tree depth
        learning_rate: Learning rate
        task_type: 'classification' or 'regression'

    Returns:
        LightGBM classifier or regressor

    Example:
        >>> model = create_lightgbm_model()
    """
    try:
        import lightgbm as lgb
    except ImportError:
        raise ImportError("LightGBM not installed. Run: pip install lightgbm")

    if task_type == 'regression':
        model = lgb.LGBMRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            verbose=-1
        )
    else:
        model = lgb.LGBMClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            verbose=-1
        )

    return model


def train_lightgbm_model(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    n_estimators: int = 100,
    max_depth: int = 6,
    feature_names: Optional[list] = None
) -> Tuple[Any, Dict]:
    """
    Train LightGBM model for trend prediction.

    Args:
        X_train: Training features
        y_train: Training labels
        X_test: Test features
        y_test: Test labels
        n_estimators: Number of trees
        max_depth: Maximum tree depth
        feature_names: Optional list of feature names

    Returns:
        Tuple of (trained model, evaluation metrics)

    Example:
        >>> model, metrics = train_lightgbm_model(X_train, y_train, X_test, y_test)
    """
    try:
        import lightgbm as lgb
        from sklearn.metrics import accuracy_score, roc_auc_score, classification_report
    except ImportError:
        raise ImportError("LightGBM or sklearn not installed")

    model = create_lightgbm_model(n_estimators=n_estimators, max_depth=max_depth)

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
    )

    # Evaluate
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    metrics = {
        'accuracy': accuracy_score(y_test, y_pred),
        'roc_auc': roc_auc_score(y_test, y_proba),
        'classification_report': classification_report(y_test, y_pred)
    }

    # Feature importance
    importance = model.feature_importances_
    if feature_names is not None:
        metrics['feature_importance'] = dict(zip(feature_names, importance))
    else:
        metrics['feature_importance'] = importance

    print(f"Accuracy: {metrics['accuracy']:.4f}")
    print(f"ROC AUC: {metrics['roc_auc']:.4f}")

    return model, metrics


def compare_models(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    feature_names: Optional[list] = None
) -> Dict[str, Dict]:
    """
    Compare XGBoost and LightGBM performance.

    Args:
        X_train: Training features
        y_train: Training labels
        X_test: Test features
        y_test: Test labels
        feature_names: Optional feature names

    Returns:
        Dict with metrics for each model

    Example:
        >>> comparison = compare_models(X_train, y_train, X_test, y_test)
        >>> print(f"XGBoost: {comparison['xgboost']['accuracy']:.4f}")
        >>> print(f"LightGBM: {comparison['lightgbm']['accuracy']:.4f}")
    """
    import time

    results = {}

    # XGBoost
    print("Training XGBoost...")
    start = time.time()
    xgb_model, xgb_metrics = train_xgboost_model(X_train, y_train, X_test, y_test, feature_names=feature_names)
    xgb_time = time.time() - start
    xgb_metrics['training_time'] = xgb_time
    results['xgboost'] = {'model': xgb_model, 'metrics': xgb_metrics}

    # LightGBM
    print("\nTraining LightGBM...")
    start = time.time()
    lgb_model, lgb_metrics = train_lightgbm_model(X_train, y_train, X_test, y_test, feature_names=feature_names)
    lgb_time = time.time() - start
    lgb_metrics['training_time'] = lgb_time
    results['lightgbm'] = {'model': lgb_model, 'metrics': lgb_metrics}

    # Summary
    print(f"\n{'='*50}")
    print("MODEL COMPARISON")
    print(f"{'='*50}")
    print(f"XGBoost  - Accuracy: {xgb_metrics['accuracy']:.4f}, ROC AUC: {xgb_metrics['roc_auc']:.4f}, Time: {xgb_time:.2f}s")
    print(f"LightGBM - Accuracy: {lgb_metrics['accuracy']:.4f}, ROC AUC: {lgb_metrics['roc_auc']:.4f}, Time: {lgb_time:.2f}s")

    return results


# ════════════════════════════════════════════════════════════════════════════
# DATA PREPARATION
# ════════════════════════════════════════════════════════════════════════════

def prepare_training_data(
    data: pd.DataFrame,
    target_col: str = 'trend_break',
    feature_cols: Optional[list] = None,
    test_size: float = 0.2,
    sequence_length: int = 60
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Prepare data for model training.

    Args:
        data: DataFrame with features and target
        target_col: Name of target column
        feature_cols: List of feature columns (None = all except target)
        test_size: Fraction for test set
        sequence_length: Sequence length for LSTM (ignored for dense models)

    Returns:
        Tuple of (X_train, X_test, y_train, y_test)

    Example:
        >>> X_train, X_test, y_train, y_test = prepare_training_data(data)
    """
    try:
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        raise ImportError("sklearn not installed. Run: pip install scikit-learn")

    data = data.dropna()

    if feature_cols is None:
        feature_cols = [col for col in data.columns if col != target_col and col != 'Date']

    X = data[feature_cols].values
    y = data[target_col].values

    # Scale features
    scaler = StandardScaler()
    X = scaler.fit_transform(X)

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42
    )

    return X_train, X_test, y_train, y_test


def create_sequences(
    data: np.ndarray,
    target: np.ndarray,
    sequence_length: int = 60
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Create sequences for LSTM model.

    Args:
        data: Feature data
        target: Target data
        sequence_length: Number of timesteps per sequence

    Returns:
        Tuple of (X_sequences, y_sequences)

    Example:
        >>> X_seq, y_seq = create_sequences(X, y, sequence_length=60)
    """
    X, y = [], []

    for i in range(sequence_length, len(data)):
        X.append(data[i - sequence_length:i])
        y.append(target[i])

    return np.array(X), np.array(y)


# ════════════════════════════════════════════════════════════════════════════
# MODEL SAVING/LOADING
# ════════════════════════════════════════════════════════════════════════════

def save_model(model, path: str, model_type: str = 'keras'):
    """
    Save trained model to file.

    Args:
        model: Trained model
        path: Save path
        model_type: 'keras' or 'xgboost'

    Example:
        >>> save_model(model, 'models/trend_model.h5', model_type='keras')
    """
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)

    if model_type == 'keras':
        model.save(path)
    elif model_type == 'xgboost':
        import joblib
        joblib.dump(model, path)
    else:
        raise ValueError(f"Unknown model type: {model_type}")

    print(f"Model saved to: {path}")


def load_model(path: str, model_type: str = 'keras'):
    """
    Load trained model from file.

    Args:
        path: Model path
        model_type: 'keras' or 'xgboost'

    Returns:
        Loaded model

    Example:
        >>> model = load_model('models/trend_model.h5', model_type='keras')
    """
    if model_type == 'keras':
        from tensorflow.keras.models import load_model as keras_load
        return keras_load(path)
    elif model_type == 'xgboost':
        import joblib
        return joblib.load(path)
    else:
        raise ValueError(f"Unknown model type: {model_type}")


# ════════════════════════════════════════════════════════════════════════════
# PREDICTION FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def predict_trend_break(
    model,
    data: pd.DataFrame,
    feature_cols: list,
    threshold: float = 0.5
) -> pd.DataFrame:
    """
    Predict trend breaks using trained model.

    Args:
        model: Trained model
        data: DataFrame with features
        feature_cols: List of feature columns used for training
        threshold: Probability threshold for positive prediction

    Returns:
        DataFrame with predictions added

    Example:
        >>> predictions = predict_trend_break(model, data, feature_cols)
    """
    try:
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        raise ImportError("sklearn not installed")

    data = data.copy()

    X = data[feature_cols].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Get predictions
    try:
        # Keras model
        probabilities = model.predict(X_scaled, verbose=0).flatten()
    except:
        # XGBoost model
        probabilities = model.predict_proba(X_scaled)[:, 1]

    data['trend_break_prob'] = probabilities
    data['trend_break_pred'] = (probabilities >= threshold).astype(int)

    return data


def get_prediction_summary(predictions: pd.DataFrame) -> Dict[str, Any]:
    """
    Get summary of predictions.

    Args:
        predictions: DataFrame with trend_break_prob and trend_break_pred columns

    Returns:
        Dictionary with summary statistics

    Example:
        >>> summary = get_prediction_summary(predictions)
    """
    summary = {
        'total_records': len(predictions),
        'predicted_breaks': predictions['trend_break_pred'].sum(),
        'break_rate': predictions['trend_break_pred'].mean(),
        'mean_probability': predictions['trend_break_prob'].mean(),
        'high_probability_count': (predictions['trend_break_prob'] >= 0.8).sum(),
        'max_probability': predictions['trend_break_prob'].max(),
        'min_probability': predictions['trend_break_prob'].min()
    }

    return summary
