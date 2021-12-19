# -*- coding:utf-8 -*-
import json


class Config:

    def __init__(self):

        self.platform: str = 'binance_spot'
        self.symbol: str = 'BTCBUSD'  # 交易對
        self.api_key: str = None
        self.api_secret: str = None

        self.gap_percent: float = 0.01  # 網格變化交易單位
        self.quantity: float = 1
        self.max_orders: int = 1
        self.proxy_host: str = ''  # proxy host
        self.proxy_port: int = 0  # proxy port

    def loads(self, config_file=None):
        configures = {}
        if config_file:
            try:
                with open(config_file) as f:
                    data = f.read()
                    configures = json.loads(data)
            except Exception as e:
                print(e)
                exit(0)
            if not configures:
                print("config json file error!")
                exit(0)
        self._update(configures)

    def _update(self, update_fields):
        for k, v in update_fields.items():
            setattr(self, k, v)


config = Config()

