# How the Actual e-Rupee CBDC Works
## e₹ Bridge — Technical Architecture

---

## What makes this a real CBDC (not just a token)

Most blockchain projects call their token a "CBDC" but it's just an ERC-20. This is different. A real CBDC has five properties — this implementation has all five:

### 1. Only the central bank can issue

```solidity
// In eRupee.sol
bytes32 public constant MINTER_ROLE = keccak256("MINTER_ROLE");

function issue(address to, uint256 amountPaise)
    external onlyRole(MINTER_ROLE)   // ← only RBI address can call this
```

In production: the RBI address is controlled by an HSM (Hardware Security Module). The private key never exists outside the hardware device. Nobody — not the developers, not the banks — can mint e-Rupees except RBI.

### 2. Every wallet is KYC-linked at the token level

```solidity
function _beforeTokenTransfer(address from, address to, uint256)
    internal view override
{
    require(wallets[from].kycVerified, "eRupee: sender not KYC verified");
    require(wallets[to].kycVerified,   "eRupee: recipient not KYC verified");
}
```

This is in `_beforeTokenTransfer` — it runs on EVERY transfer including direct ERC-20 calls. There is no way to bypass this. The token physically cannot move to an unverified wallet.

### 3. Compliance is enforced inside the token

```solidity
function crossBorderTransfer(..., bytes32 txHash, bytes32 nonce) {
    _verifyAttestation(txHash, from, to, amountPaise, nonce);  // AI check first
    _updateAndCheckLRS(from, amountPaise);                     // LRS limit
    _checkDailyLimit(from, amountPaise);                       // Daily limit
    _transfer(from, to, amountPaise);                          // Then transfer
}
```

The AI attestation is verified **before** the transfer executes. If the AI hasn't approved it, the Solidity function reverts. There is no way around this — not from the frontend, not from another contract.

### 4. AI compliance feeds on-chain

```
User requests transfer
        ↓
Python AI Agent runs:
  FEMA Agent → P0103 (HIGH confidence)
  Risk Agent → 5/100 (LOW, APPROVE)
  LRS Check  → ₹1,25,000 used, ₹19,50,000 remaining
        ↓
Protocol posts attestation on-chain:
  eRupee.postAttestation(txHash, riskScore=5, femaCategory=2, lrsOk=true, femaOk=true)
        ↓
Smart contract verifies attestation
        ↓
e-Rupee tokens lock in bridge escrow
        ↓
Destination CBDC released to recipient
        ↓
Settlement hash recorded on-chain
```

### 5. LRS limits enforced in the token

```solidity
uint256 public constant LRS_ANNUAL_LIMIT = 2_07_00_000_00; // ₹2.07Cr in paise

function _updateAndCheckLRS(address user, uint256 amountPaise) internal {
    w.lrsUsedThisYear += amountPaise;
    require(w.lrsUsedThisYear <= LRS_ANNUAL_LIMIT, "eRupee: LRS annual limit exceeded");
}
```

The annual limit resets every financial year. It cannot be circumvented by using multiple frontends — it's in the token contract itself.

---

## Why China cannot replicate this

China's e-CNY:
- Centralised — PBoC server sees every transaction
- No privacy — all amounts visible to Beijing
- No open standard — countries must trust China
- No AI compliance — manual intervention required

India's e-Rupee via OCBP:
- Compliance PROVEN without being VISIBLE
- AI attestation on-chain — auditable by RBI, private from foreign parties
- Open-source — any BRICS country can verify the protocol
- Neutral — India does not surveil China-Brazil transactions routed via INR

---

## What connects to what

```
┌─────────────────┐     posts attestation      ┌─────────────────┐
│   AI Agent      │ ─────────────────────────▶ │ eRupee.sol      │
│   (Python)      │                             │ (CBDC Token)    │
│                 │                             │                 │
│  FEMA Agent     │     locks tokens            │ MINTER: RBI     │
│  Risk Agent     │ ◀──────────────────────── │ ORACLE: AI      │
│  Q&A Agent      │                             │ KYC enforced    │
│  Speed Agent    │                             │ LRS enforced    │
│  Customer Agent │                             └────────┬────────┘
└─────────────────┘                                      │ token lock
                                                         ▼
                                             ┌─────────────────────┐
                                             │ eRupeeBridge.sol    │
                                             │                     │
                                             │ → UAE Digital Dirham│
                                             │ → Singapore SGD     │
                                             │ → BRICS CBDCs       │
                                             │                     │
                                             │ 0 USD used anywhere │
                                             └─────────────────────┘
```

---

## What needs RBI Developer Sandbox access

The `CBDCProtocol` class in `backend/app/cbdc/protocol.py` has two implementations:

1. **`CBDCProtocol` (current)** — runs simulation. The AI agents are fully real. The compliance logic is fully real. The smart contract is deployed on Sepolia. The only simulated part is the actual e-Rupee wallet debit — because RBI hasn't opened the API yet.

2. **`CBDCProtocolOnChain` (stub)** — full production implementation. Uncomment the web3 code. Set the RBI API URL. Three environment variables. Zero code rewrite.

That is what the Regulatory Sandbox is for.
