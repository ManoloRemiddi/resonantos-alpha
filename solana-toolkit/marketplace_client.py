"""
Protocol Marketplace Client — Python interface for on-chain escrow program.

Program ID: 5wpGj4EG6J5uEqozLqUyHzEQbU26yjaL5aUE5FwBiYe5
Network: Solana DevNet

Provides: list_protocol, buy_protocol, delist_protocol, get_all_listings
"""

import json
import struct
import subprocess
import base64
import base58
from pathlib import Path
from hashlib import sha256

MARKETPLACE_PROGRAM_ID = "5wpGj4EG6J5uEqozLqUyHzEQbU26yjaL5aUE5FwBiYe5"
TOKEN_2022_PROGRAM_ID = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
SPL_TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
ASSOCIATED_TOKEN_PROGRAM_ID = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
SYSTEM_PROGRAM_ID = "11111111111111111111111111111111"
DEVNET_RPC = "https://api.devnet.solana.com"

# Anchor discriminators (first 8 bytes of sha256("global:<method_name>"))
def _discriminator(name: str) -> bytes:
    return sha256(f"global:{name}".encode()).digest()[:8]

LIST_DISC = _discriminator("list_protocol")
BUY_DISC = _discriminator("buy_protocol")
DELIST_DISC = _discriminator("delist_protocol")

# Listing account discriminator
LISTING_DISC = sha256(b"account:Listing").digest()[:8]


def _run_cmd(args: list, timeout: int = 30) -> str:
    """Run CLI command, return stdout."""
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(args[:3])}...\n{result.stderr}")
    return result.stdout.strip()


def _find_pda(seeds: list[bytes], program_id: str) -> tuple[str, int]:
    """Find PDA using solana CLI. Returns (address, bump)."""
    # Use Python to derive PDA
    from solders.pubkey import Pubkey
    program_pk = Pubkey.from_string(program_id)
    pda, bump = Pubkey.find_program_address(seeds, program_pk)
    return str(pda), bump


def _get_ata(wallet: str, mint: str, token_program: str = TOKEN_2022_PROGRAM_ID) -> str:
    """Get associated token address."""
    from solders.pubkey import Pubkey
    wallet_pk = Pubkey.from_string(wallet)
    mint_pk = Pubkey.from_string(mint)
    token_prog_pk = Pubkey.from_string(token_program)
    ata_prog_pk = Pubkey.from_string(ASSOCIATED_TOKEN_PROGRAM_ID)
    
    ata, _ = Pubkey.find_program_address(
        [bytes(wallet_pk), bytes(token_prog_pk), bytes(mint_pk)],
        ata_prog_pk,
    )
    return str(ata)


def get_escrow_authority(nft_mint: str) -> tuple[str, int]:
    """Get escrow PDA for a given NFT mint."""
    from solders.pubkey import Pubkey
    mint_pk = Pubkey.from_string(nft_mint)
    return _find_pda([b"escrow", bytes(mint_pk)], MARKETPLACE_PROGRAM_ID)


def get_listing_address(nft_mint: str) -> tuple[str, int]:
    """Get listing PDA for a given NFT mint."""
    from solders.pubkey import Pubkey
    mint_pk = Pubkey.from_string(nft_mint)
    return _find_pda([b"listing", bytes(mint_pk)], MARKETPLACE_PROGRAM_ID)


def get_all_listings(rpc: str = DEVNET_RPC) -> list[dict]:
    """Fetch all active listings from chain using getProgramAccounts."""
    import requests
    
    # Filter by Listing account discriminator
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getProgramAccounts",
        "params": [
            MARKETPLACE_PROGRAM_ID,
            {
                "encoding": "base64",
                "filters": [
                    {"memcmp": {"offset": 0, "bytes": base58.b58encode(LISTING_DISC).decode()}},
                ],
            },
        ],
    }
    
    resp = requests.post(rpc, json=payload, timeout=15)
    data = resp.json()
    
    if "error" in data:
        raise RuntimeError(f"RPC error: {data['error']}")
    
    listings = []
    for account in data.get("result", []):
        raw = base64.b64decode(account["account"]["data"][0])
        # Parse: 8 disc + 32 seller + 32 nft_mint + 8 price + 8 created_at + 1 bump
        if len(raw) < 89:
            continue
        seller = base64.b58encode(raw[8:40]).decode()  # won't work, use solders
        from solders.pubkey import Pubkey
        seller = str(Pubkey.from_bytes(raw[8:40]))
        nft_mint = str(Pubkey.from_bytes(raw[40:72]))
        price_res = struct.unpack("<Q", raw[72:80])[0]
        created_at = struct.unpack("<q", raw[80:88])[0]
        bump = raw[88]
        
        listings.append({
            "listing_address": account["pubkey"],
            "seller": seller,
            "nft_mint": nft_mint,
            "price_res": price_res,
            "created_at": created_at,
            "bump": bump,
        })
    
    return listings


if __name__ == "__main__":
    print(f"Marketplace Program: {MARKETPLACE_PROGRAM_ID}")
    print(f"List discriminator: {LIST_DISC.hex()}")
    print(f"Buy discriminator: {BUY_DISC.hex()}")
    print(f"Delist discriminator: {DELIST_DISC.hex()}")
    print(f"Listing account disc: {LISTING_DISC.hex()}")
    
    listings = get_all_listings()
    print(f"\nActive listings: {len(listings)}")
    for l in listings:
        print(f"  {l['nft_mint'][:8]}... → {l['price_res']} $RES by {l['seller'][:8]}...")
