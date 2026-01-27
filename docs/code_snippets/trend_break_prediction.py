"""
TREND BREAK PREDICTION MODEL - XGBOOST CLASSIFIER

This module implements Stage 2 of the trading system: predicting when trend breaks
will occur using the most reliable indicators identified in Stage 1 (meta-learning).

Architecture:
    Stage 1: Meta-Learning → Which indicators are reliable? (meta_learning_model.py)
    Stage 2: XGBoost Classifier → When will trend breaks occur? (THIS FILE)
    Stage 3: Options Trading → Execute trades based on predictions (options_analysis.py)

Why XGBoost instead of LSTM:
    - Perfect for tabular indicator data
    - Fast training (minutes vs hours)
    - Feature importance reveals which indicators predict breaks
    - Better performance on financial data
    - Less prone to overfitting
    - Integrates seamlessly with existing indicator analysis

Usage:
    1. Create target variable: create_trend_break_target()
    2. Train model: train_trend_break_model()
    3. Predict breaks: predict_trend_break()
    4. Backtest strategy: backtest_trend_break_strategy()
"""

import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import (
    classification_report, confusion_matrix, roc_auc_score,
    precision_recall_curve, roc_curve
)
import matplotlib.pyplot as plt
from docs.code_snippets.SP_historical_data import (
    trend_break,
    TechnicalIndicators
)


# ════════════════════════════════════════════════════════════════════════════
# TARGET VARIABLE CREATION
# ════════════════════════════════════════════════════════════════════════════

def create_trend_break_target(data, lookahead_days=10, method='binary'):
    """
    Creates target variable for trend break prediction.

    Args:
        data (DataFrame): Historical price data with indicators
        lookahead_days (int): How many days forward to look for trend breaks
        method (str): Target type:
                     'binary' - 1 if break occurs, 0 otherwise
                     'days_until' - Number of days until next break (regression)
                     'probability' - Smoothed probability based on proximity

    Returns:
        Series: Target variable aligned with data index
    """
    # Detect all trend breaks
    trend_breaks = trend_break(data, 'Close', 'trend_direction')

    # Convert to dictionary for faster lookup
    break_dates = {break_date: break_info for break_date, break_info in trend_breaks}

    if method == 'binary':
        # Binary classification: Will break occur in next N days?
        target = pd.Series(0, index=data.index, name='trend_break_target')

        for i, date in enumerate(data.index):
            future_window_end = date + pd.Timedelta(days=lookahead_days)

            # Check if any trend break falls in this window
            for break_date in break_dates.keys():
                if date < break_date <= future_window_end:
                    target.iloc[i] = 1
                    break  # Found a break, no need to check further

    elif method == 'days_until':
        # Regression: How many days until next break?
        target = pd.Series(lookahead_days + 1, index=data.index, name='days_until_break')

        for i, date in enumerate(data.index):
            # Find next break after this date
            future_breaks = [bd for bd in break_dates.keys() if bd > date]

            if future_breaks:
                next_break = min(future_breaks)
                days_until = (next_break - date).days
                target.iloc[i] = min(days_until, lookahead_days + 1)

    elif method == 'probability':
        # Probability based on proximity to break (weighted)
        target = pd.Series(0.0, index=data.index, name='break_probability')

        for i, date in enumerate(data.index):
            future_window_end = date + pd.Timedelta(days=lookahead_days)

            # Find breaks in window and weight by proximity
            for break_date in break_dates.keys():
                if date < break_date <= future_window_end:
                    days_away = (break_date - date).days
                    # Closer breaks get higher probability
                    proximity_weight = 1 - (days_away / lookahead_days)
                    target.iloc[i] = max(target.iloc[i], proximity_weight)

    else:
        raise ValueError(f"Unknown method: {method}. Use 'binary', 'days_until', or 'probability'")

    print(f"\nTarget Variable Statistics ({method}):")
    print(f"  Total samples: {len(target)}")
    if method == 'binary':
        print(f"  Positive samples (breaks): {target.sum()} ({target.mean()*100:.1f}%)")
        print(f"  Negative samples (no breaks): {(target == 0).sum()} ({(1-target.mean())*100:.1f}%)")
    elif method == 'days_until':
        print(f"  Mean days until break: {target.mean():.1f}")
        print(f"  Min days until break: {target.min()}")
    elif method == 'probability':
        print(f"  Mean probability: {target.mean():.3f}")
        print(f"  Samples with >50% probability: {(target > 0.5).sum()}")

    return target


