# 網格交易策略

## Config文件
1. platform: 交易平台, 現貨寫 binance_spot  合約寫 binance_future
2. symbol: 交易對 例如:BTCBUSD等等
3. api_key : 幣安api_key
4. api_secret: 幣安api_secret
5. gap_percent: 價格差
6. quantity : 每次下單數量
7. max_orders: 單邊下單量
8. proxy_host: 
9. proxy_port: 

## 使用時機
- 震盪行情
- 高波動幣種
- 適合現貨(合约的話需要注意極端行情可能爆倉)