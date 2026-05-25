// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title  CBDCBridge
 * @notice e-Rupee cross-border settlement bridge (PoC)
 *
 * Flow:
 *  1. Backend calls lockAndRelay() with the e-Rupee CBDC tx hash
 *  2. Contract records the payment and emits CrossBorderInitiated
 *  3. Relayer calls settle() → releases stablecoin to recipient
 *
 * Security: owner + relayer access control, duplicate-hash guard,
 *           zero-amount guard, 1% fee ceiling, reentrancy-safe ordering.
 */

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

contract CBDCBridge {

    address public owner;
    address public relayer;

    uint256 public bridgeFeesBps  = 20;   // 0.20%
    uint256 public constant MAX_FEE = 100; // 1% ceiling

    enum Status { Pending, Settled, Refunded }

    struct Payment {
        address sender;
        address recipient;
        uint256 amountInr;
        uint256 convertedAmount;
        address destToken;
        uint64  timestamp;
        Status  status;
        string  purposeCode;
    }

    mapping(bytes32 => Payment) public payments;
    bytes32[] public paymentIds;

    // ── Events ────────────────────────────────────────────────────────────────
    event CrossBorderInitiated(bytes32 indexed txHash, address indexed sender, address indexed recipient, uint256 amountInr, uint256 convertedAmount, address destToken, string purposeCode);
    event CrossBorderSettled(bytes32 indexed txHash, address indexed recipient, uint256 netAmount, uint256 fee, uint256 ts);
    event CrossBorderRefunded(bytes32 indexed txHash, string reason);
    event RelayerUpdated(address oldRelayer, address newRelayer);
    event FeesUpdated(uint256 oldBps, uint256 newBps);

    modifier onlyOwner()   { require(msg.sender == owner,   "Not owner");   _; }
    modifier onlyRelayer() { require(msg.sender == relayer, "Not relayer"); _; }

    constructor(address _relayer, address _fxOracle) {
        owner   = msg.sender;
        relayer = _relayer;
    }

    // ── Core ──────────────────────────────────────────────────────────────────

    function lockAndRelay(
        bytes32        cbdcTxHash,
        address        sender,
        address        recipient,
        uint256        amountInr,
        uint256        convertedAmt,
        address        destToken,
        string calldata purposeCode
    ) external onlyRelayer {
        require(payments[cbdcTxHash].timestamp == 0, "Duplicate CBDC tx");
        require(recipient != address(0),             "Bad recipient");
        require(amountInr > 0,                       "Zero amount");

        // Write via storage pointer — avoids struct-literal stack overflow
        Payment storage p = payments[cbdcTxHash];
        p.sender          = sender;
        p.recipient       = recipient;
        p.amountInr       = amountInr;
        p.convertedAmount = convertedAmt;
        p.destToken       = destToken;
        p.timestamp       = uint64(block.timestamp);
        p.status          = Status.Pending;
        p.purposeCode     = purposeCode;

        paymentIds.push(cbdcTxHash);
        emit CrossBorderInitiated(cbdcTxHash, sender, recipient, amountInr, convertedAmt, destToken, purposeCode);
    }

    function settle(bytes32 cbdcTxHash) external onlyRelayer {
        Payment storage p = payments[cbdcTxHash];
        require(p.timestamp > 0,              "Payment not found");
        require(p.status == Status.Pending,   "Already finalised");

        uint256 fee = (p.convertedAmount * bridgeFeesBps) / 10_000;
        uint256 net = p.convertedAmount - fee;

        p.status = Status.Settled; // state change BEFORE external call
        require(IERC20(p.destToken).transfer(p.recipient, net), "Transfer failed");

        emit CrossBorderSettled(cbdcTxHash, p.recipient, net, fee, block.timestamp);
    }

    function refund(bytes32 cbdcTxHash, string calldata reason) external onlyRelayer {
        Payment storage p = payments[cbdcTxHash];
        require(p.status == Status.Pending, "Cannot refund");
        p.status = Status.Refunded;
        emit CrossBorderRefunded(cbdcTxHash, reason);
    }

    // ── Views ─────────────────────────────────────────────────────────────────
    function getPayment(bytes32 txHash) external view returns (Payment memory) { return payments[txHash]; }
    function totalPayments() external view returns (uint256) { return paymentIds.length; }

    // ── Admin ─────────────────────────────────────────────────────────────────
    function setRelayer(address r) external onlyOwner { emit RelayerUpdated(relayer, r); relayer = r; }
    function setFees(uint256 bps) external onlyOwner  { require(bps <= MAX_FEE, "Fee too high"); emit FeesUpdated(bridgeFeesBps, bps); bridgeFeesBps = bps; }
    function withdrawFees(address token, address to) external onlyOwner { IERC20(token).transfer(to, IERC20(token).balanceOf(address(this))); }
}
