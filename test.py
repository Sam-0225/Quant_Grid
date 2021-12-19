a = {'timezone': 'UTC',
     'serverTime': 1570802268092,
     'rateLimits': [{'rateLimitType': 'REQUEST_WEIGHT', 'interval': 'MINUTE', 'intervalNum': 1, 'limit': 1200},
                    {'rateLimitType': 'ORDERS', 'interval': 'MINUTE', 'intervalNum': 1, 'limit': 1200}],
     'exchangeFilters': [],
     'symbols': [{'symbol': 'BTCUSDT',
                  'status': 'TRADING',
                  'maintMarginPercent': '2.5000',
                  'requiredMarginPercent': '5.0000',
                  'baseAsset': 'BTC',
                  'quoteAsset': 'USDT',
                  'pricePrecision': 2,
                  'quantityPrecision': 3,
                  'baseAssetPrecision': 8,
                  'quotePrecision': 8,
                  'filters': [
                      {'minPrice': '0.01', 'maxPrice': '100000', 'filterType': 'PRICE_FILTER', 'tickSize': '0.01'},
                      {'stepSize': '0.001', 'filterType': 'LOT_SIZE', 'maxQty': '1000', 'minQty': '0.001'},
                      {'stepSize': '0.001', 'filterType': 'MARKET_LOT_SIZE', 'maxQty': '1000', 'minQty': '0.001'},
                      {'limit': 200, 'filterType': 'MAX_NUM_ORDERS'},
                      {'multiplierDown': '0.8500', 'multiplierUp': '1.1500', 'multiplierDecimal': '4',
                       'filterType': 'PERCENT_PRICE'}],
                  'orderTypes': ['LIMIT', 'MARKET', 'STOP'],
                  'timeInForce': ['GTC', 'IOC', 'FOK', 'GTX']}]
     }

symbols_dict = {}
items = a.get('symbols', [])
for item in items:
      if item.get('status') == 'TRADING':
          symbol = item['symbol']
          symbol_data = {'symbol': symbol}
          for f in item['filters']:
              if f['filterType'] == 'PRICE_FILTER':
                  symbol_data['min_price'] = float(f['tickSize'])
              elif f['filterType'] == 'LOT_SIZE':
                  symbol_data['min_qty'] = float(f['stepSize'])
              elif f['filterType'] == 'MIN_NOTIONAL':
                  symbol_data['min_notional'] = float(f['minNotional'])
#
#           symbols_dict[symbol] = symbol_data
#
# b = a.get('symbols', 'Not Found')
# print(b)
