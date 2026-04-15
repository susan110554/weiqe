# chain_apis

统一的链上 API 调度层（RAD-02 与支付模块共用）。

## 目标
- 把 EVM / TRON / BTC 的外部请求入口集中管理
- 在主源失败时自动走备用源
- 统一返回错误结构，便于上层准确展示原因（401/429/timeout 等）

## 当前调度
- ETH: Etherscan
- TRON:
  - Primary: Tronscan
  - Fallback: TronGrid
- BTC:
  - Primary: blockchain.info
  - Fallback: blockstream.info

## 环境变量
- `ETHERSCAN_KEY`
- `TRONGRID_API_KEY`

> 不要把真实密钥提交到仓库，请仅写入本地 `.env`。
