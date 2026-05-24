// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title ZK Compliance Verifier
 *
 * This contract implements a lightweight commitment scheme for
 * compliance verification. The full ZK-SNARK implementation
 * (Groth16 proofs) is the next milestone for the team to build.
 *
 * WHAT IT DOES NOW (commitment scheme):
 *   The user's AI agent computes:
 *     commitment = H(fema_code || lrs_amount || risk_score || nonce || address)
 *   This commitment is posted on-chain.
 *   The regulator can verify it later by asking the user to reveal
 *   the preimage — without any sensitive data being on-chain.
 *
 * WHAT THE TEAM BUILDS NEXT (full ZK-SNARK):
 *   Using Groth16 (via snarkjs + circom):
 *   - Circuit: proves fema_code is in valid set AND lrs_amount < limit
 *     WITHOUT revealing the actual values
 *   - Proof posted on-chain — verifier contract checks it in O(1)
 *   - Zero information leakage — China cannot see what India's
 *     citizens are sending money for
 *
 * WHY THIS MATTERS vs CHINA:
 *   China's e-CNY: every transaction visible to Beijing
 *   India's OCBP:  compliance provable without visibility
 *   This is the architectural difference that makes BRICS countries
 *   prefer India's protocol over China's.
 */
contract ZKComplianceVerifier {

    struct Commitment {
        bytes32 hash;        // H(fema, lrs, risk, nonce, address)
        uint256 timestamp;
        address prover;
        bool    revealed;    // True after prover discloses preimage
        bool    valid;       // Set after regulator verifies preimage
    }

    mapping(bytes32 => Commitment) public commitments;
    mapping(address => bytes32[]) public userCommitments;

    // Valid FEMA categories (1-13 as defined by RBI)
    uint8 public constant MIN_FEMA = 1;
    uint8 public constant MAX_FEMA = 13;

    // LRS limit in paise (₹2.07 crore)
    uint256 public constant LRS_LIMIT_PAISE = 207_000_000_00; // ₹2.07Cr in paise

    event CommitmentPosted(bytes32 indexed commitmentId, address indexed prover, uint256 timestamp);
    event CommitmentVerified(bytes32 indexed commitmentId, bool valid, address verifier);

    /**
     * @notice Post a compliance commitment before initiating a transfer.
     * Off-chain: agent computes H(fema || lrs || risk || nonce || sender)
     * On-chain:  only the hash is stored — zero information leaked.
     */
    function postCommitment(bytes32 commitmentHash) external returns (bytes32 commitmentId) {
        commitmentId = keccak256(abi.encodePacked(commitmentHash, msg.sender, block.timestamp));

        commitments[commitmentId] = Commitment({
            hash:      commitmentHash,
            timestamp: block.timestamp,
            prover:    msg.sender,
            revealed:  false,
            valid:     false
        });

        userCommitments[msg.sender].push(commitmentId);
        emit CommitmentPosted(commitmentId, msg.sender, block.timestamp);
    }

    /**
     * @notice Reveal the preimage for regulatory verification.
     * Called AFTER settlement — the regulator can verify that the
     * commitment was truthful without having seen the values on-chain.
     *
     * In the ZK-SNARK version this function is replaced entirely —
     * the proof itself is verifiable without revealing the preimage.
     */
    function revealAndVerify(
        bytes32 commitmentId,
        uint8   femaCategory,
        uint256 lrsAmount,
        uint8   riskScore,
        bytes32 nonce
    ) external returns (bool valid) {
        Commitment storage c = commitments[commitmentId];
        require(c.prover != address(0), "ZK: commitment not found");
        require(!c.revealed, "ZK: already revealed");

        bytes32 recomputed = keccak256(
            abi.encodePacked(femaCategory, lrsAmount, riskScore, nonce, c.prover)
        );

        bool hashMatches = recomputed == c.hash;
        bool femaInRange = femaCategory >= MIN_FEMA && femaCategory <= MAX_FEMA;
        bool lrsOk = lrsAmount <= LRS_LIMIT_PAISE;
        bool riskOk = riskScore <= 100;

        valid = hashMatches && femaInRange && lrsOk && riskOk;

        c.revealed = true;
        c.valid = valid;

        emit CommitmentVerified(commitmentId, valid, msg.sender);
    }

    /**
     * @notice Generate the commitment hash off-chain (helper — mirrors agent logic).
     * Call this from your AI agent before posting the commitment.
     */
    function computeCommitment(
        uint8   femaCategory,
        uint256 lrsAmount,
        uint8   riskScore,
        bytes32 nonce,
        address sender
    ) external pure returns (bytes32) {
        return keccak256(abi.encodePacked(femaCategory, lrsAmount, riskScore, nonce, sender));
    }
}
