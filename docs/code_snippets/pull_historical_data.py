import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mpl_finance import candlestick_ohlc
import pandas_ta as ta
import datetime


# When you run 
ticker, start, end = "all", '2001-1-1', '2023-3-8'

def get_stock_data(ticker, start_date, end_date):
    data = yf.download(ticker, start=start_date, end=end_date)
    data = data.reset_index()
    data = data[['Date', 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']]
    return data

df = pd.read_csv(r'nasdaq_screener_1678574871718.csv')
nasdaq_dict = {}
for i in df.index:
    key = df.loc[i]['Name']
    value = df.loc[i]['Symbol']
    nasdaq_dict[key] = value

stock_dict = {}
for k,v in nasdaq_dict.items():
    hist_data = get_stock_data(v, start, end)
    stock_dict[v] = hist_data
    stock_dict[v] = k.set_index(k.columns[0])


results = []
for k in stock_dict.keys():
    if "/" in k:
        results.append(k)

stock_dict['AKO^B'] = stock_dict.pop('AKO/B')
stock_dict['BF^B'] = stock_dict.pop('BF/B')
stock_dict['BIO^B'] = stock_dict.pop('BIO/B')
stock_dict['BRK^B'] = stock_dict.pop('BRK/B')
stock_dict['CRD^B'] = stock_dict.pop('CRD/B')
stock_dict['HEI^A'] = stock_dict.pop('HEI/A')
stock_dict['HVT^A'] = stock_dict.pop('HVT/A')

for k,v in stock_dict.items():
    v.to_csv(rf'C:\Users\nicho\Desktop\stock_ai\hist_stock_data\{k}.csv')

fails_dict = {}
fails_set = set()
for i in l:
    if i != "[*********************100%***********************]  1 of 1 completed":
        ticker, explanation = i.split(':')
        fails_dict[ticker] = explanation
        fails_set.update(explanation)
with open(r"C:\Users\nicho\Desktop\stock_ai\failed_list.txt", 'r') as f:
    corpus = f.read()

