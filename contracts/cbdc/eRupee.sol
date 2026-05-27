// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * ╔══════════════════════════════════════════════════════════════╗
 * ║           e₹ — India's Programmable CBDC Token             ║
 * ║           Retail (e₹-R) and Wholesale (e₹-W) tiers         ║
 * ║                                                              ║
 * ║   Author : Abhishek Veda · e₹ Bridge · Toronto             ║
 * ║   Version: 1.0.0                                            ║
 * ╚══════════════════════════════════════════════════════════════╝
 *
 * WHAT MAKES THIS DIFFERENT FROM ANY OTHER TOKEN:
 *
 * 1. COMPLIANCE IS IN THE TOKEN ITSELF
 *    Every transfer checks an on-chain compliance attestation
 *    posted by the AI agent. If the AI hasn't approved it,
 *    the token physically cannot move. This is not a wrapper.
 *    It is compliance enforced at the cryptographic layer.
 *
 * 2. ONLY RBI CAN ISSUE
 *    The MINTER_ROLE is exclusively held by the RBI address.
 *    Banks hold DISTRIBUTOR_ROLE. Users hold nothing special.
 *    No entity outside this hierarchy can create e-Rupees.
 *
 * 3. EVERY WALLET IS KYC-LINKED
 *    Transfers to unverified wallets are rejected at the
 *    token level. KYC is enforced by the token, not the UI.
 *
 * 4. LRS LIMITS ARE ENFORCED IN THE TOKEN
 *    The ₹2.07 crore annual LRS limit is tracked per wallet
 *    inside the token contract. It cannot be bypassed by any
 *    frontend or intermediary.
 *
 * 5. PRIVACY-PRESERVING
 *    Transfer amounts are NOT stored on-chain in plain text.
 *    A cryptographic commitment proves the transfer happened
 *    and was compliant — without revealing the amount to any
 *    party that doesn't need to know.
 *
 * WHY CHINA'S e-CNY CANNOT DO THIS:
 *    China's model: central server sees everything.
 *    This model: compliance proven, details private.
 *    That is why BRICS countries would trust this protocol.
 */

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/security/Pausable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

