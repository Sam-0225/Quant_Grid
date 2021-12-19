import logging
from datetime import datetime
from gateway import BinanceSpotHttp, OrderStatus, OrderType, OrderSide
from utils import config, round_to


class BinanceSpotTrader(object):

    def __init__(self):
        self.http_client = BinanceSpotHttp(api_key=config.api_key, secret=config.api_secret,
                                           proxy_host=config.proxy_host, proxy_port=config.proxy_port)

        self.buy_orders = []  # 買單
        self.sell_orders = []  # 賣單
        self.symbols_dict = {}  # 幣種

    def get_exchange_info(self):
        data = self.http_client.get_exchange_info()
        if isinstance(data, dict):
            items = data.get('symbols', [])
            for item in items:
                if item.get('status') == 'TRADING':
                    symbol = item['symbol']
                    symbol_data = {'symbol': symbol}
                    for filters in item['filters']:
                        if filters['filterType'] == 'PRICE_FILTER':
                            symbol_data['min_price'] = float(filters['tickSize'])
                        elif filters['filterType'] == 'LOT_SIZE':
                            symbol_data['min_qty'] = float(filters['stepSize'])
                        elif filters['filterType'] == 'MIN_NOTIONAL':
                            symbol_data['min_notional'] = float(filters['minNotional'])

                    self.symbols_dict[symbol] = symbol_data

    def get_bid_ask_price(self):  # 取得買進價/賣出價
        ticker = self.http_client.get_ticker(config.symbol)

        if ticker:
            return float(ticker.get('bidPrice', 'Not Found')), float(ticker.get('askPrice', 'Not Found'))
        else:
            return 0, 0

    def start(self):   # 網格交易核心邏輯

        self.get_exchange_info()  # 取得交易所資訊
        symbol_data = self.symbols_dict.get(config.symbol, None)
        if symbol_data is None:
            return None

        min_price = symbol_data.get('min_price', 0)
        min_qty = symbol_data.get('min_qty', 0)

        if min_price <= 0 and min_qty <= 0:
            return None

        bid_price, ask_price = self.get_bid_ask_price()
        print(f"bid_price: {bid_price}, ask_price: {ask_price}")

        quantity = round_to(float(config.quantity), min_qty)  # 處理小數位數

        self.buy_orders.sort(key=lambda x: float(x['price']), reverse=True)  # 最高價到最低價
        self.sell_orders.sort(key=lambda x: float(x['price']), reverse=True)  # 最高價到最低價
        print(f"buy orders: {self.buy_orders}")
        print("------------------------------")
        print(f"sell orders: {self.sell_orders}")

        buy_delete_orders = []  # 需要刪除的買單
        sell_delete_orders = []  # 需要刪除的賣單

        # 買單邏輯，檢查成交狀況
        for buy_order in self.buy_orders:

            check_order = self.http_client.get_order(buy_order.get('symbol', config.symbol),
                                                     client_order_id=buy_order.get('clientOrderId'))

            if check_order:
                if check_order.get('status') == OrderStatus.CANCELED.value:
                    buy_delete_orders.append(buy_order)
                    print(f"buy order status was canceled: {check_order.get('status')}")
                elif check_order.get('status') == OrderStatus.FILLED.value:  # 買單成交，掛賣單
                    logging.info(
                        f"買單成交時間: {datetime.now()}, 價格: {check_order.get('price')}, 數量: {check_order.get('origQty')}")

                    sell_price = round_to(float(check_order.get("price")) * (1 + float(config.gap_percent)), min_price)

                    if 0 < sell_price < ask_price:
                        sell_price = round_to(ask_price, min_price)

                    new_sell_order = self.http_client.place_order(symbol=config.symbol, order_side=OrderSide.SELL,
                                                                  order_type=OrderType.LIMIT, quantity=quantity,
                                                                  price=sell_price)
                    if new_sell_order:
                        buy_delete_orders.append(buy_order)
                        self.sell_orders.append(new_sell_order)

                    buy_price = round_to(float(check_order.get('price')) * (1 - float(config.gap_percent)), min_price)
                    if buy_price > bid_price > 0:
                        buy_price = round_to(bid_price, min_price)

                    new_buy_order = self.http_client.place_order(symbol=config.symbol, order_side=OrderSide.BUY,
                                                                 order_type=OrderType.LIMIT, quantity=quantity,
                                                                 price=buy_price)
                    if new_buy_order:
                        self.buy_orders.append(new_buy_order)

                elif check_order.get('status') == OrderStatus.NEW.value:
                    print('buy order status is: New')
                else:
                    print(f"buy order status is not above options: {check_order.get('status')}")

        # 刪掉過期或被拒絕的訂單.
        for delete_order in buy_delete_orders:
            self.buy_orders.remove(delete_order)

        # 賣單邏輯，檢查賣單狀況
        for sell_order in self.sell_orders:
            check_order = self.http_client.get_order(sell_order.get('symbol', config.symbol),
                                                     client_order_id=sell_order.get('clientOrderId'))
            if check_order:
                if check_order.get('status') == OrderStatus.CANCELED.value:
                    sell_delete_orders.append(sell_order)

                    print(f"sell order status was canceled: {check_order.get('status')}")
                elif check_order.get('status') == OrderStatus.FILLED.value:
                    logging.info(
                        f"賣單成交時間: {datetime.now()}, 價格: {check_order.get('price')}, 數量: {check_order.get('origQty')}")
                    # 賣單成交，下買單
                    buy_price = round_to(float(check_order.get('price')) * (1 - float(config.gap_percent)),
                                         min_price)
                    if buy_price > bid_price > 0:
                        buy_price = round_to(bid_price, min_price)

                    new_buy_order = self.http_client.place_order(symbol=config.symbol, order_side=OrderSide.BUY,
                                                                 order_type=OrderType.LIMIT, quantity=quantity,
                                                                 price=buy_price)
                    if new_buy_order:
                        sell_delete_orders.append(sell_order)
                        self.buy_orders.append(new_buy_order)

                    sell_price = round_to(float(check_order.get('price')) * (1 + float(config.gap_percent)), min_price)

                    if 0 < sell_price < ask_price:
                        sell_price = round_to(ask_price, min_price)

                    new_sell_order = self.http_client.place_order(symbol=config.symbol, order_side=OrderSide.SELL,
                                                                  order_type=OrderType.LIMIT, quantity=quantity,
                                                                  price=sell_price)
                    if new_sell_order:
                        self.sell_orders.append(new_sell_order)

                elif check_order.get('status') == OrderStatus.NEW.value:
                    print('sell order status is: New')
                else:
                    print(f"sell order status is not in above options: {check_order.get('status')}")

        # 刪掉過期或被拒絕的訂單.
        for delete_order in sell_delete_orders:
            self.sell_orders.remove(delete_order)

        # 沒有買單時
        if len(self.buy_orders) <= 0:
            if bid_price > 0:
                price = round_to(bid_price * (1 - float(config.gap_percent)), min_price)
                buy_order = self.http_client.place_order(symbol=config.symbol, order_side=OrderSide.BUY,
                                                         order_type=OrderType.LIMIT, quantity=quantity, price=price)
                if buy_order:
                    self.buy_orders.append(buy_order)

        elif len(self.buy_orders) > int(config.max_orders):  # 最大掛單數量
            # 訂單數量多時
            self.buy_orders.sort(key=lambda x: float(x['price']), reverse=False)  # 最低價到最高價

            delete_order = self.buy_orders[0]
            order = self.http_client.cancel_order(delete_order.get('symbol'),
                                                  client_order_id=delete_order.get('clientOrderId'))
            if order:
                self.buy_orders.remove(delete_order)

        # 沒有賣單時
        if len(self.sell_orders) <= 0:
            if ask_price > 0:
                price = round_to(ask_price * (1 + float(config.gap_percent)), min_price)
                order = self.http_client.place_order(symbol=config.symbol, order_side=OrderSide.SELL,
                                                     order_type=OrderType.LIMIT, quantity=quantity, price=price)
                if order:
                    self.sell_orders.append(order)

        elif len(self.sell_orders) > int(config.max_orders):  # 最大掛單數量
            # 訂單數量多時
            self.sell_orders.sort(key=lambda x: x['price'], reverse=True)  # 最高價到最低價

            delete_order = self.sell_orders[0]
            order = self.http_client.cancel_order(delete_order.get('symbol'),
                                                  client_order_id=delete_order.get('clientOrderId'))
            if order:
                self.sell_orders.remove(delete_order)

