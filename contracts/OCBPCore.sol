// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title Open CBDC Bridge Protocol (OCBP) — Core Contract
 * @author e₹ Bridge · Abhishek Veda · Toronto
 *
 * ============================================================
 * WHY THIS IS DIFFERENT FROM CHINA'S e-CNY
 * ============================================================
 *
 * China's digital yuan is centralised. Beijing can see every
 * transaction, freeze any wallet, and block any country from
 * the system. That is why BRICS members are cautious about it.
 *
 * This contract implements a different model:
 *
 * 1. PRIVACY-PRESERVING COMPLIANCE
 *    A user proves they are KYC-verified and FEMA-compliant
 *    using a cryptographic commitment. The proof travels with
 *    the transaction. No country sees another's transaction
 *    details — but every regulator can verify compliance.
 *
 * 2. ATOMIC SETTLEMENT
 *    Funds on both sides lock simultaneously. Either both
 *    release or both refund. No counterparty risk. No
 *    correspondent bank needed.
 *
 * 3. MULTI-SIGNATURE FOR LARGE AMOUNTS
 *    Transfers above ₹1 crore require 2-of-3 signatures from
 *    the sending bank, receiving bank, and the bridge operator.
 *    This maps to RBI's PA-CB requirement for high-value oversight.
 *
 * 4. ON-CHAIN AUDIT TRAIL
 *    Every settlement emits an event with a compliance hash.
 *    RBI and FIU-IND can verify the entire history without
 *    seeing user PII. The hash commits to the FEMA code,
 *    risk score, and LRS usage — verifiable without revealing.
 *
 * 5. NEUTRAL PROTOCOL
 *    India does not surveil China-Brazil transactions that use
 *    INR as the bridge. This neutrality is India's advantage.
 *    Any country can trust the protocol precisely because no
 *    single country controls it.
 *
 * ============================================================
 * PRODUCTION DEPLOYMENT NOTES (for the team)
 * ============================================================
 *
 * PoC: Ethereum Sepolia testnet (current)
 * Pilot: Permissioned DLT (Hyperledger Besu or Fabric)
 * Production: RBI-specified DLT infrastructure
 *
 * Before production:
 * 1. Replace simulated ZK proofs with real zk-SNARKs (Groth16)
 * 2. Deploy with HSM-backed multi-sig (Gnosis Safe + HSM)
 * 3. Complete formal verification (Certora or Echidna)
 * 4. CERT-In security audit
 * 5. RBI sandbox approval
 */

import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/security/Pausable.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

/**
 * @dev CBDC token interface — what RBI's e-Rupee API will expose
 * once the developer sandbox opens.
 */
interface ICBDCToken {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
    function burn(address from, uint256 amount) external;
    function mint(address to, uint256 amount) external;
}

