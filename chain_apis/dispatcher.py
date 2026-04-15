from __future__ import annotations

import os
from typing import Any

import httpx

ETHERSCAN_KEY = (os.getenv("ETHERSCAN_KEY") or "").strip()
TRONGRID_API_KEY = (os.getenv("TRONGRID_API_KEY") or "").strip()
TRONSCAN_BASE = "https://apilist.tronscanapi.com/api"
TRONGRID_BASE = "https://api.trongrid.io"
BTC_PRIMARY_BASE = "https://blockchain.info"
BTC_FALLBACK_BASE = "https://blockstream.info/api"


def _base_headers() -> dict[str, str]:
    return {
        "User-Agent": "weiquan-bot-chain-dispatch/1.0",
        "Accept": "application/json, text/plain, */*",
    }


def _trongrid_headers() -> dict[str, str]:
    h = _base_headers()
    if TRONGRID_API_KEY:
        h["TRON-PRO-API-KEY"] = TRONGRID_API_KEY
    return h


async def _get_json(
    client: httpx.AsyncClient, url: str, *, headers: dict[str, str] | None = None
) -> tuple[dict[str, Any] | list[Any] | None, dict[str, Any] | None]:
    try:
        r = await client.get(url, timeout=25.0, headers=headers)
    except httpx.TimeoutException:
        return None, {"error": "timeout"}
    except Exception as e:
        return None, {"error": str(e)}
    if r.status_code >= 400:
        body = (r.text or "").strip().replace("\n", " ")[:240]
        return None, {"error": f"http_{r.status_code}", "status": r.status_code, "body": body}
    try:
        return r.json(), None
    except Exception:
        body = (r.text or "").strip().replace("\n", " ")[:240]
        return None, {"error": "invalid_json", "status": r.status_code, "body": body}


async def fetch_eth_txlist(client: httpx.AsyncClient, address: str, *, offset: int = 20) -> tuple[list[dict], dict | None]:
    url = (
        "https://api.etherscan.io/api?module=account&action=txlist"
        f"&address={address}&startblock=0&endblock=99999999&page=1&offset={offset}&sort=desc"
        f"&apikey={ETHERSCAN_KEY}"
    )
    data, err = await _get_json(client, url, headers=_base_headers())
    if err:
        return [], err
    if isinstance(data, dict) and data.get("status") == "1":
        rows = data.get("result") or []
        return rows if isinstance(rows, list) else [], None
    if isinstance(data, dict) and "No transactions" in str(data.get("result", "")):
        return [], None
    return [], {"error": "etherscan_unexpected", "body": str(data)[:200]}


async def fetch_eth_balance(client: httpx.AsyncClient, address: str) -> tuple[float | None, dict | None]:
    url = (
        "https://api.etherscan.io/api?module=account&action=balance"
        f"&address={address}&tag=latest&apikey={ETHERSCAN_KEY}"
    )
    data, err = await _get_json(client, url, headers=_base_headers())
    if err:
        return None, err
    if isinstance(data, dict) and data.get("status") == "1":
        try:
            return int(data.get("result", 0)) / 1e18, None
        except Exception:
            return None, {"error": "etherscan_balance_parse"}
    return None, {"error": "etherscan_balance_unexpected", "body": str(data)[:200]}


async def fetch_eth_contract_abi(
    client: httpx.AsyncClient, address: str
) -> tuple[dict | None, dict | None]:
    url = (
        "https://api.etherscan.io/api?module=contract&action=getabi"
        f"&address={address}&apikey={ETHERSCAN_KEY}"
    )
    data, err = await _get_json(client, url, headers=_base_headers())
    if err:
        return None, err
    if isinstance(data, dict):
        return data, None
    return None, {"error": "etherscan_contract_unexpected", "body": str(data)[:200]}


async def fetch_btc_raw_address(client: httpx.AsyncClient, address: str) -> tuple[dict | None, dict | None]:
    d1, e1 = await _get_json(client, f"{BTC_PRIMARY_BASE}/rawaddr/{address}?limit=10", headers=_base_headers())
    if d1 is not None and isinstance(d1, dict):
        return d1, None
    d2, e2 = await _get_json(client, f"{BTC_FALLBACK_BASE}/address/{address}", headers=_base_headers())
    if d2 is not None and isinstance(d2, dict):
        # Normalize to blockchain.info-like keys used by existing logic.
        chain_stats = d2.get("chain_stats") or {}
        funded = int(chain_stats.get("funded_txo_sum") or 0)
        spent = int(chain_stats.get("spent_txo_sum") or 0)
        norm = {
            "n_tx": int(chain_stats.get("tx_count") or 0),
            "total_received": funded,
            "total_sent": spent,
            "final_balance": funded - spent,
        }
        return norm, None
    return None, e1 or e2 or {"error": "btc_all_sources_failed"}


