# Binance Future http requests.

import requests, time, hmac, hashlib
from enum import Enum
from threading import Lock
from datetime import datetime


class OrderStatus(object):  # 訂單狀態:新訂單、部分完成、已完成、取消、待取消、訂單被拒絕、訂單過期
    NEW = 'NEW'
    PARTIALLY_FILLED = 'PARTIALLY_FILLED'
    FILLED = 'FILLED'
    CANCELED = 'CANCELED'
    PENDING_CANCEL = 'PENDING_CANCEL'
    REJECTED = 'REJECTED'
    EXPIRED = 'EXPIRED'


class OrderType(Enum):  # 限價單、市價單、停損單(也是按市價)
    LIMIT = 'LIMIT'
    MARKET = 'MARKET'
    STOP = 'STOP'


class RequestMethod(Enum):  # 讀取、新增、更新、刪除
    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    DELETE = 'DELETE'


class Interval(Enum): # 圖表週期
    MINUTE_1 = '1m'
    MINUTE_3 = '3m'
    MINUTE_5 = '5m'
    MINUTE_15 = '15m'
    MINUTE_30 = '30m'
    HOUR_1 = '1h'
    HOUR_2 = '2h'
    HOUR_4 = '4h'
    HOUR_6 = '6h'
    HOUR_8 = '8h'
    HOUR_12 = '12h'
    DAY_1 = '1d'
    DAY_3 = '3d'
    WEEK_1 = '1w'
    MONTH_1 = '1M'


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class BinanceFutureHttp(object):

    def __init__(self, api_key=None, secret=None, host=None, proxy_host='', proxy_port=0, timeout=5, try_counts=5):
        self.key = api_key
        self.secret = secret
        self.host = host if host else 'https://fapi.binance.com'
        self.recv_window = 5000
        self.timeout = timeout
        self.order_count_lock = Lock()
        self.order_count = 1_000_000
        self.try_counts = try_counts  # 嘗試失敗次數
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port

    @property
    def proxies(self):
        if self.proxy_host and self.proxy_port:
            proxy = f"http://{self.proxy_host}:{self.proxy_port}"
            return {"http": proxy, "https": proxy}
        return {}

    def build_parameters(self, params: dict):
        keys = list(params.keys())
        keys.sort()
        return '&'.join([f"{k}={params[k]}" for k in params.keys()])

    def request(self, req_method: RequestMethod, path: str, requery_dict=None, verify=False):
        url = self.host + path

        if verify:
            query_str = self._sign(requery_dict)
            url += '?' + query_str
        elif requery_dict:
            url += '?' + self.build_parameters(requery_dict)
        headers = {"X-MBX-APIKEY": self.key}

        for i in range(0, self.try_counts):
            try:
                response = requests.request(req_method.value, url=url, headers=headers, timeout=self.timeout,
                                            proxies=self.proxies)
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"請求失敗: {response.status_code}, 繼續嘗試請求")
            except Exception as error:
                print(f"請求{path}時發生了錯誤: {error}, 時間: {datetime.now()}")
                time.sleep(3)

    def server_time(self):
        path = '/fapi/v1/time'
        return self.request(req_method=RequestMethod.GET, path=path)

    def exchangeInfo(self):

        """
        {'timezone': 'UTC', 'serverTime': 1570802268092, 'rateLimits':
        [{'rateLimitType': 'REQUEST_WEIGHT', 'interval': 'MINUTE', 'intervalNum': 1, 'limit': 1200},
        {'rateLimitType': 'ORDERS', 'interval': 'MINUTE', 'intervalNum': 1, 'limit': 1200}],
         'exchangeFilters': [], 'symbols':
         [{'symbol': 'BTCUSDT', 'status': 'TRADING', 'maintMarginPercent': '2.5000', 'requiredMarginPercent': '5.0000',
         'baseAsset': 'BTC', 'quoteAsset': 'USDT', 'pricePrecision': 2, 'quantityPrecision': 3, 'baseAssetPrecision': 8,
         'quotePrecision': 8,
         'filters': [{'minPrice': '0.01', 'maxPrice': '100000', 'filterType': 'PRICE_FILTER', 'tickSize': '0.01'},
         {'stepSize': '0.001', 'filterType': 'LOT_SIZE', 'maxQty': '1000', 'minQty': '0.001'},
         {'stepSize': '0.001', 'filterType': 'MARKET_LOT_SIZE', 'maxQty': '1000', 'minQty': '0.001'},
         {'limit': 200, 'filterType': 'MAX_NUM_ORDERS'},
         {'multiplierDown': '0.8500', 'multiplierUp': '1.1500', 'multiplierDecimal': '4', 'filterType': 'PERCENT_PRICE'}],
         'orderTypes': ['LIMIT', 'MARKET', 'STOP'], 'timeInForce': ['GTC', 'IOC', 'FOK', 'GTX']}]}
        :return:
        """

        path = '/fapi/v1/exchangeInfo'
        return self.request(req_method=RequestMethod.GET, path=path)

    def order_book(self, symbol, limit=5):
        limits = [5, 10, 20, 50, 100, 500, 1000] # limit=0 返回全部orderbook，但数据量会非常非常非常非常大！
        if limit not in limits:
            limit = 5

        path = "/fapi/v1/depth"
        query_dict = {"symbol": symbol,
                      "limit": limit}

        return self.request(RequestMethod.GET, path, query_dict)

    def get_kline(self, symbol, interval: Interval, start_time=None, end_time=None, limit=500, max_try_time=10):
        """
        :return:
        [
            1499040000000,      // 開盤時間
            "0.01634790",       // o開盤價
            "0.80000000",       // h最高價
            "0.01575800",       // l最低價
            "0.01577100",       // c收盤價(if K線未結束 即為最新價)
            "148976.11427815",  // 成交量
            1499644799999,      // 收盤時間
            "2434.19055334",    // 成交額
            308,                // 成交筆數
            "1756.87402397",    // 主動買入成交量
            "28.46694368",      // 主動買入成交額
            "17928899.62484339" // 不用理這個
        ]
        """
        path = "/fapi/v1/klines"

        query_dict = {
            "symbol": symbol,
            "interval": interval.value,
            "limit": limit
        }

        if start_time:
            query_dict['startTime'] = start_time

        if end_time:
            query_dict['endTime'] = end_time

        for _ in range(max_try_time):
            data = self.request(RequestMethod.GET, path, query_dict)
            if isinstance(data, list) and len(data):
                return data
        return []

    def get_latest_price(self, symbol):
        path = "/fapi/v1/ticker/price"
        query_dict = {"symbol": symbol}
        return self.request(RequestMethod.GET, path, query_dict)

    def get_ticker(self, symbol):
        path = "/fapi/v1/ticker/bookTicker"
        query_dict = {"symbol": symbol}
        return self.request(RequestMethod.GET, path, query_dict)

    def get_all_tickers(self):
        path = "/fapi/v1/ticker/bookTicker"
        return self.request(RequestMethod.GET, path)

    ########################### the following request is for private data ########################

    def _timestamp(self):
        return int(time.time() * 1000)

    def _sign(self, params):
        requery_string = self.build_parameters(params)
        hexdigest = hmac.new(self.secret.encode('utf8'), requery_string.encode("utf-8"), hashlib.sha256).hexdigest()
        return requery_string + '&signature=' + str(hexdigest)

    def get_client_order_id(self):
        """
        generate the client_order_id for user.
        :return: new client order id
        """
        with self.order_count_lock:
            self.order_count += 1
            return "x-cLbi5uMH" + str(self._timestamp()) + str(self.order_count)

    def place_order(self, symbol: str, order_side: OrderSide, order_type: OrderType, quantity, price,
                    time_inforce="GTC", client_order_id=None, recvWindow=5000, stop_price=0):

        """
        下單
        :param symbol: BTCBUSD
        :param side: BUY or SELL
        :param type: LIMIT MARKET STOP
        :param quantity: 數量
        :param price: 價格
        :param stop_price: 止損單價格
        :param time_inforce:
        :param params: 其他參數
        LIMIT : timeInForce, quantity, price
        MARKET : quantity
        STOP: quantity, price, stopPrice
        :return:
        """

        path = '/fapi/v1/order'

        if client_order_id is None:
            client_order_id = self.get_client_order_id()

        params = {
            "symbol": symbol,
            "side": order_side.value,
            "type": order_type.value,
            "quantity": quantity,
            "price": price,
            "recvWindow": recvWindow,
            "timeInForce": "GTC",
            "timestamp": self._timestamp(),
            "newClientOrderId": client_order_id
        }

        if order_type == OrderType.LIMIT:
            params['timeInForce'] = time_inforce

        if order_type == OrderType.MARKET and params.get('price'):
            del params['price']

        if order_type == OrderType.STOP:
            if stop_price > 0:
                params["stopPrice"] = stop_price
            else:
                raise ValueError("stopPrice must greater than 0")

        return self.request(RequestMethod.POST, path=path, requery_dict=params, verify=True)

    def get_order(self, symbol, client_order_id=None):
        path = "/fapi/v1/order"
        query_dict = {"symbol": symbol, "timestamp": self._timestamp()}
        if client_order_id:
            query_dict["origClientOrderId"] = client_order_id

        return self.request(RequestMethod.GET, path, query_dict, verify=True)

    def cancel_order(self, symbol, client_order_id=None):
        path = "/fapi/v1/order"
        params = {"symbol": symbol, "timestamp": self._timestamp()}
        if client_order_id:
            params["origClientOrderId"] = client_order_id

        return self.request(RequestMethod.DELETE, path, params, verify=True)

    def get_open_orders(self, symbol=None):
        path = "/fapi/v1/openOrders"

        params = {"timestamp": self._timestamp()}
        if symbol:
            params["symbol"] = symbol

        return self.request(RequestMethod.GET, path, params, verify=True)

    def cancel_open_orders(self, symbol):
        """
        撤銷某交易對的所有掛單
        :param symbol: symbol
        :return: return a list of orders.
        """
        path = "/fapi/v1/allOpenOrders"

        params = {"timestamp": self._timestamp(),
                  "recvWindow": self.recv_window,
                  "symbol": symbol}

        return self.request(RequestMethod.DELETE, path, params, verify=True)

    def get_balance(self):
        """
        [{'accountId': 18396, 'asset': 'USDT', 'balance': '530.21334791', 'withdrawAvailable': '530.21334791', 'updateTime': 1570330854015}]
        :return:
        """
        path = "/fapi/v1/balance"
        params = {"timestamp": self._timestamp()}

        return self.request(RequestMethod.GET, path=path, requery_dict=params, verify=True)

    def get_account_info(self):
        """
        {'feeTier': 2, 'canTrade': True, 'canDeposit': True, 'canWithdraw': True, 'updateTime': 0, 'totalInitialMargin': '0.00000000',
        'totalMaintMargin': '0.00000000', 'totalWalletBalance': '530.21334791', 'totalUnrealizedProfit': '0.00000000',
        'totalMarginBalance': '530.21334791', 'totalPositionInitialMargin': '0.00000000', 'totalOpenOrderInitialMargin': '0.00000000',
        'maxWithdrawAmount': '530.2133479100000', 'assets':
        [{'asset': 'USDT', 'walletBalance': '530.21334791', 'unrealizedProfit': '0.00000000', 'marginBalance': '530.21334791',
        'maintMargin': '0.00000000', 'initialMargin': '0.00000000', 'positionInitialMargin': '0.00000000', 'openOrderInitialMargin': '0.00000000',
        'maxWithdrawAmount': '530.2133479100000'}]}
        :return:
        """
        path = "/fapi/v1/account"
        params = {"timestamp": self._timestamp()}
        return self.request(RequestMethod.GET, path, params, verify=True)

    def get_position_info(self):
        """
        [{'symbol': 'BTCUSDT', 'positionAmt': '0.000', 'entryPrice': '0.00000', 'markPrice': '8326.40833498', 'unRealizedProfit': '0.00000000', 'liquidationPrice': '0'}]
        :return:
        """
        path = "/fapi/v1/positionRisk"
        params = {"timestamp": self._timestamp()}
        return self.request(RequestMethod.GET, path, params, verify=True)


