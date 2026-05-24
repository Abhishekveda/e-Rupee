const { expect } = require("chai");
const { ethers } = require("hardhat");

/**
 * CBDCBridge contract tests
 * Run: npx hardhat test
 */

describe("CBDCBridge", function () {
  let bridge, mockAED, mockSGD;
  let owner, relayer, recipient, attacker;
  const FUND = ethers.parseUnits("1000000", 6);

  beforeEach(async function () {
    [owner, relayer, recipient, attacker] = await ethers.getSigners();

    const Stablecoin = await ethers.getContractFactory("MockStablecoin");
    mockAED = await Stablecoin.deploy("Mock AED", "mAED");
    mockSGD = await Stablecoin.deploy("Mock SGD", "mSGD");

    const Bridge = await ethers.getContractFactory("CBDCBridge");
    bridge = await Bridge.deploy(relayer.address, owner.address);

    // Fund bridge with test stablecoins
    await mockAED.transfer(await bridge.getAddress(), FUND);
    await mockSGD.transfer(await bridge.getAddress(), FUND);
  });

  // ── Deployment ─────────────────────────────────────────────────────────────

  it("sets owner and relayer correctly", async function () {
    expect(await bridge.owner()).to.equal(owner.address);
    expect(await bridge.relayer()).to.equal(relayer.address);
  });

  it("starts with 0.20% fee", async function () {
    expect(await bridge.bridgeFeesBps()).to.equal(20);
  });

  // ── lockAndRelay ───────────────────────────────────────────────────────────

  it("accepts a valid payment from relayer", async function () {
    const txHash = ethers.keccak256(ethers.toUtf8Bytes("cbdc-tx-001"));
    const amountINR = ethers.parseUnits("10000", 6); // 10,000 INR in paise*100
    const convertedAED = ethers.parseUnits("440", 6);

    await expect(
      bridge.connect(relayer).lockAndRelay(
        txHash,
        owner.address,
        recipient.address,
        amountINR,
        convertedAED,
        await mockAED.getAddress(),
        "P0102"
      )
    )
      .to.emit(bridge, "CrossBorderInitiated")
      .withArgs(
        txHash,
        owner.address,
        recipient.address,
        amountINR,
        convertedAED,
        await mockAED.getAddress(),
        "P0102"
      );

    expect(await bridge.totalPayments()).to.equal(1);
    const payment = await bridge.getPayment(txHash);
    expect(payment.status).to.equal(0); // Pending
  });

  it("rejects duplicate CBDC tx hash", async function () {
    const txHash = ethers.keccak256(ethers.toUtf8Bytes("duplicate-tx"));
    const args = [
      txHash, owner.address, recipient.address,
      1000n, 44n, await mockAED.getAddress(), "P0102",
    ];
    await bridge.connect(relayer).lockAndRelay(...args);
    await expect(bridge.connect(relayer).lockAndRelay(...args))
      .to.be.revertedWith("Duplicate CBDC tx");
  });

  it("rejects calls from non-relayer", async function () {
    const txHash = ethers.keccak256(ethers.toUtf8Bytes("attacker-tx"));
    await expect(
      bridge.connect(attacker).lockAndRelay(
        txHash, attacker.address, attacker.address,
        1000n, 44n, await mockAED.getAddress(), "P0102"
      )
    ).to.be.revertedWith("Not relayer");
  });

  it("rejects zero-amount transfers", async function () {
    const txHash = ethers.keccak256(ethers.toUtf8Bytes("zero-tx"));
    await expect(
      bridge.connect(relayer).lockAndRelay(
        txHash, owner.address, recipient.address,
        0n, 0n, await mockAED.getAddress(), "P0102"
      )
    ).to.be.revertedWith("Zero amount");
  });

  // ── settle ─────────────────────────────────────────────────────────────────

  it("settles a payment and transfers tokens to recipient", async function () {
    const txHash = ethers.keccak256(ethers.toUtf8Bytes("settle-tx-001"));
    const converted = ethers.parseUnits("440", 6);
    const fee = (converted * 20n) / 10000n;
    const net = converted - fee;

    await bridge.connect(relayer).lockAndRelay(
      txHash, owner.address, recipient.address,
      ethers.parseUnits("10000", 6), converted,
      await mockAED.getAddress(), "P0102"
    );

    const beforeBal = await mockAED.balanceOf(recipient.address);

    // Settle and verify event fields — skip timestamp (non-deterministic in EVM)
    const tx = await bridge.connect(relayer).settle(txHash);
    const receipt = await tx.wait();
    const event = receipt.logs.find(
      l => l.fragment && l.fragment.name === "CrossBorderSettled"
    );
    expect(event).to.not.be.undefined;
    expect(event.args[0]).to.equal(txHash);
    expect(event.args[1]).to.equal(recipient.address);
    expect(event.args[2]).to.equal(net);
    expect(event.args[3]).to.equal(fee);

    const afterBal = await mockAED.balanceOf(recipient.address);
    expect(afterBal - beforeBal).to.equal(net);

    const payment = await bridge.getPayment(txHash);
    expect(payment.status).to.equal(1); // Settled
  });

  it("cannot settle twice", async function () {
    const txHash = ethers.keccak256(ethers.toUtf8Bytes("double-settle"));
    await bridge.connect(relayer).lockAndRelay(
      txHash, owner.address, recipient.address,
      1000n, ethers.parseUnits("44", 6), await mockAED.getAddress(), "P0102"
    );
    await bridge.connect(relayer).settle(txHash);
    await expect(bridge.connect(relayer).settle(txHash))
      .to.be.revertedWith("Already finalised");
  });

  // ── refund ─────────────────────────────────────────────────────────────────

  it("emits refund event on failed bridge", async function () {
    const txHash = ethers.keccak256(ethers.toUtf8Bytes("refund-tx"));
    await bridge.connect(relayer).lockAndRelay(
      txHash, owner.address, recipient.address,
      1000n, 44n, await mockAED.getAddress(), "P0102"
    );
    await expect(bridge.connect(relayer).refund(txHash, "FX oracle timeout"))
      .to.emit(bridge, "CrossBorderRefunded")
      .withArgs(txHash, "FX oracle timeout");
  });

  // ── admin ──────────────────────────────────────────────────────────────────

  it("owner can update relayer", async function () {
    await bridge.connect(owner).setRelayer(attacker.address);
    expect(await bridge.relayer()).to.equal(attacker.address);
  });

  it("non-owner cannot update relayer", async function () {
    await expect(bridge.connect(attacker).setRelayer(attacker.address))
      .to.be.revertedWith("Not owner");
  });

  it("cannot set fee above 1%", async function () {
    await expect(bridge.connect(owner).setFees(101))
      .to.be.revertedWith("Fee too high");
  });
});
