// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title CBDCBridge
 * @notice Cross-border settlement bridge for e-Rupee (CBDC) payments.
 *
 * Flow:
 *   1. RBI authorised relayer calls lockAndRelay() with the CBDC tx hash
 *      from the backend (after the e-Rupee debit is confirmed).
 *   2. Contract locks the relay record and emits CrossBorderInitiated.
 *   3. Off-chain oracle (Chainlink / custom) confirms FX rate and calls settle().
 *   4. settle() transfers recipient tokens and emits CrossBorderSettled.
 *
 * For the PoC, we emit events that the frontend listens to via ethers.js.
 * In production this contract would hold real stablecoin balances (AED / SGD).
 */

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

contract CBDCBridge {

    // ── State ──────────────────────────────────────────────────────────────────

    address public owner;
    address public relayer;          // authorised backend relayer address
    address public fxOracle;         // Chainlink aggregator or custom oracle

    uint256 public bridgeFeesBps = 20;   // 0.20% in basis points
    uint256 public constant MAX_FEE_BPS = 100;  // 1% ceiling

    enum Status { Pending, Settled, Refunded, Expired }

    struct PaymentRecord {
        bytes32  cbdcTxHash;          // hash from e-Rupee backend
        address  sender;              // original INR sender (identifier)
        address  recipient;           // receiving wallet on destination chain
        uint256  amountInr;           // amount in smallest INR unit (paise)
        uint256  convertedAmount;     // destination currency amount
        address  destinationToken;    // ERC-20 representing AED/SGD stablecoin
        uint64   timestamp;
        Status   status;
        string   purposeCode;         // FEMA purpose code for compliance
    }

    mapping(bytes32 => PaymentRecord) public payments;   // key: cbdcTxHash
    bytes32[] public paymentIds;

    // ── Events ─────────────────────────────────────────────────────────────────

    event CrossBorderInitiated(
        bytes32 indexed cbdcTxHash,
        address indexed sender,
        address indexed recipient,
        uint256 amountInr,
        uint256 convertedAmount,
        address destinationToken,
        string  purposeCode
    );

    event CrossBorderSettled(
        bytes32 indexed cbdcTxHash,
        address indexed recipient,
        uint256 settledAmount,
        uint256 fee,
        uint256 blockTimestamp
    );

    event CrossBorderRefunded(bytes32 indexed cbdcTxHash, string reason);

    event RelayerUpdated(address indexed oldRelayer, address indexed newRelayer);
    event FeesUpdated(uint256 oldBps, uint256 newBps);

    // ── Modifiers ──────────────────────────────────────────────────────────────

    modifier onlyOwner()   { require(msg.sender == owner,   "Not owner");   _; }
    modifier onlyRelayer() { require(msg.sender == relayer, "Not relayer"); _; }

    // ── Constructor ────────────────────────────────────────────────────────────

    constructor(address _relayer, address _fxOracle) {
        owner    = msg.sender;
        relayer  = _relayer;
        fxOracle = _fxOracle;
    }

    // ── Core: initiate cross-border transfer ───────────────────────────────────

    /**
     * @notice Called by the authorised relayer after e-Rupee debit is confirmed.
     * @param cbdcTxHash    SHA-256 hash of the CBDC transaction from the RBI ledger
     * @param sender        Sender identifier (can be a hashed wallet ID for privacy)
     * @param recipient     Destination wallet address
     * @param amountInr     Transfer amount in paise (INR × 100)
     * @param convertedAmt  Pre-calculated destination amount (relayer provides, oracle validates)
     * @param destToken     ERC-20 stablecoin address (mock AED / SGD token)
     * @param purposeCode   FEMA remittance purpose code
     */
    function lockAndRelay(
        bytes32 cbdcTxHash,
        address sender,
        address recipient,
        uint256 amountInr,
        uint256 convertedAmt,
        address destToken,
        string calldata purposeCode
    ) external onlyRelayer {
        require(payments[cbdcTxHash].timestamp == 0, "Duplicate CBDC tx");
        require(recipient != address(0), "Bad recipient");
        require(amountInr > 0, "Zero amount");

        PaymentRecord storage p = payments[cbdcTxHash];
        p.cbdcTxHash       = cbdcTxHash;
        p.sender           = sender;
        p.recipient        = recipient;
        p.amountInr        = amountInr;
        p.convertedAmount  = convertedAmt;
        p.destinationToken = destToken;
        p.timestamp        = uint64(block.timestamp);
        p.status           = Status.Pending;
        p.purposeCode      = purposeCode;

        paymentIds.push(cbdcTxHash);

        emit CrossBorderInitiated(
            cbdcTxHash, sender, recipient,
            amountInr, convertedAmt, destToken, purposeCode
        );
    }

    // ── Core: settle (release funds to recipient) ──────────────────────────────

    /**
     * @notice Finalises a pending payment. Called by relayer after FX oracle confirms.
     * @param cbdcTxHash  The payment to settle
     */
    function settle(bytes32 cbdcTxHash) external onlyRelayer {
        PaymentRecord storage p = payments[cbdcTxHash];
        require(p.timestamp > 0, "Payment not found");
        require(p.status == Status.Pending, "Already finalised");

        uint256 fee = (p.convertedAmount * bridgeFeesBps) / 10_000;
        uint256 netAmount = p.convertedAmount - fee;

        // Transfer destination stablecoin to recipient
        bool ok = IERC20(p.destinationToken).transfer(p.recipient, netAmount);
        require(ok, "Token transfer failed");

        p.status = Status.Settled;

        emit CrossBorderSettled(
            cbdcTxHash,
            p.recipient,
            netAmount,
            fee,
            block.timestamp
        );
    }

    // ── Refund (if bridge fails or expires) ───────────────────────────────────

    function refund(bytes32 cbdcTxHash, string calldata reason) external onlyRelayer {
        PaymentRecord storage p = payments[cbdcTxHash];
        require(p.status == Status.Pending, "Cannot refund");
        p.status = Status.Refunded;
        emit CrossBorderRefunded(cbdcTxHash, reason);
        // In production: call back to CBDC API to re-credit sender wallet
    }

    // ── View helpers ──────────────────────────────────────────────────────────

    function getPayment(bytes32 cbdcTxHash) external view returns (PaymentRecord memory) {
        return payments[cbdcTxHash];
    }

    function totalPayments() external view returns (uint256) {
        return paymentIds.length;
    }

    // ── Admin ──────────────────────────────────────────────────────────────────

    function setRelayer(address _relayer) external onlyOwner {
        emit RelayerUpdated(relayer, _relayer);
        relayer = _relayer;
    }

    function setFees(uint256 bps) external onlyOwner {
        require(bps <= MAX_FEE_BPS, "Fee too high");
        emit FeesUpdated(bridgeFeesBps, bps);
        bridgeFeesBps = bps;
    }

    function withdrawFees(address token, address to) external onlyOwner {
        uint256 bal = IERC20(token).balanceOf(address(this));
        IERC20(token).transfer(to, bal);
    }
}
