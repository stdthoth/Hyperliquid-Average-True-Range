from eth_account.signers.local import LocalAccount
import eth_account
import json
import time
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants
import ccxt
import pandas as pd
import datetime
import schedule
import requests

symbol = 'ETH'
timeframe = '5m'
limit = 100

max_loss = -3
target = 9

hyper_symbol = symbol + '/USD'

def asking_bid(symbol):
    '''
    sample of output [[{'n':2,'px':768250,'sz':370},{'n':2, 'px':767850, 'sz':}]]
    notice px is in a different format, we may need to convert when we make an order 
    '''
    url = 'https://api.hyperliquid.xyz/info'
    headers = {'Content-Type':'application/json'}

    data = {
        "type":"l2Book",
        "coin": symbol
    }

    resp = requests.post(url,headers=headers,data=json.dump(data))
    l2_data = resp.json()
    l2_data = l2_data['levels']
    print(l2_data)

    #get bid price and asking price
    bid = float(l2_data[0][0]['px'])
    ask = float(l2_data[1][0]['px'])

    ask = float(ask)
    bid = float(bid)

    print(f'ask:{ask} bid: {bid}')

    return ask,bid,l2_data

def output_size_decimal(symbol):
    '''
    this outputs the  size decimals for a given symbol which is - the size you can 
    buy or sell at. for example. if size decimal == 1 then you can buy/sell at 1.4
    if size decimal == 2 then you can buy/sell at 1.45
    if size decimal == 3 then you can buy/sell at 1.456

    if size is not right then it will throw an error response code

    
    '''
    url = 'https://api.hyperliquid.xyz/info'
    headers = {'Content-Type':'application/json'}
    data = {"type":"meta"}

    resp = requests.post(url,headers=headers,data=json.dump(data))

    if resp.status_code == 200:
        data = resp.json()
        symbols = data['universe']
        symbol_info = next((s for s in symbols if s['name'] == symbol),None)
        if symbol_info:
            size_decimals =symbol_info['szDecimals']
            return size_decimals
        else:
            print('symbol not found')
    else:
        print('Error:',resp.status_code)       


