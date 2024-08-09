from eth_account.signers.local import LocalAccount
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants
from dotenv import load_dotenv

import eth_account
import json
import time
import os
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

load_dotenv()
hyper_secret = os.getenv("HYPER_SECRET")
hyper_wallet = os.getenv("HYPER_WALLET")

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

def get_datetime_to_epoch(dt):
    epoch = datetime.datetime.utcfromtimestamp(0)
    return int((dt - epoch).total_seconds() * 1000.0)

def get_timerange_in_ms(minutes_back):
    current_time_ms = int(datetime.datetime.utcnow().timestamp() * 1000)
    start_time_ms = current_time_ms - (minutes_back * 60 * 1000)
    end_time_ms = current_time_ms
    return start_time_ms,end_time_ms

def get_ohlcv(hyper_symbol,timeframe,limit):
    cb = ccxt.coinbase()
    ohlcv = cb.fetch_ohlcv(hyper_symbol,timeframe,limit=limit)
    df = pd.DataFrame(ohlcv,columns=['timestamp','open','high','low','close','volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'],unit='ms')

    df = df.tail(limit)
    df['support'] = df[:-2]['close'].min()
    df['resis'] = df[:-2]['close'].max()

    return df

def get_supply_and_demand_zones(symbol,timeframe,limit):
    '''
    we can pass in a timeframe and limit to change supply and demand zones
    it outputs a df with supply and demand zones for each time frames
    #this is the supply zone and demand zone ranges
    #row 0 is the CLOSE, row 1 is the WICK(high/low)
    #and the supply/demand zone is in between the two 
    '''
    print('calculating supply and demand zone')

    #get ohlcv data
    sdz_limit = 96
    sdz_sma = 20

    sd_df = pd.DataFrame() #supply and demand zone data frame

    df = get_ohlcv(symbol,timeframe,limit)
    print(df)

    support_1h = df.iloc[-1]['support']
    resistance_1h = df.iloc[-1]['resis']
    #print(f'this is support for 1h {support_1h} and this is resistance for 1h {resistance_1h}')

    df['supp_lo'] = df[:-2]['low'].min()
    supp_low_1h = df.iloc[-1]['supp_lo']
    #print(f'this is the support low:{supp_low_1h} and this is support {support_1h} Demand zone is ')

    df['res_hi'] = df[:-2]['high'].max()
    res_high_1h =df.iloc[-1]['res_hi']
    #print(f'this is the res high:{res_high_1h} and this is the resistace{resistance_1h} Supply Zone is')

    sd_df['1h_dz'] = [supp_low_1h,support_1h]
    sd_df['1h_sz'] = [res_high_1h,resistance_1h]

    return sd_df #this is the df where the zone is indicated per timeframe and range is between row 0 and 1

print(get_supply_and_demand_zones(hyper_symbol,timeframe,limit))


