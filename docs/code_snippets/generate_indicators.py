import pandas as pd
import numpy as np
import pandas_ta as ta


INDICATOR_FUNCTIONS = {
        'MACD': 'moving_average_convergence_divergence',
        'RSI': 'relative_strength_index',
        'ADX': 'average_directional_index',
        'RoC': 'rate_of_change',
        'Stoch': 'stochastic',
        'Rel_Str': 'relative_strength',
        'MAL': 'moving_averages',
        'Super': 'supertrend',
        'Para_SAR': 'psar',
        'OBI': 'obv',
        'TLEV': 'traders_lion_enhanced_volume()',
        'VPTI': 'volume_price_trend_indicator',
        'MFI': 'Money Flow Index',
        'CMFI': 'chaikin_money_flow_indicator',
        'Acc_Dis': 'accumulation_dis tribution',
        'EoM': 'ease_of_movement',
        'VaP': 'volume_at_price',
        'VWAP': 'volume_weighted_average_price',
        'BBands': 'bollinger_bands',
        'KChan': 'keltner_channel',
        'DonChan': 'donchian_channel',
        'ATR': 'Average True Range'}

def indicators(data):
    data['MACD'] = ta.macd(data['Close'])
    data['RSI'] = ta.rsi(data['Close'])
    data['ADX'] = ta.rsi(data['High'], data['Low'], data['Close'])
    data['RoC'] = ta.roc(data['Close'])
    data['SToch'] = ta.stoch(data['High'], data['Low'], data['Close'])
    data['Rel_Str'] = ta.rs(data['Close'])
    data['MAL'] = ta.sma(data['Close'])
    data['Super'] = ta.supertrend(data['High'], data['Low'], data['Close'])
    data['Para_SAR'] = ta.psar(data['High'], data['Low'], data['Close'])
    data['OBI'] = ta.obv(data['Close'], data['Volume'])
    data['TLEV'] = ta.tlev(data['Close'], data['Volume'])
    data['VPTI'] = ta.vpt(data['Close'], data['Volume'])
    data['MFI'] = ta.mfi(data['High'], data['Low'], data['Close'], data['Volume'])
    data['CMFI'] = ta.cmf(data['High'], data['Low'], data['Close'], data['Volume'])
    data['Acc_Dis'] = ta.ad(data['High'], data['Low'], data['Close'], data['Volume'])
    data['EoM'] = ta.eom(data['High'], data['Low'], data['Volume'])
    data['VaP'] = ta.vwap(data['Close'], data['Volume'])
    data['VWAP'] = ta.vwap(data['High'], data['Low'], data['Close'], data['Volume'])
    data['BBands'] = ta.bbands(data['Close'])
    data['KChan'] = ta.kc(data['High'], data['Low'], data['Close'])
    data['DonChan'] = ta.donchian(data['High'], data['Low'])
    data['ATR'] = ta.atr(data['High'], data['Low'], data['Close'], data['Volume'])
    return data