async def fetch_tron_account(client: httpx.AsyncClient, address: str) -> tuple[dict | None, dict | None]:
    # Primary: Tronscan
    d1, e1 = await _get_json(
        client,
        f"{TRONSCAN_BASE}/accountv2?address={address}",
        headers=_base_headers(),
    )
    if d1 is not None and isinstance(d1, dict):
        d1["source"] = "tronscan"
        return d1, None

    # Fallback: TronGrid
    d2, e2 = await _get_json(
        client,
        f"{TRONGRID_BASE}/v1/accounts/{address}",
        headers=_trongrid_headers(),
    )
    if d2 is not None and isinstance(d2, dict):
        rows = d2.get("data") or []
        row = rows[0] if rows else {}
        trc20 = row.get("trc20") or []
        balances = []
        for item in trc20:
            if not isinstance(item, dict):
                continue
            for token, qty in item.items():
                token_up = str(token or "").upper()
                if token_up.startswith("T") and len(token_up) >= 30:
                    # Contract address as key; keep raw for caller.
                    balances.append({"tokenAddr": token, "quantity": qty, "tokenAbbr": token})
        norm = {
            "source": "trongrid",
            "transactions_in": 0,
            "transactions_out": 0,
            "balance": row.get("balance") or 0,
            "balances": balances,
            "_raw": row,
        }
        return norm, None
    return None, e1 or e2 or {"error": "tron_account_all_sources_failed"}


async def fetch_tron_latest_block(client: httpx.AsyncClient) -> tuple[int | None, dict | None]:
    d1, e1 = await _get_json(client, f"{TRONSCAN_BASE}/block/latest", headers=_base_headers())
    if d1 is not None and isinstance(d1, dict):
        n = d1.get("number") or d1.get("blockNumber")
        if n is not None:
            try:
                return int(n), None
            except Exception:
                pass
    # Fallback: TronGrid wallet endpoint (GET works in most gateways)
    d2, e2 = await _get_json(client, f"{TRONGRID_BASE}/wallet/getnowblock", headers=_trongrid_headers())
    if d2 is not None and isinstance(d2, dict):
        hdr = ((d2.get("block_header") or {}).get("raw_data") or {})
        n2 = hdr.get("number")
        if n2 is not None:
            try:
                return int(n2), None
            except Exception:
                pass
    return None, e1 or e2 or {"error": "tron_latest_block_unavailable"}


async def fetch_tron_trc20_transfers(
    client: httpx.AsyncClient, deposit: str, contract_address: str, *, limit: int = 50
) -> tuple[list[dict], dict | None]:
    url = (
        f"{TRONSCAN_BASE}/token_trc20/transfers"
        f"?limit={limit}&start=0&sort=-timestamp&relatedAddress={deposit}"
        f"&contract_address={contract_address}"
    )
    d1, e1 = await _get_json(client, url, headers=_base_headers())
    if d1 is not None and isinstance(d1, dict):
        rows = d1.get("token_transfers") or []
        return rows if isinstance(rows, list) else [], None

    # Fallback: TronGrid TRC20 transfer feed
    d2, e2 = await _get_json(
        client,
        f"{TRONGRID_BASE}/v1/accounts/{deposit}/transactions/trc20?limit={limit}&only_to=true&contract_address={contract_address}",
        headers=_trongrid_headers(),
    )
    if d2 is not None and isinstance(d2, dict):
        out: list[dict] = []
        for r in d2.get("data") or []:
            if not isinstance(r, dict):
                continue
            block_num = r.get("block_number") or r.get("block")
            try:
                block_num = int(block_num) if block_num is not None else None
            except Exception:
                block_num = None
            out.append(
                {
                    "to_address": r.get("to"),
                    "from_address": r.get("from"),
                    "block_ts": int(r.get("block_timestamp") or 0),
                    "quant": str(r.get("value") or "0"),
                    "transaction_id": r.get("transaction_id") or "",
                    "block": block_num,
                    "confirmed": True,
                    "source": "trongrid",
                }
            )
        return out, None
    return [], e1 or e2 or {"error": "tron_trc20_transfers_unavailable"}


async def fetch_tron_trx_incoming(
    client: httpx.AsyncClient, deposit: str, *, limit: int = 40
) -> tuple[list[dict], dict | None]:
    paths = (
        f"{TRONSCAN_BASE}/transfer/trx?limit={limit}&start=0&sort=-timestamp&relatedAddress={deposit}",
        f"{TRONSCAN_BASE}/trx/transfers?limit={limit}&start=0&sort=-timestamp&relatedAddress={deposit}",
    )
    for p in paths:
        d, _e = await _get_json(client, p, headers=_base_headers())
        if d is None:
            continue
        raw = []
        if isinstance(d, dict):
            raw = d.get("data") or d.get("transfers") or d.get("txs") or []
        elif isinstance(d, list):
            raw = d
        if isinstance(raw, list):
            return [x for x in raw if isinstance(x, dict)], None

    # Fallback (best-effort): TronGrid native tx list
    d2, e2 = await _get_json(
        client,
        f"{TRONGRID_BASE}/v1/accounts/{deposit}/transactions?limit={limit}&only_to=true",
        headers=_trongrid_headers(),
    )
    if d2 is not None and isinstance(d2, dict):
        out: list[dict] = []
        for r in d2.get("data") or []:
            if not isinstance(r, dict):
                continue
            out.append(
                {
                    "toAddress": ((r.get("raw_data") or {}).get("contract") or [{}])[0]
                    .get("parameter", {})
                    .get("value", {})
                    .get("to_address", ""),
                    "timestamp": int(r.get("block_timestamp") or 0),
                    "amount": 0,
                    "source": "trongrid",
                }
            )
        return out, None
    return [], e2 or {"error": "tron_trx_incoming_unavailable"}
