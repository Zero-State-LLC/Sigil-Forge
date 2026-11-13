// Knowledge-of-intent circuit (v2)
//
// Private: intent_bytes[256] (zero-padded), nonce[32]
// Public:  intent_len, the byte length of the intent
//          expected_commitment[32] = SHA-256(nonce || intent_bytes)
//
// intent_len is bound exactly: every byte before it is non-zero and every
// byte from it on is zero. So the published length is proven, and an intent
// cannot be confused with the same intent plus trailing zero bytes.
//
// Proves knowledge of a preimage for the ZK companion commitment
// (src/sigil_forge/proofs/zk_commit.py). Domain-separated public commitment
// is bound off-circuit via the intent capsule.
//
// SHA-256 is built here from the standard library's compression function, so
// the circuit has no external dependency and compiles offline. The message is
// always 288 bytes, so the padding is fixed: five 64-byte blocks.
//
// Tested with nargo 1.0.0 and bb 6.0.0. Core forge does not require either.

use std::hash::sha256_compression;

global MAX_INTENT: u32 = 256;
global BLOCKS: u32 = 5;

fn sha256_288(msg: [u8; 288]) -> [u8; 32] {
    let mut padded: [u8; 320] = [0; 320];
    for i in 0..288 {
        padded[i] = msg[i];
    }
    padded[288] = 0x80;
    // 64-bit big-endian bit length: 288 * 8 = 2304 = 0x0900
    padded[318] = 0x09;
    padded[319] = 0x00;

    let mut state: [u32; 8] = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
    ];
    for b in 0..BLOCKS {
        let mut words: [u32; 16] = [0; 16];
        for w in 0..16 {
            let o = b * 64 + w * 4;
            words[w] = ((padded[o] as u32) << 24)
                | ((padded[o + 1] as u32) << 16)
                | ((padded[o + 2] as u32) << 8)
                | (padded[o + 3] as u32);
        }
        state = sha256_compression(words, state);
    }

    let mut out: [u8; 32] = [0; 32];
    for w in 0..8 {
        out[w * 4] = (state[w] >> 24) as u8;
        out[w * 4 + 1] = (state[w] >> 16) as u8;
        out[w * 4 + 2] = (state[w] >> 8) as u8;
        out[w * 4 + 3] = state[w] as u8;
    }
    out
}

fn main(
    intent_len: pub u32,
    intent_bytes: [u8; 256],
    nonce: [u8; 32],
    expected_commitment: pub [u8; 32],
) {
    // intent_len bounds
    assert(intent_len <= MAX_INTENT);

    // Bytes of the intent are non-zero; padding after intent_len is zero.
    for i in 0..256 {
        if i as u32 >= intent_len {
            assert(intent_bytes[i] == 0);
        } else {
            assert(intent_bytes[i] != 0);
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

    let digest = sha256_288(preimage);
    for i in 0..32 {
        assert(digest[i] == expected_commitment[i]);
    }
}
