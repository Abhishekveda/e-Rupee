/**
 * deploy.js — Hardhat deployment for CBDCBridge + mock stablecoins
 *
 * Usage:
 *   npx hardhat run scripts/deploy.js --network sepolia
 *
 * Requires .env with:
 *   PRIVATE_KEY=0x...
 *   SEPOLIA_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/YOUR_KEY
 *   ETHERSCAN_API_KEY=...
 */

const { ethers } = require("hardhat");

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying from:", deployer.address);
  console.log("Balance:", ethers.formatEther(await deployer.provider.getBalance(deployer.address)), "ETH\n");

  // 1. Deploy mock stablecoins (AED and SGD)
  const Stablecoin = await ethers.getContractFactory("MockStablecoin");

  console.log("Deploying MockAED...");
  const mockAED = await Stablecoin.deploy("Mock UAE Dirham", "mAED");
  await mockAED.waitForDeployment();
  console.log("  MockAED:", await mockAED.getAddress());

  console.log("Deploying MockSGD...");
  const mockSGD = await Stablecoin.deploy("Mock Singapore Dollar", "mSGD");
  await mockSGD.waitForDeployment();
  console.log("  MockSGD:", await mockSGD.getAddress());

  // 2. Deploy CBDCBridge
  // relayer = deployer for PoC; oracle = deployer for PoC (replace with Chainlink)
  console.log("\nDeploying CBDCBridge...");
  const Bridge = await ethers.getContractFactory("CBDCBridge");
  const bridge = await Bridge.deploy(deployer.address, deployer.address);
  await bridge.waitForDeployment();
  const bridgeAddr = await bridge.getAddress();
  console.log("  CBDCBridge:", bridgeAddr);

  // 3. Fund bridge with mock stablecoins so it can pay out
  const FUND_AMOUNT = ethers.parseUnits("1000000", 6); // 1M tokens
  await mockAED.transfer(bridgeAddr, FUND_AMOUNT);
  await mockSGD.transfer(bridgeAddr, FUND_AMOUNT);
  console.log("  Funded bridge with 1M mAED and 1M mSGD");

  // 4. Write addresses to a local file for the backend to read
  const fs = require("fs");
  const addresses = {
    network: "sepolia",
    bridge: bridgeAddr,
    mockAED: await mockAED.getAddress(),
    mockSGD: await mockSGD.getAddress(),
    deployer: deployer.address,
    deployedAt: new Date().toISOString(),
  };
  fs.writeFileSync(
    "./deployed-addresses.json",
    JSON.stringify(addresses, null, 2)
  );
  console.log("\nAddresses saved to deployed-addresses.json");
  console.log(JSON.stringify(addresses, null, 2));

  console.log("\n✓ Deployment complete. Verify on Etherscan:");
  console.log(`  npx hardhat verify --network sepolia ${bridgeAddr} "${deployer.address}" "${deployer.address}"`);
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