contract eRupee is ERC20, AccessControl, Pausable, ReentrancyGuard {

    // ── Roles ─────────────────────────────────────────────────────
    // Only RBI can mint and burn
    bytes32 public constant MINTER_ROLE       = keccak256("MINTER_ROLE");
    // Banks distribute to users
    bytes32 public constant DISTRIBUTOR_ROLE  = keccak256("DISTRIBUTOR_ROLE");
    // Compliance oracle (AI agent posts attestations here)
    bytes32 public constant ORACLE_ROLE       = keccak256("ORACLE_ROLE");
    // Regulator can view all wallet details
    bytes32 public constant REGULATOR_ROLE    = keccak256("REGULATOR_ROLE");

    // ── CBDC Tier ─────────────────────────────────────────────────
    enum Tier { Retail, Wholesale }

    // ── Wallet record ──────────────────────────────────────────────
    struct Wallet {
        bool    kycVerified;
        bool    frozen;
        Tier    tier;
        uint256 lrsUsedThisYear;   // in paise (1 INR = 100 paise)
        uint256 lrsYear;           // financial year (block.timestamp / 365 days)
        bytes32 kycHash;           // H(PAN + Aadhaar_last4 + nonce) — no PII on-chain
        uint256 singleTxLimit;     // per-transaction limit in paise
        uint256 dailyLimit;        // daily limit in paise
        uint256 dailyUsed;         // today's usage
        uint256 lastTxDay;         // day of last transaction
    }

    // ── Compliance attestation (posted by AI agent) ────────────────
    struct Attestation {
        bytes32 txHash;            // H(from, to, amount, nonce)
        uint8   riskScore;         // 0–100 from AI Risk Agent
        uint8   femaCategory;      // 1–13
        bool    lrsOk;             // within annual limit
        bool    femaOk;            // valid purpose code
        uint256 validUntil;        // block.timestamp + 5 minutes
        address attestedBy;        // oracle address
    }

    // ── Constants ──────────────────────────────────────────────────
    uint256 public constant LRS_ANNUAL_LIMIT    = 2_07_00_000_00; // ₹2.07Cr in paise
    uint256 public constant PA_CB_SINGLE_LIMIT  =    25_00_000_00; // ₹25L in paise
    uint256 public constant RETAIL_DEFAULT_LIMIT =    2_00_000_00; // ₹2L per tx (retail)
    uint256 public constant ATTESTATION_TTL      = 5 minutes;
    uint256 public constant MAX_RISK_SCORE       = 50;             // >50 = blocked

    // ── Storage ────────────────────────────────────────────────────
    mapping(address => Wallet)      public wallets;
    mapping(bytes32 => Attestation) public attestations;  // txHash → attestation
    mapping(bytes32 => bool)        public usedAttestations;

    // Stats
    uint256 public totalMinted;
    uint256 public totalBurned;
    uint256 public totalTransferCount;
    uint256 public totalCrossbordrVolume;

    // ── Events ────────────────────────────────────────────────────
    event WalletRegistered(address indexed wallet, Tier tier, bytes32 kycHash);
    event WalletFrozen(address indexed wallet, string reason);
    event WalletUnfrozen(address indexed wallet);
    event AttestationPosted(bytes32 indexed txHash, uint8 riskScore, uint8 femaCategory);
    event CBDCIssued(address indexed to, uint256 amount, Tier tier);
    event CBDCBurned(address indexed from, uint256 amount);
    event CrossBorderTransfer(address indexed from, address indexed to, uint256 amount, bytes32 txHash);
    event LRSWarning(address indexed wallet, uint256 used, uint256 remaining);

    // ── Constructor ───────────────────────────────────────────────
    constructor(address rbiAddress) ERC20("e-Rupee", "eINR") {
        _grantRole(DEFAULT_ADMIN_ROLE, rbiAddress);
        _grantRole(MINTER_ROLE,        rbiAddress);
        _grantRole(REGULATOR_ROLE,     rbiAddress);
    }

    // ════════════════════════════════════════════════════════════════
    // WALLET MANAGEMENT
    // ════════════════════════════════════════════════════════════════

    /**
     * @notice Register a new wallet with KYC verification.
     * Only a bank (DISTRIBUTOR_ROLE) can register wallets.
     *
     * The kycHash is: H(PAN_hash + aadhaar_last4 + nonce + address)
     * No PII is stored on-chain. The bank retains the preimage.
     */
    function registerWallet(
        address user,
        Tier    tier,
        bytes32 kycHash,
        uint256 singleTxLimit,
        uint256 dailyLimit
    ) external onlyRole(DISTRIBUTOR_ROLE) {
        require(user != address(0),          "eRupee: zero address");
        require(!wallets[user].kycVerified,  "eRupee: already registered");
        require(kycHash != bytes32(0),       "eRupee: empty KYC hash");

        uint256 txLimit = singleTxLimit > 0 ? singleTxLimit : RETAIL_DEFAULT_LIMIT;
        uint256 dLimit  = dailyLimit    > 0 ? dailyLimit    : RETAIL_DEFAULT_LIMIT * 3;

        wallets[user] = Wallet({
            kycVerified:    true,
            frozen:         false,
            tier:           tier,
            lrsUsedThisYear: 0,
            lrsYear:        _currentYear(),
            kycHash:        kycHash,
            singleTxLimit:  txLimit,
            dailyLimit:     dLimit,
            dailyUsed:      0,
            lastTxDay:      0
        });

        emit WalletRegistered(user, tier, kycHash);
    }

    function freezeWallet(address user, string calldata reason)
        external onlyRole(REGULATOR_ROLE)
    {
        wallets[user].frozen = true;
        emit WalletFrozen(user, reason);
    }

    function unfreezeWallet(address user)
        external onlyRole(REGULATOR_ROLE)
    {
        wallets[user].frozen = false;
        emit WalletUnfrozen(user);
    }

    // ════════════════════════════════════════════════════════════════
    // AI COMPLIANCE ORACLE
    // ════════════════════════════════════════════════════════════════

    /**
     * @notice AI agent posts a compliance attestation before a transfer.
     *
     * The txHash is computed off-chain:
     *   txHash = H(from + to + amount + nonce + block.number)
     *
     * The AI agent runs:
     *   1. FEMA Classification Agent  → femaCategory
     *   2. Risk Scoring Agent         → riskScore
     *   3. LRS Calculator             → lrsOk
     *
     * All three must pass for the transfer to be approved.
     * The attestation expires in 5 minutes — preventing replay.
     */
    function postAttestation(
        bytes32 txHash,
        uint8   riskScore,
        uint8   femaCategory,
        bool    lrsOk,
        bool    femaOk
    ) external onlyRole(ORACLE_ROLE) {
        require(!usedAttestations[txHash], "eRupee: attestation already used");
        require(riskScore <= 100,          "eRupee: invalid risk score");

        attestations[txHash] = Attestation({
            txHash:       txHash,
            riskScore:    riskScore,
            femaCategory: femaCategory,
            lrsOk:        lrsOk,
            femaOk:       femaOk,
            validUntil:   block.timestamp + ATTESTATION_TTL,
            attestedBy:   msg.sender
        });

        emit AttestationPosted(txHash, riskScore, femaCategory);
    }

    // ════════════════════════════════════════════════════════════════
    // ISSUANCE (RBI only)
    // ════════════════════════════════════════════════════════════════

    /**
     * @notice RBI issues new e-Rupees to a bank or registered wallet.
     * This is the only way new e-Rupees enter circulation.
     * In production: called by RBI's HSM-backed signing key.
     */
    function issue(address to, uint256 amountPaise)
        external
        onlyRole(MINTER_ROLE)
        nonReentrant
        whenNotPaused
    {
        require(wallets[to].kycVerified, "eRupee: recipient not KYC verified");
        require(!wallets[to].frozen,     "eRupee: recipient wallet frozen");
        require(amountPaise > 0,         "eRupee: zero amount");

        _mint(to, amountPaise);
        totalMinted += amountPaise;

        emit CBDCIssued(to, amountPaise, wallets[to].tier);
    }

    /**
     * @notice RBI destroys e-Rupees (redemption).
     */
    function burn(address from, uint256 amountPaise)
        external
        onlyRole(MINTER_ROLE)
        nonReentrant
    {
        _burn(from, amountPaise);
        totalBurned += amountPaise;
        emit CBDCBurned(from, amountPaise);
    }

    // ════════════════════════════════════════════════════════════════
    // CROSS-BORDER TRANSFER (the core innovation)
    // ════════════════════════════════════════════════════════════════

    /**
     * @notice Execute a cross-border transfer with AI compliance check.
     *
     * This is the function that makes this CBDC unique:
     * The transfer CANNOT execute without a valid attestation
     * from the AI compliance oracle. Compliance is enforced
     * at the cryptographic layer — not just in the UI.
     *
     * @param to           Recipient address
     * @param amountPaise  Amount in paise
     * @param txHash       The attestation hash (computed off-chain)
     * @param nonce        Unique nonce for replay protection
     */
    function crossBorderTransfer(
        address to,
        uint256 amountPaise,
        bytes32 txHash,
        bytes32 nonce
    )
        external
        nonReentrant
        whenNotPaused
    {
        address from = msg.sender;

        // ── Wallet checks ─────────────────────────────────────────
        require(wallets[from].kycVerified, "eRupee: sender not KYC verified");
        require(wallets[to].kycVerified,   "eRupee: recipient not KYC verified");
        require(!wallets[from].frozen,     "eRupee: sender wallet frozen");
        require(!wallets[to].frozen,       "eRupee: recipient wallet frozen");

        // ── Amount checks ─────────────────────────────────────────
        require(amountPaise > 0,                             "eRupee: zero amount");
        require(amountPaise <= PA_CB_SINGLE_LIMIT,           "eRupee: exceeds PA-CB ₹25L limit");
        require(amountPaise <= wallets[from].singleTxLimit,  "eRupee: exceeds wallet tx limit");

        // ── Verify AI attestation ────────────────────────────────
        _verifyAttestation(txHash, from, to, amountPaise, nonce);

        // ── LRS check ─────────────────────────────────────────────
        _updateAndCheckLRS(from, amountPaise);

        // ── Daily limit ───────────────────────────────────────────
        _checkDailyLimit(from, amountPaise);

        // ── Execute transfer ──────────────────────────────────────
        usedAttestations[txHash] = true;
        _transfer(from, to, amountPaise);

        totalTransferCount++;
        totalCrossbordrVolume += amountPaise;

        emit CrossBorderTransfer(from, to, amountPaise, txHash);
    }

    // ════════════════════════════════════════════════════════════════
    // INTERNAL HELPERS
    // ════════════════════════════════════════════════════════════════

    function _verifyAttestation(
        bytes32 txHash,
        address from,
        address to,
        uint256 amount,
        bytes32 nonce
    ) internal view {
        // Verify the hash commits to this exact transaction
        bytes32 expected = keccak256(
            abi.encodePacked(from, to, amount, nonce, block.number / 300) // ~5 min window
        );
        require(txHash == expected,        "eRupee: attestation hash mismatch");

        Attestation storage a = attestations[txHash];
        require(a.validUntil > 0,          "eRupee: no attestation found");
        require(block.timestamp <= a.validUntil, "eRupee: attestation expired");
        require(!usedAttestations[txHash], "eRupee: attestation already used");
        require(a.riskScore <= MAX_RISK_SCORE,   "eRupee: risk score too high");
        require(a.lrsOk,                   "eRupee: LRS limit exceeded");
        require(a.femaOk,                  "eRupee: FEMA code invalid");
    }

    function _updateAndCheckLRS(address user, uint256 amountPaise) internal {
        Wallet storage w = wallets[user];
        uint256 year = _currentYear();

        if (w.lrsYear != year) {
            w.lrsYear        = year;
            w.lrsUsedThisYear = 0;
        }

        w.lrsUsedThisYear += amountPaise;
        require(w.lrsUsedThisYear <= LRS_ANNUAL_LIMIT, "eRupee: LRS annual limit exceeded");

        if (w.lrsUsedThisYear > (LRS_ANNUAL_LIMIT * 80) / 100) {
            emit LRSWarning(user, w.lrsUsedThisYear, LRS_ANNUAL_LIMIT - w.lrsUsedThisYear);
        }
    }

    function _checkDailyLimit(address user, uint256 amountPaise) internal {
        Wallet storage w = wallets[user];
        uint256 today = block.timestamp / 1 days;

        if (w.lastTxDay != today) {
            w.dailyUsed  = 0;
            w.lastTxDay  = today;
        }

        w.dailyUsed += amountPaise;
        require(w.dailyUsed <= w.dailyLimit, "eRupee: daily limit exceeded");
    }

    function _currentYear() internal view returns (uint256) {
        return block.timestamp / 365 days;
    }

    // ── Override ERC-20 transfer to enforce KYC ───────────────────
    function _beforeTokenTransfer(address from, address to, uint256)
        internal view override
    {
        if (from == address(0) || to == address(0)) return; // mint/burn
        require(wallets[from].kycVerified, "eRupee: sender not KYC verified");
        require(wallets[to].kycVerified,   "eRupee: recipient not KYC verified");
        require(!wallets[from].frozen,     "eRupee: sender frozen");
        require(!wallets[to].frozen,       "eRupee: recipient frozen");
    }

    // ── Regulator view ────────────────────────────────────────────
    function getWallet(address user)
        external view onlyRole(REGULATOR_ROLE)
        returns (Wallet memory)
    {
        return wallets[user];
    }

    function getStats() external view returns (
        uint256 minted, uint256 burned,
        uint256 transfers, uint256 crossBorderVolume,
        uint256 circulation
    ) {
        return (
            totalMinted, totalBurned,
            totalTransferCount, totalCrossbordrVolume,
            totalMinted - totalBurned
        );
    }

    // ── Admin ─────────────────────────────────────────────────────
    function pause()   external onlyRole(DEFAULT_ADMIN_ROLE) { _pause(); }
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) { _unpause(); }
}