if __name__ == '__main__':
    # import pandas as pd

    key = ''
    secret = ''
    binance = BinanceFutureHttp(api_key=key, secret=secret)

    # import datetime
    # print(datetime.datetime.now())

    data = binance.get_kline('BTCUSDT', Interval.HOUR_1, limit=100)
    print(data)
    print(isinstance(data, list))

    exit()
    # info = binance.exchangeInfo()
    # print(info)
    # exit()
    # print(binance.order_book(symbol='BTCUSDT', limit=5))
    # exit()

    # print(binance.latest_price('BTCUSDT'))
    # kline = binance.kline('BTCUSDT', interval='1m')
    # print(pd.DataFrame(kline))

    # print(binance.ticker("BTCUSDT"))

    # print(binance.get_ticker('BTCUSDT'))
    # {'symbol': 'BTCUSDT', 'side': 'SELL', 'type': 'LIMIT', 'quantity': 0.001, 'price': 8360.82, 'recvWindow': 5000, 'timestamp': 1570969995974, 'timeInForce': 'GTC'}

    # data = binance.place_order(symbol="BTCUSDT", side=OrderSide.BUY, order_type=OrderType.MARKET, quantity=0.001, price=8250.82)
    # print(data)

    # cancel_order = binance.cancel_order("BTCUSDT", order_id="30714952")
    # print(cancel_order)

    # balance = binance.get_balance()
    # print(balance)

    # account_info = binance.get_account_info()
    # print(account_info)

    # account_info = binance.get_position_info()
    # print(account_info)

    """
    {'orderId': 30714952, 'symbol': 'BTCUSDT', 'accountId': 18396, 'status': 'NEW', 'clientOrderId': 'ZC3qSbzbODl0GId9idK9hM', 'price': '7900', 'origQty': '0.010', 'executedQty': '0', 'cumQty': '0', 'cumQuote': '0', 'timeInForce': 'GTC', 'type': 'LIMIT', 'reduceOnly': False, 'side': 'BUY', 'stopPrice': '0', 'updateTime': 1569658787083}
    {'orderId': 30714952, 'symbol': 'BTCUSDT', 'accountId': 18396, 'status': 'NEW', 'clientOrderId': 'ZC3qSbzbODl0GId9idK9hM', 'price': '7900', 'origQty': '0.010', 'executedQty': '0', 'cumQty': '0', 'cumQuote': '0', 'timeInForce': 'GTC', 'type': 'LIMIT', 'reduceOnly': False, 'side': 'BUY', 'stopPrice': '0', 'updateTime': 1569658787083}
    """
