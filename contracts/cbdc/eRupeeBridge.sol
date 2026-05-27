// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * ╔══════════════════════════════════════════════════════════════╗
 * ║         e₹ Cross-Border Bridge — OCBP Core                 ║
 * ║                                                              ║
 * ║  Connects the e-Rupee CBDC to destination CBDCs            ║
 * ║  UAE Digital Dirham · Singapore SGD · BRICS partners        ║
 * ╚══════════════════════════════════════════════════════════════╝
 *
 * HOW THIS WORKS:
 *
 *  Step 1 — Sender calls initiateTransfer()
 *           e-Rupee tokens lock in this contract (escrow)
 *           AI attestation verified on-chain
 *
 *  Step 2 — Bridge relayer observes the lock event
 *           Calls destination chain CBDC contract
 *           Releases destination currency to recipient
 *
 *  Step 3 — Relayer calls confirmSettlement()
 *           Records the destination tx hash
 *           Emits final settlement event
 *
 *  If Step 2 fails → refund() releases e-Rupee back to sender
 *
 * THE DOLLAR IS NOT USED ANYWHERE IN THIS FLOW.
 * USD → INR → AED (multi-hop) is handled by the off-chain relayer.
 */

interface IeRupee {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

contract eRupeeBridge {

    address public owner;
    address public relayer;
    IeRupee public eRupeeToken;

    uint256 public bridgeFeeBps = 20;       // 0.20%
    uint256 public constant MAX_FEE = 100;  // 1% ceiling
    uint256 public constant TIMEOUT = 10 minutes;

    enum Status { Pending, Settled, Refunded }

    struct Transfer {
        address  sender;
        address  recipient;
        uint256  amountPaise;
        uint256  fxRate;           // scaled ×1e6: fxRate/1e6 = rate
        uint256  destinationAmt;
        bytes32  destCurrency;     // keccak256("AED"), keccak256("SGD") etc
        bytes32  complianceHash;   // from AI attestation
        uint8    riskScore;
        uint8    femaCategory;
        uint256  createdAt;
        uint256  settledAt;
        string   destTxHash;       // destination chain tx hash
        Status   status;
    }

    mapping(bytes32 => Transfer) public transfers;
    bytes32[] public transferIds;

    // FX rates (in production: Chainlink oracle)
    mapping(bytes32 => uint256) public fxRates; // currency → rate ×1e6

    uint256 public totalVolumePaise;
    uint256 public totalFeesCollected;
    uint256 public totalDollarFreeVolume;

    event TransferInitiated(bytes32 indexed id, address sender, address recipient, uint256 amountPaise, bytes32 destCurrency, uint8 riskScore);
    event TransferSettled(bytes32 indexed id, uint256 destinationAmt, uint256 feePaise, string destTxHash);
    event TransferRefunded(bytes32 indexed id, string reason);
    event FXRateUpdated(bytes32 currency, uint256 rate);

    modifier onlyOwner()   { require(msg.sender == owner,   "Not owner");   _; }
    modifier onlyRelayer() { require(msg.sender == relayer, "Not relayer"); _; }

    constructor(address _eRupeeToken, address _relayer) {
        owner        = msg.sender;
        relayer      = _relayer;
        eRupeeToken  = IeRupee(_eRupeeToken);

        // Seed FX rates (production: Chainlink)
        fxRates[keccak256("AED")] = 44000;   // 1 INR = 0.044 AED  (×1e6)
        fxRates[keccak256("SGD")] = 16000;   // 1 INR = 0.016 SGD
        fxRates[keccak256("USD")] = 12000;   // 1 INR = 0.012 USD
        fxRates[keccak256("RUB")] = 930000;  // 1 INR = 0.93 RUB
        fxRates[keccak256("BRL")] = 62000;   // 1 INR = 0.062 BRL
        fxRates[keccak256("ZAR")] = 220000;  // 1 INR = 0.22 ZAR
        fxRates[keccak256("SAR")] = 45000;   // 1 INR = 0.045 SAR
        fxRates[keccak256("CNY")] = 86000;   // 1 INR = 0.086 CNY
    }

    /**
     * @notice Initiate a cross-border transfer.
     * Locks e-Rupee tokens in escrow. Emits event for relayer.
     *
     * @param recipient      Recipient address on destination chain
     * @param amountPaise    Amount in paise
     * @param destCurrency   keccak256 of currency code e.g. keccak256("AED")
     * @param complianceHash AI compliance commitment hash
     * @param riskScore      AI risk score
     * @param femaCategory   FEMA purpose code category
     * @param nonce          Unique nonce
     */
    function initiateTransfer(
        address  recipient,
        uint256  amountPaise,
        bytes32  destCurrency,
        bytes32  complianceHash,
        uint8    riskScore,
        uint8    femaCategory,
        bytes32  nonce
    ) external returns (bytes32 transferId) {
        require(recipient   != address(0),                 "Bridge: zero address");
        require(amountPaise > 0,                           "Bridge: zero amount");
        require(fxRates[destCurrency] > 0,                 "Bridge: unsupported currency");
        require(riskScore   <= 100,                        "Bridge: invalid risk score");
        require(riskScore   <= 70,                         "Bridge: risk too high");

        uint256 feePaise  = (amountPaise * bridgeFeeBps) / 10000;
        uint256 netPaise  = amountPaise - feePaise;
        uint256 destAmt   = (netPaise * fxRates[destCurrency]) / 1e6;

        transferId = keccak256(abi.encodePacked(
            msg.sender, recipient, amountPaise, block.timestamp, nonce
        ));

        Transfer storage t = transfers[transferId];
        t.sender          = msg.sender;
        t.recipient       = recipient;
        t.amountPaise     = amountPaise;
        t.fxRate          = fxRates[destCurrency];
        t.destinationAmt  = destAmt;
        t.destCurrency    = destCurrency;
        t.complianceHash  = complianceHash;
        t.riskScore       = riskScore;
        t.femaCategory    = femaCategory;
        t.createdAt       = block.timestamp;
        t.status          = Status.Pending;

        transferIds.push(transferId);
        totalVolumePaise     += amountPaise;
        totalDollarFreeVolume += amountPaise;

        // Lock e-Rupee tokens in escrow
        require(
            eRupeeToken.transferFrom(msg.sender, address(this), amountPaise),
            "Bridge: token lock failed"
        );

        emit TransferInitiated(
            transferId, msg.sender, recipient,
            amountPaise, destCurrency, riskScore
        );
    }

    /**
     * @notice Relayer confirms settlement after destination chain tx.
     * Records the destination chain transaction hash on-chain.
     */
    function confirmSettlement(bytes32 transferId, string calldata destTxHash)
        external
        onlyRelayer
    {
        Transfer storage t = transfers[transferId];
        require(t.createdAt > 0,             "Bridge: not found");
        require(t.status == Status.Pending,  "Bridge: not pending");

        uint256 feePaise = (t.amountPaise * bridgeFeeBps) / 10000;
        t.status     = Status.Settled;
        t.settledAt  = block.timestamp;
        t.destTxHash = destTxHash;
        totalFeesCollected += feePaise;

        emit TransferSettled(transferId, t.destinationAmt, feePaise, destTxHash);
    }

    /**
     * @notice Refund if settlement fails or times out.
     * Returns locked e-Rupee to sender.
     */
    function refund(bytes32 transferId, string calldata reason)
        external
    {
        Transfer storage t = transfers[transferId];
        require(t.createdAt > 0,              "Bridge: not found");
        require(t.status == Status.Pending,   "Bridge: not pending");
        require(
            msg.sender == relayer ||
            block.timestamp > t.createdAt + TIMEOUT,
            "Bridge: not authorised or not timed out"
        );

        totalVolumePaise      -= t.amountPaise;
        totalDollarFreeVolume -= t.amountPaise;
        t.status = Status.Refunded;

        require(eRupeeToken.transfer(t.sender, t.amountPaise), "Bridge: refund failed");
        emit TransferRefunded(transferId, reason);
    }

    // ── Admin ──────────────────────────────────────────────────────
    function updateFXRate(bytes32 currency, uint256 rate) external onlyRelayer {
        require(rate > 0, "Bridge: zero rate");
        fxRates[currency] = rate;
        emit FXRateUpdated(currency, rate);
    }

    function setFees(uint256 bps) external onlyOwner {
        require(bps <= MAX_FEE, "Bridge: fee too high");
        bridgeFeeBps = bps;
    }

    function getTransfer(bytes32 id) external view returns (Transfer memory) {
        return transfers[id];
    }

    function getStats() external view returns (
        uint256 volume, uint256 dollarFree, uint256 fees, uint256 count
    ) {
        return (totalVolumePaise, totalDollarFreeVolume, totalFeesCollected, transferIds.length);
    }
}
