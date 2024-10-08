from eth_account.signers.local import LocalAccount
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants
from dotenv import load_dotenv
from typing import List
from decimal import Decimal

import eth_account
import json
import time
import os
import ccxt
import pandas as pd
import datetime
import schedule
import random
import requests

load_dotenv()
hyper_secret = os.getenv("HYPER_SECRET")
hyper_wallet = os.getenv("HYPER_WALLET")

symbol = 'ETH'
timeframe = '5m'
limit = 100

max_loss = -3
target = 9

hyper_symbol = symbol + '/USD'
max_trading_range = 30
no_trading_hrs = 7

min_acc_value = 5


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

def get_leverage():
    '''
    this function sets the leverage, calculates size and gets signal from a signal.txt file
    #options are n for neutral 
    #b60, b70, s60, s70 for skewed
    '''
    leverage = 20
    #get balance
    #get volume

    print('leverage:',leverage)

    #get signals from file
    with open(",/signals.txt") as file:
        signal = file.read().strip()
    
    #initialize long only and short only values to false
    long_only = False
    short_only = False

    print(f'this is the signal {signal}')

    #update the long and short based on the signal
    if signal == 'n':
        long_only = False
        short_only = False
    elif signal == 'b60':
        long_only = (random.random() < 0.6)
        short_only = False
    elif signal == 'b70':
        long_only == (random.random() < 0.7)
        short_only == False
    elif signal == 's60':
        long_only == False
        short_only == (random.random() < 0.6)
    elif signal == 's70':
        long_only == False
        short_only == (random.random() < 0.7)

    print('leverage:',leverage,'signal:',signal)

    account:LocalAccount = eth_account.Account.from_key(hyper_secret)
    exchange = Exchange(account.address,constants.MAINNET_API_URL)
    info = Info(constants.MAINNET_API_URL,skip_ws=True)
    
    #get the user_state and print out leverage information
    user_state = info.user_state(account.address)
    account_value = user_state["marginSummary"]["accountValue"]
    account_value = float(account_value)
    print(account_value)

    account_value_95 = account_value * .95
    #print(f'current leverage for {symbol}:')
    #print(json.dumps(user_state["assetPositions"][exchange.coin_to_asset[symbol]["position"]]))

    #print('adjusting leverage...')
    #Set the ETH leverage to 21x cross margin
    print(exchange.update_leverage(leverage,symbol))
    price = asking_bid(symbol)[0]

    size = (account_value_95/price) * leverage
    size = int(size)
    print(f'this is the size that we can use for 95% of acct value {size}')


    user_state = info.user_state(account.address)
    #print('current leverage for {symbol}:')
    #print(json.dumps(user_state["assetPositions"][exchange.coin_to_asset[symbol]["position"]]))

    return leverage, size,long_only,short_only



def limit_order(coin:str,is_buy:bool,sz:float,limit_px:float,reduce_only:bool=False):
    account:LocalAccount = eth_account.Account.from_key(hyper_secret)
    exchange = Exchange(account,constants.MAINNET_API_URL)
    sz = round(sz,1)
    limit_px = round(limit_px,1)
    print(f'placing limit order for {coin} with size {sz} at {limit_px}')
    order_res = exchange.order(coin,is_buy,sz,limit_px,{"limit":{"tif":"Gtc"}},reduce_only=reduce_only)
    if is_buy == True:
        print(f"limit BUY order placed resting:{order_res['response']['data']['statuses'][0]}")
    else:
        print(f"limit SELL order placed, resting:{order_res['response']['data']['statuses'][0]}")

    return order_res

def get_position():
    account:LocalAccount= eth_account.Account.from_key(hyper_secret)
    info = Info(constants.MAINNET_API_URL,skip_ws=True)
    user_state = info.user_state(account.address)
    print(f"this is the current account value:{user_state['margin_summary']['account_value']}")

    positions = []

    for position in user_state["assetPositions"]:
        #print(float(position["position"]["szi"]))
        if (position["position"]['coin'] == symbol) and float(position["position"]["szi"]) != 0:
            positions.append(position["positions"])
            in_pos = True
            size = float(position["position"]["szi"])
            pos_sym = position["position"]["coin"]
            entry_px = float(position["position"]["entryPx"])
            pnl_percentage = float(position["position"]["returnOnEquity"]) * 100
            #print(f'this is the pnl{pnl_perc}')
            break
        else:
            in_pos= False
            size = 0
            pos_sym = None
            entry_px = 0
            pnl_percentage = 0

    if size > 0:
        long = True
    elif size < 0:
        long = False
    else:
        long = None

    return positions,in_pos,pos_sym,entry_px,pnl_percentage,long

def cancel_all_orders():
    '''
    This cancels all open orders on hyperliquid
    '''
    account:LocalAccount = eth_account.Account.from_key(hyper_secret)
    exchange = Exchange(account.address,constants.MAINNET_API_URL)
    info = Info(constants.MAINNET_API_URL,skip_ws=True)
    open_orders = info.open_orders(account.address)

    #print(open_orders)
    print("these are the open orders.. want to cancel")

    for open in open_orders:
        #print(f'cancelling all orders{open}')
        exchange.cancel(open["coin"],open["oid"])

def get_open_order_prices() -> List[Decimal]:
    account = eth_account.Account.from_key(hyper_secret)
    exchange = Exchange(account.address,constants.MAINNET_API_URL)
    info = Info(constants.MAINNET_API_URL,skip_ws=True)
    open_orders = info.open_orders(account.address)

    open_order_prices = []
    for open in open_orders:
        open_order_prices.append(Decimal(open["limitPx"]))

    return open_order_prices

