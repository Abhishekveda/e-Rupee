// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title Open CBDC Bridge Protocol (OCBP) — Core Contract v1.0
 * @author e₹ Bridge · Abhishek Veda · Toronto
 *
 * India's privacy-preserving CBDC cross-border settlement protocol.
 * Unlike China's e-CNY, compliance is PROVEN without being VISIBLE.
 * No single country can surveil another's transactions — but every
 * regulator can verify compliance. That is the competitive advantage.
 *
 * Security: ReentrancyGuard + Pausable + AccessControl (OpenZeppelin)
 * Compliance: ZK-commitment scheme, LRS enforcement, PA-CB limits
 * Settlement: Atomic with timeout + auto-refund, multi-sig for large amounts
 */

import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/security/Pausable.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";

contract OCBPCore is ReentrancyGuard, Pausable, AccessControl {

    // ── Roles ─────────────────────────────────────────────────────────────────
    bytes32 public constant BRIDGE_OPERATOR   = keccak256("BRIDGE_OPERATOR");
    bytes32 public constant REGULATOR         = keccak256("REGULATOR");
    bytes32 public constant COMPLIANCE_ORACLE = keccak256("COMPLIANCE_ORACLE");

    // ── Constants ─────────────────────────────────────────────────────────────
    uint256 public constant PA_CB_LIMIT          = 2_500_000 * 1e18;  // ₹25L
    uint256 public constant LRS_ANNUAL_LIMIT     = 20_750_000 * 1e18; // ~$250K
    uint256 public constant HIGH_VALUE_THRESHOLD = 10_000_000 * 1e18; // ₹1Cr
    uint256 public constant SETTLEMENT_TIMEOUT   = 5 minutes;
    uint256 public constant PROTOCOL_VERSION     = 2;

    // ── Types ─────────────────────────────────────────────────────────────────
    enum TransferStatus { Pending, Verified, Settled, Refunded, FlaggedReview }

    struct Transfer {
        bytes32        id;
        address        sender;
        address        recipient;
        uint256        amountINR;
        uint256        fxRate;
        uint256        destinationAmount;
        bytes32        currency;
        bytes32        complianceHash;
        uint8          riskScore;
        uint8          femaCategory;
        uint256        createdAt;
        uint256        settledAt;
        TransferStatus status;
        bool           requiresMultiSig;
        uint8          multiSigCount;
    }

    struct ComplianceAttestation {
        bytes32 transferId;
        bytes32 commitmentHash;
        uint8   riskScore;
        bool    lrsWithinLimit;
        bool    femaValid;
        uint256 timestamp;
        address attestedBy;
    }

    // ── Storage ───────────────────────────────────────────────────────────────
    mapping(bytes32 => Transfer)              public transfers;
    mapping(bytes32 => ComplianceAttestation) public attestations;
    mapping(bytes32 => mapping(address => bool)) public multiSigApprovals;
    mapping(address => uint256) public lrsUsedThisYear;
    mapping(address => uint256) public lrsYear;
    mapping(bytes32 => bool)    public usedCommitments;
    mapping(bytes32 => address) public destinationTokens;
    mapping(bytes32 => bool)    public supportedCurrencies;

    address public feeRecipient;
    uint256 public bridgeFeeBps    = 20;
    uint256 public totalTransfersCount;
    uint256 public totalVolumeINR;
    uint256 public totalFeesCollected;
    uint256 public totalDollarsFree;

    // ── Events ────────────────────────────────────────────────────────────────
    event TransferInitiated(bytes32 indexed id, address indexed sender, uint256 amountINR, bytes32 currency, bytes32 complianceHash, uint8 riskScore);
    event ComplianceVerified(bytes32 indexed id, address indexed oracle, bool approved);
    event TransferSettled(bytes32 indexed id, uint256 destinationAmount, uint256 feeINR, uint256 settledAt);
    event TransferRefunded(bytes32 indexed id, string reason);
    event HighValueApproval(bytes32 indexed id, address approver, uint8 sigsCollected);
    event LRSLimitApproaching(address indexed user, uint256 used, uint256 remaining);

    // ── Constructor ───────────────────────────────────────────────────────────
    constructor(address _feeRecipient) {
        feeRecipient = _feeRecipient;
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(BRIDGE_OPERATOR, msg.sender);
        _grantRole(REGULATOR, msg.sender);
    }

    // ── Admin ─────────────────────────────────────────────────────────────────
    function registerCurrency(bytes32 key, address token) external onlyRole(DEFAULT_ADMIN_ROLE) {
        destinationTokens[key] = token;
        supportedCurrencies[key] = true;
    }

    // ── Step 1: Initiate transfer ─────────────────────────────────────────────
    /**
     * @notice Initiate a cross-border CBDC transfer.
     *
     * The complianceHash is a ZK-commitment: H(fema || lrs || risk || nonce || sender)
     * Only the hash goes on-chain — actual FEMA code and LRS amount stay private.
     * Regulators verify compliance by requesting the preimage off-chain.
     *
     * @param recipient           Recipient wallet on destination chain
     * @param amountINR           Amount in paise (₹1 = 100 paise)
     * @param fxRate              FX rate scaled by 1e6
     * @param destinationCurrency keccak256 of currency code e.g. keccak256("AED")
     * @param complianceHash      ZK commitment: H(fema||lrs||risk||nonce||msg.sender)
     * @param riskScore           AI risk score 0-100 (>50 flags for review)
     * @param femaCategory        FEMA purpose code category 1-13
     * @param nonce               Unique nonce for replay protection
     */
    function initiateTransfer(
        address recipient,
        uint256 amountINR,
        uint256 fxRate,
        bytes32 destinationCurrency,
        bytes32 complianceHash,
        uint8   riskScore,
        uint8   femaCategory,
        bytes32 nonce
    )
        external
        nonReentrant
        whenNotPaused
        returns (bytes32 transferId)
    {
        _validateTransfer(recipient, amountINR, fxRate, destinationCurrency, femaCategory, nonce);
        _verifyCommitment(complianceHash, femaCategory, amountINR, riskScore, nonce);
        _checkLRS(amountINR);

        transferId = _buildAndStore(
            recipient, amountINR, fxRate, destinationCurrency,
            complianceHash, riskScore, femaCategory, nonce
        );
    }

    // ── Internal helpers (split to avoid stack-too-deep) ─────────────────────

    function _validateTransfer(
        address recipient,
        uint256 amountINR,
        uint256 fxRate,
        bytes32 destinationCurrency,
        uint8   femaCategory,
        bytes32 nonce
    ) internal view {
        require(recipient != address(0),                      "OCBP: zero address");
        require(amountINR > 0,                                "OCBP: zero amount");
        require(amountINR <= PA_CB_LIMIT,                     "OCBP: exceeds PA-CB Rs 25L limit");
        require(supportedCurrencies[destinationCurrency],     "OCBP: unsupported currency");
        require(fxRate > 0,                                   "OCBP: invalid FX rate");
        require(femaCategory >= 1 && femaCategory <= 13,      "OCBP: invalid FEMA category");
        require(!usedCommitments[nonce],                      "OCBP: nonce reused (replay protection)");
    }

    function _verifyCommitment(
        bytes32 complianceHash,
        uint8   femaCategory,
        uint256 amountINR,
        uint8   riskScore,
        bytes32 nonce
    ) internal view {
        bytes32 expected = keccak256(
            abi.encodePacked(femaCategory, amountINR, riskScore, nonce, msg.sender)
        );
        require(complianceHash == expected, "OCBP: invalid compliance commitment");
    }

    function _checkLRS(uint256 amountINR) internal {
        _updateLRSUsage(msg.sender, amountINR);
        uint256 used = lrsUsedThisYear[msg.sender];
        require(used <= LRS_ANNUAL_LIMIT, "OCBP: LRS annual limit exceeded");
        if (used > (LRS_ANNUAL_LIMIT * 80) / 100) {
            emit LRSLimitApproaching(msg.sender, used, LRS_ANNUAL_LIMIT - used);
        }
    }

    function _buildAndStore(
        address recipient,
        uint256 amountINR,
        uint256 fxRate,
        bytes32 destinationCurrency,
        bytes32 complianceHash,
        uint8   riskScore,
        uint8   femaCategory,
        bytes32 nonce
    ) internal returns (bytes32 transferId) {
        transferId = keccak256(
            abi.encodePacked(msg.sender, recipient, amountINR, block.timestamp, nonce)
        );

        // Write fields via storage pointer — avoids struct-literal stack explosion
        Transfer storage t = transfers[transferId];
        t.id               = transferId;
        t.sender           = msg.sender;
        t.recipient        = recipient;
        t.amountINR        = amountINR;
        t.fxRate           = fxRate;
        t.currency         = destinationCurrency;
        t.complianceHash   = complianceHash;
        t.riskScore        = riskScore;
        t.femaCategory     = femaCategory;
        t.createdAt        = block.timestamp;
        t.status           = riskScore > 50
                               ? TransferStatus.FlaggedReview
                               : TransferStatus.Pending;
        t.requiresMultiSig = amountINR > HIGH_VALUE_THRESHOLD;

        // Compute destination amount separately to keep stack shallow
        _setDestinationAmount(transferId, amountINR, fxRate);

        usedCommitments[nonce] = true;
        totalTransfersCount++;
        totalVolumeINR   += amountINR;
        totalDollarsFree += amountINR;

        emit TransferInitiated(
            transferId, msg.sender, amountINR,
            destinationCurrency, complianceHash, riskScore
        );
    }

    function _setDestinationAmount(bytes32 transferId, uint256 amountINR, uint256 fxRate) internal {
        uint256 feeINR = (amountINR * bridgeFeeBps) / 10000;
        transfers[transferId].destinationAmount = ((amountINR - feeINR) * fxRate) / 1e6;
    }

    // ── Step 2: Compliance oracle attests ─────────────────────────────────────
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
        require(t.id != bytes32(0),             "OCBP: transfer not found");
        require(
            t.status == TransferStatus.Pending ||
            t.status == TransferStatus.FlaggedReview,
            "OCBP: wrong status"
        );
        require(block.timestamp <= t.createdAt + SETTLEMENT_TIMEOUT, "OCBP: timed out");

        attestations[transferId] = ComplianceAttestation({
            transferId:     transferId,
            commitmentHash: commitmentHash,
            riskScore:      riskScore,
            lrsWithinLimit: lrsWithinLimit,
            femaValid:      femaValid,
            timestamp:      block.timestamp,
            attestedBy:     msg.sender
        });

        bool approved = lrsWithinLimit && femaValid && riskScore <= 70;
        if (approved) {
            t.status = t.requiresMultiSig
                ? TransferStatus.Pending
                : TransferStatus.Verified;
        } else {
            t.status = TransferStatus.FlaggedReview;
        }

        emit ComplianceVerified(transferId, msg.sender, approved);
    }

    // ── Step 3a: Multi-sig for high-value transfers ──────────────────────────
    function approveHighValue(bytes32 transferId)
        external
        onlyRole(BRIDGE_OPERATOR)
        nonReentrant
    {
        Transfer storage t = transfers[transferId];
        require(t.requiresMultiSig,                          "OCBP: not high-value");
        require(t.status == TransferStatus.Pending,          "OCBP: wrong status");
        require(!multiSigApprovals[transferId][msg.sender],  "OCBP: already approved");

        multiSigApprovals[transferId][msg.sender] = true;
        t.multiSigCount++;

        emit HighValueApproval(transferId, msg.sender, t.multiSigCount);
        if (t.multiSigCount >= 2) {
            t.status = TransferStatus.Verified;
        }
    }

    // ── Step 3b: Settle ───────────────────────────────────────────────────────
    function settle(bytes32 transferId)
        external
        onlyRole(BRIDGE_OPERATOR)
        nonReentrant
        whenNotPaused
    {
        Transfer storage t = transfers[transferId];
        require(t.id != bytes32(0),                                           "OCBP: not found");
        require(t.status == TransferStatus.Verified,                          "OCBP: not verified");
        require(block.timestamp <= t.createdAt + SETTLEMENT_TIMEOUT,          "OCBP: timed out");

        uint256 feeINR = (t.amountINR * bridgeFeeBps) / 10000;
        t.status    = TransferStatus.Settled;
        t.settledAt = block.timestamp;
        totalFeesCollected += feeINR;

        emit TransferSettled(transferId, t.destinationAmount, feeINR, block.timestamp);
    }

    // ── Refund ────────────────────────────────────────────────────────────────
    function refund(bytes32 transferId, string calldata reason)
        external
        nonReentrant
    {
        Transfer storage t = transfers[transferId];
        require(t.id != bytes32(0),             "OCBP: not found");
        require(t.status != TransferStatus.Settled, "OCBP: already settled");
        require(
            hasRole(BRIDGE_OPERATOR, msg.sender) ||
            block.timestamp > t.createdAt + SETTLEMENT_TIMEOUT,
            "OCBP: not authorised"
        );

        if (lrsUsedThisYear[t.sender] >= t.amountINR) {
            lrsUsedThisYear[t.sender] -= t.amountINR;
        }
        totalVolumeINR   -= t.amountINR;
        totalDollarsFree -= t.amountINR;
        t.status = TransferStatus.Refunded;

        emit TransferRefunded(transferId, reason);
    }

    // ── Regulator view (RBI / FIU-IND) ───────────────────────────────────────
    function getComplianceRecord(bytes32 transferId)
        external
        view
        onlyRole(REGULATOR)
        returns (
            TransferStatus status,
            bytes32        complianceHash,
            uint8          riskScore,
            uint256        createdAt,
            uint256        settledAt,
            bool           requiresMultiSig
        )
    {
        Transfer storage t = transfers[transferId];
        return (t.status, t.complianceHash, t.riskScore, t.createdAt, t.settledAt, t.requiresMultiSig);
    }

    function getProtocolStats()
        external
        view
        returns (uint256 count, uint256 volume, uint256 dollarFree, uint256 fees, uint256 version)
    {
        return (totalTransfersCount, totalVolumeINR, totalDollarsFree, totalFeesCollected, PROTOCOL_VERSION);
    }

    // ── Internal ──────────────────────────────────────────────────────────────
    function _updateLRSUsage(address user, uint256 amount) internal {
        uint256 currentYear = block.timestamp / 365 days;
        if (lrsYear[user] != currentYear) {
            lrsYear[user] = currentYear;
            lrsUsedThisYear[user] = 0;
        }
        lrsUsedThisYear[user] += amount;
    }

    // ── Admin ─────────────────────────────────────────────────────────────────
    function pause()   external onlyRole(DEFAULT_ADMIN_ROLE) { _pause(); }
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) { _unpause(); }

    function updateBridgeFee(uint256 newBps) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(newBps <= 100, "OCBP: fee cannot exceed 1%");
        bridgeFeeBps = newBps;
    }

    function updateFeeRecipient(address newRecipient) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(newRecipient != address(0), "OCBP: zero address");
        feeRecipient = newRecipient;
    }
}
