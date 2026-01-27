# Securities Prediction Model - Source Package
# This package contains modular components for the trading prediction system

from .data_fetcher import get_stock_data, fetch_and_store
from .technical_indicators import (
    calculate_rsi, calculate_adx, calculate_roc, calculate_supertrend,
    calculate_vpt, calculate_macd, stochastic_oscillator, bollinger_bands,
    on_balance_volume, chaikin_money_flow, volume_weighted_average_price,
    accumulation_distribution_line, money_flow_index, moving_averages,
    trend_line, percent_number_of_stocks_above_moving_average,
    periodic_high_and_lows, advance_decline
)
from .trend_analysis import (
    trend_break, trend_line_break_accuracy, feature_engineering,
    analyze_indicator_accuracy, filter_best_indicators
)
from .options_pricing import (
    black_scholes_call, black_scholes_put, option_analysis,
    get_option_prices, binomial_tree_american, calculate_greeks,
    get_risk_free_rate, analyze_option_pricing, filter_options_by_trend
)
from .models import (
    create_xgboost_model, train_xgboost_model,
    create_lightgbm_model, train_lightgbm_model,
    create_lstm_model, create_dense_model,
    compare_models, prepare_training_data
)
from .meta_learning_model import (
    calculate_market_regime_features,
    create_accuracy_features_dataset,
    train_indicator_reliability_model,
    predict_indicator_reliability,
    analyze_indicator_accuracy,
    train_on_trend_breaks,
    get_stock_data_from_db,
    get_trend_breaks_from_db,
    get_available_tickers
)
from .populate_market_indices import (
    batch_load_market_data,
    calculate_market_features_batch,
    calculate_market_instrument_indicators,
    calculate_market_features,
    get_market_index_data
)

__version__ = "1.0.0"
__all__ = [
    # Data fetching
    'get_stock_data', 'fetch_and_store',
    # Technical indicators
    'calculate_rsi', 'calculate_adx', 'calculate_roc', 'calculate_supertrend',
    'calculate_vpt', 'calculate_macd', 'stochastic_oscillator', 'bollinger_bands',
    'on_balance_volume', 'chaikin_money_flow', 'volume_weighted_average_price',
    'accumulation_distribution_line', 'money_flow_index', 'moving_averages',
    'trend_line', 'percent_number_of_stocks_above_moving_average',
    'periodic_high_and_lows', 'advance_decline',
    # Trend analysis
    'trend_break', 'trend_line_break_accuracy', 'feature_engineering',
    'analyze_indicator_accuracy', 'filter_best_indicators',
    # Options pricing
    'black_scholes_call', 'black_scholes_put', 'option_analysis',
    'get_option_prices', 'binomial_tree_american', 'calculate_greeks',
    'get_risk_free_rate', 'analyze_option_pricing', 'filter_options_by_trend',
    # ML Models
    'create_xgboost_model', 'train_xgboost_model',
    'create_lightgbm_model', 'train_lightgbm_model',
    'create_lstm_model', 'create_dense_model',
    'compare_models', 'prepare_training_data',
    # Meta-learning model
    'calculate_market_regime_features',
    'create_accuracy_features_dataset',
    'train_indicator_reliability_model',
    'predict_indicator_reliability',
    'analyze_indicator_accuracy',
    'train_on_trend_breaks',
    'get_stock_data_from_db',
    'get_trend_breaks_from_db',
    'get_available_tickers',
    # Market indices
    'batch_load_market_data',
    'calculate_market_features_batch',
    'calculate_market_instrument_indicators',
    'calculate_market_features',
    'get_market_index_data',
]