def kill_switch(symbol):
    positions,in_pos,pos_size,pos_sym,entry_px,pnl_perc,long = get_position()
    while in_pos == True:
        cancel_all_orders()

        ask_bid = asking_bid(pos_sym)
        ask = ask_bid[0]
        bid = ask_bid[1]

        pos_size = abs(pos_size)

        if long == True:
            limit_order(pos_sym,False,pos_size,ask)
            print('kill switch --- SELL TO CLOSE TRADE SUBMITTED')
            time.sleep(3)
        elif long == False:
            limit_order(pos_sym,True,pos_size,bid)
            print('kill switch --- BUY TO CLOSE TRADE SUBMITTED')
            time.sleep(3)

        positions,in_pos,pos_size,pos_sym,entry_px,pnl_perc,long = get_position()
    
    print('positions terminated successfully')

def close_with_pnl():
    '''
    manage loss with pnl close
    '''
    print('closing pnl')
    positions,in_pos,pos_size,pos_sym,entry_px,pnl_perc,long = get_position()
    if pnl_perc > target:
        print(f'pnl gain is {pnl_perc} and target is {target}... closing position W ✅')
        kill_switch(pos_sym)
    elif pnl_perc <= max_loss:
        print(f'pnl loss is {pnl_perc} and max loss is {max_loss}.... closing position L ❌')
        kill_switch(pos_sym)
    else:
        print(f'pnl loss is {pnl_perc} and max loss is {max_loss} and target {target}... not CLOSED')
    print('finished with pnl_close')

def trading_range(data):
    data['previous_close'] = data['close'].shift(1)
    data['high-low'] = abs(data['high']-data['low'])
    data['high-pc'] = abs(data['high']-data['previous_close'])
    data['low-pc'] = abs(data['low']-data['previous_close'])

    trading_range = data[['high-low','high-pc','low-pc']].max(axis=1)
    return trading_range

def average_true_range(data,time):
    data['tr'] = trading_range(data)
    average_true_range = data['tr'].rolling(time).mean()
    return average_true_range

def no_trading(data, time):
    data['no_trading'] = (data['tr' > max_trading_range]).any()
    #if any are above the max trading range, it is not tradeable, so we want False
    no_trading = data['no_trading']

    return no_trading

def get_atr_no_trading():
    bars = get_ohlcv('BTC/USD',timeframe='1h',limit=no_trading_hrs)
    df = pd.DataFrame(bars[:-1],columns=['timestamp','open','high','close','volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'],unit='ms')

    atr = average_true_range(df,3)
    #print(atr)

    df['no_trading'] = (df['tr'] > max_trading_range).any()
    #if any are above tht max trading range we want to return a false

    no_trading = df['no_trading'].iloc[-1]
    #print(df)

    print(f'no trading {no_trading}')    

def bot():
    sdz = get_supply_and_demand_zones(symbol,timeframe,limit)
    #print(sdz)
    sz_1hr = sdz['1h_sz']
    sz_1hr_0 = sz_1hr.iloc[0]
    sz_1hr_1 = sz_1hr.iloc[-1]


    dz_1h = sdz['1h_dz']
    dz_1hr_0 = dz_1h.iloc[0]
    dz_1h_1 = dz_1h.iloc[-1]

    buy1 = max(dz_1hr_0,dz_1h_1)
    buy2 = (dz_1hr_0 + dz_1h_1) / 2
    #print(buy1,buy2)

    #if it is a sell - sell #1 at the lowest and #2 at the average
    sell1 =min(sz_1hr_0,sz_1hr_1)
    sell2 =(sz_1hr_0 + sz_1hr_1) / 2

    #see if in any positions - if no place an order
    position, in_pos,pos_size, pos_sym,entry_px,pnl_perc,long = get_position()
    #print(position, in_pos,pos_size, pos_sym,entry_px,pnl_perc,long)
    print(f'position size is {pos_size} in pos is {in_pos} pnl pnl_percentage is {pnl_perc} and long is {long}')

    openorders = get_open_order_prices()
    #print(openorders)
    openorders = [float(d) for d in openorders]

    if buy2 and sell2 in openorders:
        new_orders = False
        print('buy2 and sell2 are in open orders')
    else:
        new_orders = True
        print('no open orders')
    
    account:LocalAccount = eth_account.Account.from_key(hyper_secret)
    info = Info(constants.MAINNET_API_URL,skip_ws=True)
    user_state = info.user_state(account.address)
    account_value = user_state["marginSummary"]["accountValue"]
    account_value = float(account_value)

    #check the ATR to see if we need to set no trading as true
    no_trading = get_atr_no_trading()
    if account_value < min_acc_value:
        no_trading = True

    if not in_pos and new_orders == True and no_trading == False:

        print('not in position... setting orders...')

        #cancel all orders
        cancel_all_orders()

        leverage,size,long_only,short_only = get_leverage()

        if long_only == True:
            #create a buy order
            #buy1 = limit_order(symbol.True,size,buy2,False)
            buy1 = limit_order(symbol,True,size,buy2,False)
        elif short_only == True:
            #create a sell order
            #sell1 = limit_order(symbol.False,size,sell2,False)
            sell2 = limit_order(symbol,False,size,sell2,False)
        else:
            buy2 = limit_order(symbol,True,size/2,buy2,False)
            sell2 = limit_order(symbol,False,size/2,sell2,False)
    
    elif in_pos and no_trading == False:
        print('we are in positions.... checking PNL hit')
        close_with_pnl()
    elif no_trading == True:
        cancel_all_orders()
        kill_switch(pos_sym)
    else:
        print('orders are set 😎..')

    time.sleep(3)