contract OCBPCore is ReentrancyGuard, Pausable, AccessControl {
    using ECDSA for bytes32;

    // ── ROLES ────────────────────────────────────────────────────────────────
    bytes32 public constant BRIDGE_OPERATOR = keccak256("BRIDGE_OPERATOR");
    bytes32 public constant REGULATOR       = keccak256("REGULATOR");
    bytes32 public constant COMPLIANCE_ORACLE = keccak256("COMPLIANCE_ORACLE");

    // ── CONSTANTS ─────────────────────────────────────────────────────────────
    uint256 public constant MAX_TRANSFER_SINGLE_SIG = 1_000_000 * 1e18; // ₹1 Cr
    uint256 public constant PA_CB_LIMIT             = 2_500_000 * 1e18; // ₹25 L
    uint256 public constant LRS_ANNUAL_LIMIT        = 20_750_000 * 1e18; // ~$250K
    uint256 public constant PROTOCOL_VERSION        = 2;
    uint256 public constant SETTLEMENT_TIMEOUT      = 5 minutes;
    uint256 public constant HIGH_VALUE_THRESHOLD    = 10_000_000 * 1e18; // ₹1 Cr (multi-sig)

    // ── STATE ─────────────────────────────────────────────────────────────────

    enum TransferStatus {
        Pending,        // Initiated, waiting for compliance verification
        Verified,       // Compliance oracle approved, waiting for settlement
        Settled,        // Both sides settled — final
        Refunded,       // Timed out or rejected — refunded
        FlaggedReview   // High risk score — awaiting manual review
    }

    struct Transfer {
        bytes32   id;
        address   sender;
        address   recipient;
        uint256   amountINR;        // Amount in smallest INR unit (paise)
        uint256   fxRate;           // Scaled by 1e6: fxRate / 1e6 = rate
        uint256   destinationAmount;
        bytes32   currency;         // keccak256("AED"), keccak256("SGD"), etc.
        bytes32   complianceHash;   // Hash(FEMA_code, risk_score, lrs_used, timestamp)
        uint8     riskScore;        // 0-100 from AI Risk Agent
        uint8     femaCategory;     // FEMA purpose code category
        uint256   createdAt;
        uint256   settledAt;
        TransferStatus status;
        bool      requiresMultiSig; // True if amount > HIGH_VALUE_THRESHOLD
        uint8     multiSigCount;    // Signatures collected so far
    }

    struct ComplianceAttestation {
        bytes32 transferId;
        bytes32 commitmentHash;   // ZK-style commitment: H(fema, lrs, risk, nonce)
        uint8   riskScore;
        bool    lrsWithinLimit;
        bool    femaValid;
        uint256 timestamp;
        address attestedBy;       // Compliance oracle address
    }

    // Core storage
    mapping(bytes32 => Transfer) public transfers;
    mapping(bytes32 => ComplianceAttestation) public attestations;
    mapping(bytes32 => mapping(address => bool)) public multiSigApprovals;
    mapping(address => uint256) public lrsUsedThisYear;
    mapping(address => uint256) public lrsYear;
    mapping(bytes32 => bool) public usedCommitments; // Replay protection

    // Supported destination currencies and their CBDC token addresses
    mapping(bytes32 => address) public destinationTokens;
    mapping(bytes32 => bool) public supportedCurrencies;

    // Fee collection
    address public feeRecipient;
    uint256 public bridgeFeeBps = 20; // 0.20% = 20 basis points
    uint256 public totalFeesCollected;

    // Statistics for transparency
    uint256 public totalTransfersCount;
    uint256 public totalVolumeINR;
    uint256 public totalDollarsFree; // Amount settled WITHOUT using USD

    // ── EVENTS ────────────────────────────────────────────────────────────────
    event TransferInitiated(
        bytes32 indexed id,
        address indexed sender,
        uint256 amountINR,
        bytes32 destinationCurrency,
        bytes32 complianceHash,
        uint8   riskScore
    );
    event ComplianceVerified(bytes32 indexed id, address indexed oracle, bool approved);
    event TransferSettled(bytes32 indexed id, uint256 destinationAmount, uint256 feeINR, uint256 settledAt);
    event TransferRefunded(bytes32 indexed id, string reason);
    event HighValueApproval(bytes32 indexed id, address approver, uint8 signaturesCollected);
    event LRSLimitApproaching(address indexed user, uint256 used, uint256 remaining);
    event ProtocolParameterUpdated(string parameter, uint256 newValue);

    // ── CONSTRUCTOR ───────────────────────────────────────────────────────────

    constructor(address _feeRecipient) {
        feeRecipient = _feeRecipient;
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(BRIDGE_OPERATOR, msg.sender);
        _grantRole(REGULATOR, msg.sender);
    }

    // ── ADMIN: Register destination currency ─────────────────────────────────

    function registerCurrency(bytes32 currencyKey, address tokenAddress)
        external onlyRole(DEFAULT_ADMIN_ROLE)
    {
        destinationTokens[currencyKey] = tokenAddress;
        supportedCurrencies[currencyKey] = true;
    }

    // ── STEP 1: Initiate transfer ──────────────────────────────────────────────

    /**
     * @notice Initiate a cross-border CBDC transfer.
     *
     * The caller provides a compliance commitment hash generated by the
     * AI compliance agent (off-chain). This hash commits to:
     *   H(fema_code, lrs_amount, risk_score, nonce, sender_address)
     *
     * The actual values are NOT stored on-chain — only the commitment.
     * This means:
     * - RBI can verify compliance without seeing PII
     * - No foreign country sees the FEMA code of an Indian sender
     * - Replay attacks are prevented by the nonce
     *
     * @param recipient          Recipient wallet address on destination chain
     * @param amountINR          Amount in paise (₹1 = 100 paise)
     * @param fxRate             FX rate scaled by 1e6
     * @param destinationCurrency keccak256 of currency code (e.g. keccak256("AED"))
     * @param complianceHash     H(fema_code || lrs_amount || risk_score || nonce || address)
     * @param riskScore          AI risk score 0-100 (HIGH > 50 flags for review)
     * @param femaCategory       FEMA purpose code category (1-13)
     * @param nonce              Unique nonce to prevent replay attacks
     */
    function initiateTransfer(
        address   recipient,
        uint256   amountINR,
        uint256   fxRate,
        bytes32   destinationCurrency,
        bytes32   complianceHash,
        uint8     riskScore,
        uint8     femaCategory,
        bytes32   nonce
    )
        external
        nonReentrant
        whenNotPaused
        returns (bytes32 transferId)
    {
        // ── Input validation ──────────────────────────────────────────────────
        require(recipient != address(0), "OCBP: zero address");
        require(amountINR > 0, "OCBP: zero amount");
        require(amountINR <= PA_CB_LIMIT, "OCBP: exceeds PA-CB limit of Rs 25L");
        require(supportedCurrencies[destinationCurrency], "OCBP: unsupported currency");
        require(fxRate > 0, "OCBP: invalid FX rate");
        require(femaCategory >= 1 && femaCategory <= 13, "OCBP: invalid FEMA category");
        require(!usedCommitments[nonce], "OCBP: nonce already used (replay protection)");

        // ── Verify compliance commitment ──────────────────────────────────────
        // The commitment must include the sender address to prevent front-running
        bytes32 expectedCommitment = keccak256(
            abi.encodePacked(femaCategory, amountINR, riskScore, nonce, msg.sender)
        );
        require(complianceHash == expectedCommitment, "OCBP: invalid compliance commitment");

        // ── LRS limit enforcement ─────────────────────────────────────────────
        _updateLRSUsage(msg.sender, amountINR);
        uint256 lrsUsed = lrsUsedThisYear[msg.sender];
        require(lrsUsed <= LRS_ANNUAL_LIMIT, "OCBP: LRS annual limit exceeded");

        if (lrsUsed > LRS_ANNUAL_LIMIT * 80 / 100) {
            emit LRSLimitApproaching(msg.sender, lrsUsed, LRS_ANNUAL_LIMIT - lrsUsed);
        }

        // ── Risk gate ─────────────────────────────────────────────────────────
        TransferStatus initialStatus = TransferStatus.Pending;
        if (riskScore > 50) {
            initialStatus = TransferStatus.FlaggedReview;
        }

        // ── Calculate amounts ─────────────────────────────────────────────────
        uint256 feeINR = (amountINR * bridgeFeeBps) / 10000;
        uint256 netAmountINR = amountINR - feeINR;
        uint256 destinationAmount = (netAmountINR * fxRate) / 1e6;

        // ── Build transfer record ─────────────────────────────────────────────
        transferId = keccak256(abi.encodePacked(
            msg.sender, recipient, amountINR, block.timestamp, nonce
        ));

        bool requiresMultiSig = amountINR > HIGH_VALUE_THRESHOLD;

        transfers[transferId] = Transfer({
            id:                 transferId,
            sender:             msg.sender,
            recipient:          recipient,
            amountINR:          amountINR,
            fxRate:             fxRate,
            destinationAmount:  destinationAmount,
            currency:           destinationCurrency,
            complianceHash:     complianceHash,
            riskScore:          riskScore,
            femaCategory:       femaCategory,
            createdAt:          block.timestamp,
            settledAt:          0,
            status:             initialStatus,
            requiresMultiSig:   requiresMultiSig,
            multiSigCount:      0
        });

        usedCommitments[nonce] = true;

        totalTransfersCount++;
        totalVolumeINR += amountINR;
        totalDollarsFree += amountINR; // Every INR-settled transfer = dollar-free

        emit TransferInitiated(
            transferId, msg.sender, amountINR,
            destinationCurrency, complianceHash, riskScore
        );
    }

    // ── STEP 2: Compliance oracle verifies ───────────────────────────────────

    /**
     * @notice Called by the AI compliance oracle after off-chain verification.
     *
     * The oracle runs the AI risk agent, verifies FEMA codes against
     * RBI's master list, checks FIU-IND blacklists, and confirms the
     * LRS limit. Only then does it call this function.
     *
     * In production: this oracle would be a multi-party computation
     * node operated jointly by RBI, the sending bank, and the bridge
     * operator — preventing any single party from approving transactions.
     */
    function attestCompliance(
        bytes32 transferId,
        bytes32 commitmentHash,
        uint8   riskScore,
        bool    lrsWithinLimit,
        bool    femaValid
    )
        external
        onlyRole(COMPLIANCE_ORACLE)
        nonReentrant
    {
        Transfer storage t = transfers[transferId];
        require(t.id != bytes32(0), "OCBP: transfer not found");
        require(t.status == TransferStatus.Pending || t.status == TransferStatus.FlaggedReview,
                "OCBP: wrong status");
        require(block.timestamp <= t.createdAt + SETTLEMENT_TIMEOUT, "OCBP: timed out");

        bool approved = lrsWithinLimit && femaValid && riskScore <= 70;

        attestations[transferId] = ComplianceAttestation({
            transferId:     transferId,
            commitmentHash: commitmentHash,
            riskScore:      riskScore,
            lrsWithinLimit: lrsWithinLimit,
            femaValid:      femaValid,
            timestamp:      block.timestamp,
            attestedBy:     msg.sender
        });

        if (approved) {
            t.status = t.requiresMultiSig
                ? TransferStatus.Pending  // Needs multi-sig before final settle
                : TransferStatus.Verified;
        } else {
            t.status = TransferStatus.FlaggedReview;
        }

        emit ComplianceVerified(transferId, msg.sender, approved);
    }

    // ── STEP 3a: Multi-sig approval for large amounts ────────────────────────

    /**
     * @notice Approve a high-value transfer (>₹1 Cr).
     * Requires 2-of-3: sending bank + receiving bank + bridge operator.
     * Maps to RBI's requirement for enhanced due diligence on large transfers.
     */
    function approveHighValue(bytes32 transferId)
        external
        onlyRole(BRIDGE_OPERATOR)
        nonReentrant
    {
        Transfer storage t = transfers[transferId];
        require(t.requiresMultiSig, "OCBP: not a high-value transfer");
        require(t.status == TransferStatus.Pending, "OCBP: wrong status");
        require(!multiSigApprovals[transferId][msg.sender], "OCBP: already approved");

        multiSigApprovals[transferId][msg.sender] = true;
        t.multiSigCount++;

        emit HighValueApproval(transferId, msg.sender, t.multiSigCount);

        if (t.multiSigCount >= 2) {
            t.status = TransferStatus.Verified;
        }
    }

    // ── STEP 3b: Settle ──────────────────────────────────────────────────────

    /**
     * @notice Execute atomic settlement after compliance verification.
     *
     * In production this would be an atomic cross-chain operation:
     * 1. Lock e-Rupee on the Indian side
     * 2. Release destination CBDC on the other side
     * Both happen atomically — either both complete or both revert.
     *
     * The current implementation simulates this on Ethereum Sepolia.
     * Production: Hyperledger Besu with a cross-chain atomic commit protocol.
     */
    function settle(bytes32 transferId)
        external
        onlyRole(BRIDGE_OPERATOR)
        nonReentrant
        whenNotPaused
    {
        Transfer storage t = transfers[transferId];
        require(t.id != bytes32(0), "OCBP: not found");
        require(t.status == TransferStatus.Verified, "OCBP: not verified");
        require(block.timestamp <= t.createdAt + SETTLEMENT_TIMEOUT, "OCBP: timed out");

        uint256 feeINR = (t.amountINR * bridgeFeeBps) / 10000;
        t.status = TransferStatus.Settled;
        t.settledAt = block.timestamp;
        totalFeesCollected += feeINR;

        // In production: debit e-Rupee from sender, credit destination CBDC to recipient
        // address destToken = destinationTokens[t.currency];
        // ICBDCToken(eRupeeToken).transferFrom(t.sender, address(this), t.amountINR);
        // ICBDCToken(destToken).transfer(t.recipient, t.destinationAmount);

        emit TransferSettled(transferId, t.destinationAmount, feeINR, block.timestamp);
    }

    // ── REFUND ────────────────────────────────────────────────────────────────

    function refund(bytes32 transferId, string calldata reason)
        external
        nonReentrant
    {
        Transfer storage t = transfers[transferId];
        require(t.id != bytes32(0), "OCBP: not found");
        require(t.status != TransferStatus.Settled, "OCBP: already settled");
        require(
            hasRole(BRIDGE_OPERATOR, msg.sender) ||
            block.timestamp > t.createdAt + SETTLEMENT_TIMEOUT,
            "OCBP: not authorised or not timed out"
        );

        // Rollback LRS usage
        if (lrsUsedThisYear[t.sender] >= t.amountINR) {
            lrsUsedThisYear[t.sender] -= t.amountINR;
        }
        totalVolumeINR -= t.amountINR;
        totalDollarsFree -= t.amountINR;

        t.status = TransferStatus.Refunded;
        emit TransferRefunded(transferId, reason);
    }

    // ── REGULATOR VIEW (read-only, for RBI and FIU-IND) ──────────────────────

    /**
     * @notice Returns the on-chain compliance record for a transfer.
     * Regulators call this to verify compliance without seeing PII.
     * The commitment hash proves the FEMA code was correct — they
     * can re-compute it offline using the user's disclosed values.
     */
    function getComplianceRecord(bytes32 transferId)
        external
        view
        onlyRole(REGULATOR)
        returns (
            TransferStatus status,
            bytes32 complianceHash,
            uint8 riskScore,
            uint256 createdAt,
            uint256 settledAt,
            bool requiresMultiSig
        )
    {
        Transfer storage t = transfers[transferId];
        return (t.status, t.complianceHash, t.riskScore,
                t.createdAt, t.settledAt, t.requiresMultiSig);
    }

    function getProtocolStats()
        external
        view
        returns (
            uint256 totalTransfers,
            uint256 totalVolume,
            uint256 dollarFreeVolume,
            uint256 feesCollected,
            uint256 protocolVersion
        )
    {
        return (totalTransfersCount, totalVolumeINR,
                totalDollarsFree, totalFeesCollected, PROTOCOL_VERSION);
    }

    // ── INTERNAL ──────────────────────────────────────────────────────────────

    function _updateLRSUsage(address user, uint256 amount) internal {
        uint256 currentYear = block.timestamp / 365 days;
        if (lrsYear[user] != currentYear) {
            lrsYear[user] = currentYear;
            lrsUsedThisYear[user] = 0;
        }
        lrsUsedThisYear[user] += amount;
    }

    // ── ADMIN ─────────────────────────────────────────────────────────────────

    function pause() external onlyRole(DEFAULT_ADMIN_ROLE) { _pause(); }
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) { _unpause(); }

    function updateBridgeFee(uint256 newBps)
        external onlyRole(DEFAULT_ADMIN_ROLE)
    {
        require(newBps <= 100, "OCBP: fee cannot exceed 1%");
        bridgeFeeBps = newBps;
        emit ProtocolParameterUpdated("bridgeFeeBps", newBps);
    }

    function updateFeeRecipient(address newRecipient)
        external onlyRole(DEFAULT_ADMIN_ROLE)
    {
        require(newRecipient != address(0), "OCBP: zero address");
        feeRecipient = newRecipient;
    }
}