# ════════════════════════════════════════════════════════════════════════════
# FEATURE ENGINEERING
# ════════════════════════════════════════════════════════════════════════════

def engineer_features(data, indicator_names, lookback_periods=[5, 10, 20]):
    """
    Engineers additional features from raw indicators.

    Creates derived features that may be more predictive:
    - Rate of change (momentum)
    - Moving averages
    - Volatility measures
    - Crossovers

    Args:
        data (DataFrame): Price data with indicators
        indicator_names (list): Base indicator column names
        lookback_periods (list): Periods for rolling calculations

    Returns:
        DataFrame: Original data + engineered features
    """
    feature_data = data.copy()

    print(f"\nEngineering features from {len(indicator_names)} base indicators...")

    for indicator in indicator_names:
        if indicator not in data.columns:
            continue

        # Rate of change (momentum)
        for period in lookback_periods:
            feature_data[f'{indicator}_roc_{period}'] = data[indicator].pct_change(periods=period)

        # Moving averages
        for period in lookback_periods:
            feature_data[f'{indicator}_ma_{period}'] = data[indicator].rolling(period).mean()

        # Volatility (rolling standard deviation)
        for period in lookback_periods:
            feature_data[f'{indicator}_std_{period}'] = data[indicator].rolling(period).std()

        # Distance from moving average (normalized)
        for period in lookback_periods:
            ma = data[indicator].rolling(period).mean()
            feature_data[f'{indicator}_dist_ma_{period}'] = (data[indicator] - ma) / ma

    # Price-specific features
    if 'Close' in data.columns:
        feature_data['price_momentum_5'] = data['Close'].pct_change(5)
        feature_data['price_momentum_10'] = data['Close'].pct_change(10)
        feature_data['price_volatility_20'] = data['Close'].pct_change().rolling(20).std()

        if 'High' in data.columns and 'Low' in data.columns:
            feature_data['price_range'] = (data['High'] - data['Low']) / data['Close']

    # Volume features
    if 'Volume' in data.columns:
        feature_data['volume_ma_20'] = data['Volume'].rolling(20).mean()
        feature_data['volume_ratio'] = data['Volume'] / feature_data['volume_ma_20']

    # Drop NaN rows created by rolling calculations
    feature_data = feature_data.dropna()

    print(f"  Created {len(feature_data.columns) - len(data.columns)} new features")
    print(f"  Total features: {len(feature_data.columns)}")
    print(f"  Samples after dropping NaN: {len(feature_data)}")

    return feature_data


# ════════════════════════════════════════════════════════════════════════════
# MODEL TRAINING
# ════════════════════════════════════════════════════════════════════════════

