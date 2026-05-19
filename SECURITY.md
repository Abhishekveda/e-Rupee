# Security Policy

## Scope

This repository is a **Proof of Concept** built for the RBIH Bank-Fintech Showcase 2026.
It is not deployed on mainnet and does not hold real funds.

## Supported Versions

| Version | Status          |
|---------|-----------------|
| 0.1.x   | PoC / testnet only |

## Reporting a Vulnerability

If you discover a security issue, **do not open a public GitHub issue.**

Please email: **security@[your-domain].in** with:

1. Description of the vulnerability
2. Steps to reproduce
3. Potential impact
4. Suggested fix (optional)

You will receive an acknowledgement within 48 hours.

## Known PoC Limitations (not bugs)

The following are intentional simplifications for the PoC that **must be hardened before production**:

| Component | PoC shortcut | Production requirement |
|-----------|-------------|----------------------|
| Relayer auth | Single EOA address | HSM-backed multi-sig (Gnosis Safe) |
| FX rate | Hardcoded constants | Chainlink price feeds with TWAP |
| KYC/AML | Not implemented | Integration with CERSAI / VKYC provider |
| Wallet ledger | In-memory dict | PostgreSQL with row-level encryption |
| CBDC API | Mock FastAPI | Live RBI e-Rupee developer sandbox |
| Bridge token | MockStablecoin ERC-20 | Regulated digital dirham / SGD (MAS/CBUAE) |
| LRS enforcement | Not implemented | Hard cap per RBI Master Direction |

## Security Checklist (pre-production)

- [ ] Smart contract audit by a SEBI/RBI-recognised firm
- [ ] Penetration test on FastAPI backend
- [ ] HSM key management for relayer private key
- [ ] Rate limiting and DDoS protection on API
- [ ] End-to-end encryption for wallet IDs in transit
- [ ] Data localisation: all INR transaction data must reside in India (IT Act, 2000)
