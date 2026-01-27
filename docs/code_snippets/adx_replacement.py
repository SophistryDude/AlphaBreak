import pandas as pd
import pandas_ta as ta


def calculate_adx(ticker, start_date, end_date):
    """
    Calculate ADX, +DI, and -DI using pandas_ta instead of talib.

    Args:
        ticker (str): Stock ticker symbol
        start_date (str): Start date for data retrieval
        end_date (str): End date for data retrieval

    Returns:
        pd.DataFrame: DataFrame with ADX, PDI (Plus Directional Indicator),
                      and NDI (Minus Directional Indicator) columns added
    """
    # Import get_stock_data function from SP_historical_data
    from docs.code_snippets.SP_historical_data import get_stock_data

    # Get stock data
    data = get_stock_data(ticker, start_date, end_date)

    # Calculate ADX using pandas_ta (returns DataFrame with multiple columns)
    adx_data = data.ta.adx(high=data['High'], low=data['Low'], close=data['Close'], length=14)

    # pandas_ta returns columns: ADX_14, DMP_14, DMN_14
    # Rename to match the original function's output format
    data['ADX'] = adx_data[f'ADX_14']
    data['PDI'] = adx_data[f'DMP_14']  # Plus Directional Movement
    data['NDI'] = adx_data[f'DMN_14']  # Minus Directional Movement

    # Return the calculated data
    return data
