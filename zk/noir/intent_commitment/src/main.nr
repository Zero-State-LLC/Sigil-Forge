// Knowledge-of-intent circuit (v1)
//
// Private: intent_len, intent_bytes[256] (zero-padded), nonce[32]
// Public:  expected_commitment[32] = SHA-256(nonce || intent_bytes)
//
// Proves knowledge of a preimage for the ZK companion commitment
// (src/sigil_forge/proofs/zk_commit.py). Domain-separated public commitment
// is bound off-circuit via the intent capsule.
//
// Requires nargo with std::hash::sha256. Core forge does not require nargo.

use std::hash::sha256;

global MAX_INTENT: u32 = 256;
global NONCE_LEN: u32 = 32;

fn main(
    intent_len: u32,
    intent_bytes: [u8; 256],
    nonce: [u8; 32],
    expected_commitment: pub [u8; 32],
) {
    // intent_len bounds
    assert(intent_len <= MAX_INTENT);

    // Padding after intent_len must be zero
    for i in 0..256 {
        if i as u32 >= intent_len {
            assert(intent_bytes[i] == 0);
        }
    }

    // Preimage = nonce || intent_bytes (288 bytes)
    let mut preimage: [u8; 288] = [0; 288];
    for i in 0..32 {
        preimage[i] = nonce[i];
    }
    for i in 0..256 {
        preimage[32 + i] = intent_bytes[i];
    }

    let digest = sha256::digest(preimage);
    for i in 0..32 {
        assert(digest[i] == expected_commitment[i]);
    }
}
