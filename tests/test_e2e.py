"""
Integration test — runs the full cross-border transfer flow locally.
Start the FastAPI server first: uvicorn app.main:app --reload
Then: pytest tests/test_e2e.py -v
"""

import pytest
import httpx
import asyncio
import time

BASE = "http://localhost:8000"


@pytest.fixture(scope="module")
def client():
    return httpx.Client(base_url=BASE, timeout=10)


def test_health(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "operational"


def test_get_existing_wallet(client):
    r = client.get("/v1/wallets/INDIA_USER_001")
    assert r.status_code == 200
    data = r.json()
    assert data["currency"] == "INR"
    assert data["balance"] > 0


def test_wallet_not_found(client):
    r = client.get("/v1/wallets/GHOST_WALLET")
    assert r.status_code == 404


def test_fx_quote_uae(client):
    r = client.post("/v1/fx/quote", json={"amount_inr": 10000, "target_currency": "AED"})
    assert r.status_code == 200
    data = r.json()
    assert data["from"] == "INR"
    assert data["to"] == "AED"
    assert data["converted_amount"] == pytest.approx(440, rel=0.01)
    assert "bridge_fee_inr" in data


def test_fx_quote_unsupported_currency(client):
    r = client.post("/v1/fx/quote", json={"amount_inr": 5000, "target_currency": "JPY"})
    assert r.status_code == 400


def test_full_transfer_flow(client):
    # Top up wallet to ensure sufficient balance
    client.post("/v1/wallets/topup", json={"wallet_id": "INDIA_USER_001", "amount": 50000})

    # Initiate transfer
    payload = {
        "sender_wallet": "INDIA_USER_001",
        "recipient_address": "0xABC123def456789",
        "recipient_country": "UAE",
        "amount_inr": 10000.0,
        "purpose_code": "P0102",
        "notes": "Family remittance",
    }
    r = client.post("/v1/erupee/transfer", json=payload)
    assert r.status_code == 200
    data = r.json()

    assert data["status"] == "pending_bridge"
    assert data["cbdc_tx_hash"].startswith("0xcbdc")
    assert data["bridge_tx_hash"].startswith("0xbridge")
    assert data["target_currency"] == "AED"
    assert data["converted_amount"] == pytest.approx(440, rel=0.01)

    tx_id = data["tx_id"]

    # Poll for settlement (background task takes ~3s)
    settled = False
    for _ in range(10):
        time.sleep(0.5)
        check = client.get(f"/v1/transactions/{tx_id}")
        if check.json()["status"] == "settled":
            settled = True
            break

    assert settled, "Transaction did not settle within 5 seconds"
    final = client.get(f"/v1/transactions/{tx_id}").json()
    assert "settled_at" in final
    assert "settlement_block" in final


def test_insufficient_balance(client):
    payload = {
        "sender_wallet": "INDIA_USER_001",
        "recipient_address": "0xSomeAddress",
        "recipient_country": "UAE",
        "amount_inr": 999_999_999.0,
        "purpose_code": "P0102",
    }
    r = client.post("/v1/erupee/transfer", json=payload)
    assert r.status_code == 400
    assert "Insufficient balance" in r.json()["detail"]


def test_list_transactions(client):
    r = client.get("/v1/transactions")
    assert r.status_code == 200
    data = r.json()
    assert "count" in data
    assert isinstance(data["transactions"], list)
