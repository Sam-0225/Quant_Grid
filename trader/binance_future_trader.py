import logging
from datetime import datetime
from gateway import BinanceFutureHttp, OrderStatus, OrderType, OrderSide
from utils import config
from utils import round_to


class BinanceFutureTrader(object):

    def __init__(self):
        """
        the grid trading in Future will endure a lot of risk， use it before you understand the risk and grid strategy.
        網格交易在合約上有很大風險，注意風控
        """
        self.http_client = BinanceFutureHttp(api_key=config.api_key, secret=config.api_secret,
                                             proxy_host=config.proxy_host, proxy_port=config.proxy_port)

        self.buy_orders = []  # 買單
        self.sell_orders = []  # 賣單
        self.symbols_dict = {}  # 幣種

    def get_exchange_info(self):
        data = self.http_client.exchange_info()
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

        # print(len(self.symbols),self.symbols)  # 129 個交易對

    def get_bid_ask_price(self):  # 取得買進價/賣出價
        ticker = self.http_client.get_ticker(config.symbol)

        if ticker:
            return float(ticker.get('bidPrice', 'Not Found')), float(ticker.get('askPrice', 'Not Found'))
        else:
            return 0, 0

    def start(self):  # 網格交易核心邏輯
        self.get_exchange_info()  # 取得交易所資訊
        symbol_data = self.symbols_dict.get(config.symbol, None)
        if symbol_data is None:
            return None

        min_price = symbol_data.get('min_price', 0)
        min_qty = symbol_data.get('min_qty', 0)

        if min_price <= 0 and min_qty <= 0:
            return None

        bid_price, ask_price = self.get_bid_ask_price()
        print(f"bid_price: {bid_price}, ask_price: {ask_price}, time: {datetime.now()}")

        quantity = round_to(float(config.quantity), float(min_qty))

        self.buy_orders.sort(key=lambda x: float(x['price']), reverse=True)  # 最高價到最低價
        self.sell_orders.sort(key=lambda x: float(x['price']), reverse=True)  # 最高價到最低價

        buy_delete_orders = []  # 需要刪除的買單
        sell_delete_orders = []  # 需要刪除的賣單
        # 買單邏輯，檢查成交狀況
        for buy_order in self.buy_orders:

            check_order = self.http_client.get_order(buy_order.get('symbol', config.symbol),
                                                     client_order_id=buy_order.get('clientOrderId'))

            if check_order:
                if check_order.get('status') == OrderStatus.CANCELED.value:
                    buy_delete_orders.append(buy_order)
                    print(f"buy order was canceled: {check_order.get('status')}, time: {datetime.now()}")
                elif check_order.get('status') == OrderStatus.FILLED.value:  # 買單成交，掛賣單
                    print(f"buy order was filled, time: {datetime.now()}")
                    logging.info(
                        f"buy order was filled, price: {check_order.get('price')}, qty: {check_order.get('origQty')}, time: {datetime.now()}")

                    sell_price = round_to(float(check_order.get("price")) * (1 + float(config.gap_percent)), min_price)

                    if 0 < sell_price < ask_price:
                        sell_price = round_to(ask_price, float(min_price))

                    new_sell_order = self.http_client.place_order(symbol=config.symbol, order_side=OrderSide.SELL,
                                                                  order_type=OrderType.LIMIT, quantity=quantity,
                                                                  price=sell_price)
                    if new_sell_order:
                        print(
                            f"buy order was filled and place the sell order: {new_sell_order}, time: {datetime.now()}")
                        buy_delete_orders.append(buy_order)
                        self.sell_orders.append(new_sell_order)

                    buy_price = round_to(float(check_order.get("price")) * (1 - float(config.gap_percent)), min_price)

                    if buy_price > bid_price > 0:
                        buy_price = round_to(buy_price, min_price)

                    new_buy_order = self.http_client.place_order(symbol=config.symbol, order_side=OrderSide.BUY,
                                                                 order_type=OrderType.LIMIT, quantity=quantity,
                                                                 price=buy_price)
                    if new_buy_order:
                        print(f"買單成交，下了更低價的買單: {new_buy_order}, 時間: {datetime.now()}")
                        self.buy_orders.append(new_buy_order)

                elif check_order.get('status') == OrderStatus.NEW.value:
                    print(f"buy order status is: New , time: {datetime.now()}")
                else:
                    print(f"buy order status is not above options: {check_order.get('status')}, time: {datetime.now()}")

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

                    print(f"sell order was canceled: {check_order.get('status')}, time: {datetime.now()}")
                elif check_order.get('status') == OrderStatus.FILLED.value:
                    logging.info(
                        f"sell order was filled, price: {check_order.get('price')}, qty: {check_order.get('origQty')}, time: {datetime.now()}")
                    # 賣單成交，下買單
                    buy_price = round_to(float(check_order.get("price")) * (1 - float(config.gap_percent)),
                                         min_price)
                    if buy_price > bid_price > 0:
                        buy_price = round_to(buy_price, min_price)

                    new_buy_order = self.http_client.place_order(symbol=config.symbol, order_side=OrderSide.BUY,
                                                                 order_type=OrderType.LIMIT, quantity=quantity,
                                                                 price=buy_price)
                    if new_buy_order:
                        print(f"sell order was filled, place buy order: {new_buy_order}, time: {datetime.now()}")
                        sell_delete_orders.append(sell_order)
                        self.buy_orders.append(new_buy_order)

                    sell_price = round_to(float(check_order.get("price")) * (1 + float(config.gap_percent)),
                                          min_price)

                    if 0 < sell_price < ask_price:
                        sell_price = round_to(ask_price, min_price)

                    new_sell_order = self.http_client.place_order(symbol=config.symbol, order_side=OrderSide.SELL,
                                                                  order_type=OrderType.LIMIT, quantity=quantity,
                                                                  price=sell_price)
                    if new_sell_order:
                        print(f"賣單成交，下了更高價的賣單: {new_sell_order},time: {datetime.now()}")
                        self.sell_orders.append(new_sell_order)

                elif check_order.get('status') == OrderStatus.NEW.value:
                    print(f"sell order is: New, time: {datetime.now()}")
                else:
                    print(
                        f"sell order status is not in above options: {check_order.get('status')}, 時間: {datetime.now()}")

        # 刪掉過期或被拒絕的訂單.
        for delete_order in sell_delete_orders:
            self.sell_orders.remove(delete_order)

        # 沒有買單時
        if len(self.buy_orders) <= 0:
            if bid_price > 0:
                price = round_to(bid_price * (1 - float(config.gap_percent)), min_price)

                buy_order = self.http_client.place_order(symbol=config.symbol, order_side=OrderSide.BUY,
                                                         order_type=OrderType.LIMIT, quantity=quantity, price=price)
                print(f'沒有買單，根據盤口下買單: {buy_order}, 時間: {datetime.now()}')
                if buy_order:
                    self.buy_orders.append(buy_order)
        else:
            self.buy_orders.sort(key=lambda x: float(x['price']), reverse=False)  # 最低價到最高價
            delete_orders = []
            for i in range(len(self.buy_orders) - 1):
                order = self.buy_orders[i]
                next_order = self.buy_orders[i + 1]

                if float(next_order['price']) / float(order['price']) - 1 < 0.001:
                    print(f"買單之間價差太小，撤銷訂單：{next_order}, 時間: {datetime.now()}")
                    cancel_order = self.http_client.cancel_order(next_order.get('symbol'),
                                                                 client_order_id=next_order.get('clientOrderId'))
                    if cancel_order:
                        delete_orders.append(next_order)

            for order in delete_orders:
                self.buy_orders.remove(order)

            if len(self.buy_orders) > int(config.max_orders):  # 最大掛單數量
                # 訂單數量較多時
                self.buy_orders.sort(key=lambda x: float(x['price']), reverse=False)  # 最低價到最高價

                delete_order = self.buy_orders[0]
                print(f"訂單太多了，撤銷最低價的買單：{delete_order}, 時間: {datetime.now()}")
                order = self.http_client.cancel_order(delete_order.get('symbol'),
                                                      client_order_id=delete_order.get('clientOrderId'))
                if order:
                    self.buy_orders.remove(delete_order)

        # 沒有賣單的時候
        if len(self.sell_orders) <= 0:
            if ask_price > 0:
                price = round_to(ask_price * (1 + float(config.gap_percent)), float(min_price))
                sell_order = self.http_client.place_order(symbol=config.symbol, order_side=OrderSide.SELL,
                                                          order_type=OrderType.LIMIT, quantity=quantity, price=price)
                print(f'沒有賣單，根據盤口下單:{sell_order} , 時間: {datetime.now()}')
                if sell_order:
                    self.sell_orders.append(sell_order)

        else:
            self.sell_orders.sort(key=lambda x: float(x['price']), reverse=False)  # 最低價到最高價
            delete_orders = []
            for i in range(len(self.sell_orders) - 1):
                order = self.sell_orders[i]
                next_order = self.sell_orders[i + 1]

                if float(next_order['price']) / float(order['price']) - 1 < 0.001:
                    print(f"賣單之間價差太小，撤銷訂單:{next_order}, 時間: {datetime.now()}")
                    cancel_order = self.http_client.cancel_order(next_order.get('symbol'),
                                                                 client_order_id=next_order.get('clientOrderId'))
                    if cancel_order:
                        delete_orders.append(next_order)

            for order in delete_orders:
                self.sell_orders.remove(order)

            if len(self.sell_orders) > int(config.max_orders):  # 最大掛單數量
                # 訂單數量較多時
                self.sell_orders.sort(key=lambda x: x['price'], reverse=True)  # 最高價到最低價

                delete_order = self.sell_orders[0]
                print(f"訂單太多了，撤銷最高價賣單：{delete_order}, 時間:{datetime.now()}")
                order = self.http_client.cancel_order(delete_order.get('symbol'),
                                                      client_order_id=delete_order.get('clientOrderId'))
                if order:
                    self.sell_orders.remove(delete_order)