def train_trend_break_model(ticker, start_date, end_date,
                            indicator_names=None,
                            lookahead_days=10,
                            engineer_features_flag=True,
                            test_split_date=None):
    """
    Trains XGBoost model to predict trend breaks.

    Args:
        ticker (str): Stock ticker symbol
        start_date (str): Training data start date
        end_date (str): Training data end date
        indicator_names (list): Indicators to use as features. If None, uses all.
        lookahead_days (int): Days forward to predict trend breaks
        engineer_features_flag (bool): Whether to create derived features
        test_split_date (str): Date to split train/test. If None, uses 80/20 split.

    Returns:
        dict: Trained model, feature names, evaluation metrics, and predictions
    """
    print(f"\n{'='*80}")
    print(f"TRAINING TREND BREAK PREDICTION MODEL: {ticker}")
    print(f"{'='*80}\n")

    # Get indicator data
    print("Step 1: Fetching indicator data...")
    ti = TechnicalIndicators(ticker, start_date, end_date)
    all_data = ti.get_all_indicators()

    # Select indicators
    if indicator_names is None:
        indicator_names = list(TechnicalIndicators.INDICATOR_FUNCTIONS.keys())

    # Filter to available indicators
    available_indicators = [ind for ind in indicator_names if ind in all_data.columns]
    print(f"  Using {len(available_indicators)} indicators")

    # Engineer features
    if engineer_features_flag:
        print("\nStep 2: Engineering features...")
        feature_data = engineer_features(all_data, available_indicators)
    else:
        feature_data = all_data[available_indicators].copy()

    # Create target variable
    print(f"\nStep 3: Creating target variable (lookahead: {lookahead_days} days)...")
    target = create_trend_break_target(all_data, lookahead_days, method='binary')

    # Align features and target
    common_index = feature_data.index.intersection(target.index)
    X = feature_data.loc[common_index]
    y = target.loc[common_index]

    print(f"\nStep 4: Preparing train/test split...")

    # Time-based split (CRITICAL for time series)
    if test_split_date:
        split_idx = X.index.get_loc(X[X.index >= test_split_date].index[0])
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
        print(f"  Split date: {test_split_date}")
    else:
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
        split_date = X.index[split_idx]
        print(f"  Split date (80/20): {split_date.date()}")

    print(f"  Training samples: {len(X_train)} ({y_train.sum()} positive)")
    print(f"  Test samples: {len(X_test)} ({y_test.sum()} positive)")

    # Handle class imbalance
    scale_pos_weight = (y_train == 0).sum() / (y_train == 1).sum()
    print(f"  Class imbalance ratio: {scale_pos_weight:.2f}")

    # Train XGBoost model
    print(f"\nStep 5: Training XGBoost classifier...")

    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=3,
        gamma=0.1,
        scale_pos_weight=scale_pos_weight,  # Handle class imbalance
        objective='binary:logistic',
        eval_metric=['logloss', 'auc'],
        random_state=42,
        n_jobs=-1
    )

    # Train with early stopping
    model.fit(
        X_train, y_train,
        eval_set=[(X_train, y_train), (X_test, y_test)],
        early_stopping_rounds=20,
        verbose=False
    )

    print(f"  Training complete! Best iteration: {model.best_iteration}")

    # Evaluate model
    print(f"\nStep 6: Evaluating model...")

    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]

    # Classification metrics
    print(f"\n{'='*80}")
    print("MODEL PERFORMANCE")
    print(f"{'='*80}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=['No Break', 'Break']))

    print("\nConfusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    print(f"  True Negatives:  {cm[0,0]:5d} | False Positives: {cm[0,1]:5d}")
    print(f"  False Negatives: {cm[1,0]:5d} | True Positives:  {cm[1,1]:5d}")

    # AUC-ROC
    auc_score = roc_auc_score(y_test, y_pred_proba)
    print(f"\nAUC-ROC Score: {auc_score:.4f}")

    # Feature importance
    print(f"\nTop 15 Most Important Features:")
    feature_importance = pd.DataFrame({
        'feature': X_train.columns,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)

    for idx, row in feature_importance.head(15).iterrows():
        print(f"  {row['feature']:40s} {row['importance']:.4f}")

    print(f"{'='*80}\n")

    # Return comprehensive results
    return {
        'model': model,
        'feature_names': list(X_train.columns),
        'X_train': X_train,
        'X_test': X_test,
        'y_train': y_train,
        'y_test': y_test,
        'y_pred': y_pred,
        'y_pred_proba': y_pred_proba,
        'auc_score': auc_score,
        'feature_importance': feature_importance,
        'lookahead_days': lookahead_days,
        'ticker': ticker
    }


# ════════════════════════════════════════════════════════════════════════════
# PREDICTION
# ════════════════════════════════════════════════════════════════════════════

def predict_trend_break(model, ticker, current_date, feature_names,
                        indicator_names, lookahead_days=10,
                        engineer_features_flag=True):
    """
    Predicts probability of trend break in next N days.

    Args:
        model: Trained XGBoost model
        ticker (str): Stock ticker symbol
        current_date (str): Date to make prediction from ('YYYY-MM-DD' or 'latest')
        feature_names (list): Feature column names from training
        indicator_names (list): Base indicator names
        lookahead_days (int): Prediction horizon
        engineer_features_flag (bool): Whether to engineer features

    Returns:
        dict: Prediction results including probability, recommendation, and supporting data
    """
    # Get recent data
    if current_date == 'latest':
        end_date = pd.Timestamp.now().strftime('%Y-%m-%d')
    else:
        end_date = current_date

    # Need enough history for feature engineering
    start_date = (pd.to_datetime(end_date) - pd.Timedelta(days=120)).strftime('%Y-%m-%d')

    # Fetch data
    ti = TechnicalIndicators(ticker, start_date, end_date)
    all_data = ti.get_all_indicators()

    # Engineer features
    if engineer_features_flag:
        feature_data = engineer_features(all_data, indicator_names)
    else:
        feature_data = all_data[indicator_names].copy()

    # Get latest features
    latest_features = feature_data.iloc[-1][feature_names].values.reshape(1, -1)

    # Make prediction
    prob_break = model.predict_proba(latest_features)[0, 1]
    prediction = model.predict(latest_features)[0]

    # Generate recommendation
    if prob_break > 0.7:
        recommendation = "HIGH PROBABILITY - Strong trend break signal"
        action = "Consider taking position"
    elif prob_break > 0.5:
        recommendation = "MODERATE PROBABILITY - Trend break likely"
        action = "Monitor closely, prepare for position"
    elif prob_break > 0.3:
        recommendation = "LOW PROBABILITY - Trend break possible"
        action = "Stay alert, no immediate action"
    else:
        recommendation = "VERY LOW PROBABILITY - Trend continuation expected"
        action = "Maintain current strategy"

    # Get feature contributions
    feature_contributions = pd.DataFrame({
        'feature': feature_names,
        'value': latest_features[0],
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)

    print(f"\n{'='*80}")
    print(f"TREND BREAK PREDICTION: {ticker}")
    print(f"{'='*80}")
    print(f"Date: {end_date}")
    print(f"Prediction Horizon: Next {lookahead_days} days")
    print(f"\nProbability of Trend Break: {prob_break:.1%}")
    print(f"Prediction: {'BREAK EXPECTED' if prediction == 1 else 'NO BREAK'}")
    print(f"\n{recommendation}")
    print(f"Recommended Action: {action}")
    print(f"\nTop 5 Contributing Features:")
    for _, row in feature_contributions.head(5).iterrows():
        print(f"  {row['feature']:40s} = {row['value']:10.4f}")
    print(f"{'='*80}\n")

    return {
        'probability': prob_break,
        'prediction': prediction,
        'recommendation': recommendation,
        'action': action,
        'feature_contributions': feature_contributions,
        'current_price': all_data['Close'].iloc[-1],
        'date': end_date
    }


# ════════════════════════════════════════════════════════════════════════════
# BACKTESTING
# ════════════════════════════════════════════════════════════════════════════

def backtest_trend_break_strategy(results, threshold=0.5):
    """
    Backtests the trend break prediction strategy.

    Simulates trading based on model predictions to evaluate real-world performance.

    Args:
        results (dict): Output from train_trend_break_model()
        threshold (float): Probability threshold to trigger trades (0.0-1.0)

    Returns:
        dict: Backtest metrics and trade log
    """
    print(f"\n{'='*80}")
    print("BACKTESTING TREND BREAK STRATEGY")
    print(f"{'='*80}\n")

    X_test = results['X_test']
    y_test = results['y_test']
    y_pred_proba = results['y_pred_proba']
    model = results['model']

    # Generate signals
    signals = (y_pred_proba >= threshold).astype(int)

    # Calculate performance metrics
    true_positives = ((signals == 1) & (y_test == 1)).sum()
    false_positives = ((signals == 1) & (y_test == 0)).sum()
    true_negatives = ((signals == 0) & (y_test == 0)).sum()
    false_negatives = ((signals == 0) & (y_test == 1)).sum()

    # Trading metrics
    total_signals = signals.sum()
    correct_signals = true_positives
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0

    print(f"Threshold: {threshold:.1%}")
    print(f"Total Signals Generated: {total_signals}")
    print(f"Correct Signals: {correct_signals} ({precision:.1%} precision)")
    print(f"Missed Breaks: {false_negatives} ({recall:.1%} recall)")
    print(f"False Alarms: {false_positives}")
    print(f"\nTrue Positives:  {true_positives:5d} | False Positives: {false_positives:5d}")
    print(f"False Negatives: {false_negatives:5d} | True Negatives:  {true_negatives:5d}")

    # Calculate profit simulation (assuming simple strategy)
    # Profit if correct signal, loss if wrong signal
    profit_per_correct = 100  # Arbitrary units
    loss_per_wrong = -50

    total_profit = (true_positives * profit_per_correct +
                    false_positives * loss_per_wrong)

    print(f"\nSimulated P&L (arbitrary units):")
    print(f"  Total Profit: {total_profit:+.0f}")
    print(f"  Profit per Signal: {total_profit/total_signals if total_signals > 0 else 0:+.1f}")

    # Risk-reward analysis
    print(f"\nRisk-Reward Analysis:")
    print(f"  Win Rate: {precision:.1%}")
    print(f"  Signal Frequency: {total_signals/len(y_test):.1%} of days")

    print(f"{'='*80}\n")

    return {
        'threshold': threshold,
        'total_signals': total_signals,
        'true_positives': true_positives,
        'false_positives': false_positives,
        'false_negatives': false_negatives,
        'true_negatives': true_negatives,
        'precision': precision,
        'recall': recall,
        'total_profit': total_profit
    }


# ════════════════════════════════════════════════════════════════════════════
# MODEL PERSISTENCE
# ════════════════════════════════════════════════════════════════════════════

def save_trend_break_model(results, output_dir='.'):
    """Saves trained model and metadata."""
    import os
    import pickle

    ticker = results['ticker']
    lookahead = results['lookahead_days']

    # Save XGBoost model
    model_path = os.path.join(output_dir, f'{ticker}_trend_break_model_{lookahead}d.json')
    results['model'].save_model(model_path)
    print(f"✓ Model saved to {model_path}")

    # Save metadata
    metadata = {
        'feature_names': results['feature_names'],
        'lookahead_days': lookahead,
        'ticker': ticker,
        'auc_score': results['auc_score'],
        'feature_importance': results['feature_importance']
    }
    metadata_path = os.path.join(output_dir, f'{ticker}_trend_break_metadata_{lookahead}d.pkl')
    with open(metadata_path, 'wb') as f:
        pickle.dump(metadata, f)
    print(f"✓ Metadata saved to {metadata_path}")


def load_trend_break_model(model_path, metadata_path):
    """Loads saved model and metadata."""
    import pickle

    model = xgb.XGBClassifier()
    model.load_model(model_path)

    with open(metadata_path, 'rb') as f:
        metadata = pickle.load(f)

    return {'model': model, **metadata}


# ════════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    # Train model
    print("="*80)
    print("EXAMPLE: TRAINING TREND BREAK PREDICTION MODEL")
    print("="*80)

    results = train_trend_break_model(
        ticker='AAPL',
        start_date='2018-01-01',
        end_date='2023-12-31',
        lookahead_days=10,
        engineer_features_flag=True,
        test_split_date='2023-01-01'
    )

    # Save model
    save_trend_break_model(results)

    # Backtest
    backtest_results = backtest_trend_break_strategy(results, threshold=0.5)

    # Make prediction
    prediction = predict_trend_break(
        model=results['model'],
        ticker='AAPL',
        current_date='latest',
        feature_names=results['feature_names'],
        indicator_names=list(TechnicalIndicators.INDICATOR_FUNCTIONS.keys()),
        lookahead_days=10,
        engineer_features_flag=True
    )

    print("\n" + "="*80)
    print("COMPLETE! Model ready for integration with options trading system.")
    print("="*80)
