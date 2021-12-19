import logging
from utils import config
from time import sleep
from trader.binance_spot_trader import BinanceSpotTrader
from trader.binance_future_trader import BinanceFutureTrader

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    filename='log.txt')
logger = logging.getLogger('binance')

if __name__ == '__main__':
    config.loads('./config.json')  # 載入主配置

    if config.platform == 'binance_spot':
        trader = BinanceSpotTrader()
    elif config.platform == 'binance_future':
        trader = BinanceFutureTrader()
    else:
        print('輸入錯誤')

    orders = trader.http_client.cancel_open_orders(config.symbol)
    print(f"cancel orders: {orders}")

    while True:
        try:
            trader.start()
            sleep(20)

        except Exception as error:
            print(f"catch error: {error}")
            sleep(5)
