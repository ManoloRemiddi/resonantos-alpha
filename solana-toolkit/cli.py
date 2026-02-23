#!/usr/bin/env python3
"""ResonantOS Solana Toolkit CLI."""

import argparse
import json
import sys

from toolkit import create_toolkit


def cmd_balance(args):
    """Show SOL balance."""
    tk = create_toolkit(keypair_path=args.keypair, network=args.network)
    bal = tk.wallet.get_balance()
    print(f"Wallet: {tk.pubkey}")
    print(f"Network: {tk.wallet.network}")
    print(f"SOL Balance: {bal:.9f}")


def cmd_airdrop(args):
    """Request SOL airdrop (devnet/testnet)."""
    tk = create_toolkit(keypair_path=args.keypair, network=args.network)
    print(f"Requesting {args.amount} SOL airdrop to {tk.pubkey}...")
    sig = tk.wallet.airdrop(args.amount)
    print(f"Airdrop tx: {sig}")


def cmd_create_token(args):
    """Create a new token mint."""
    tk = create_toolkit(keypair_path=args.keypair, network=args.network)
    if args.type == "spl":
        mint = tk.tokens.create_spl_token(decimals=args.decimals)
    else:
        mint = tk.tokens.create_token2022_non_transferable(decimals=args.decimals)
    print(f"Mint: {mint}")


def cmd_mint(args):
    """Mint tokens to a wallet."""
    tk = create_toolkit(keypair_path=args.keypair, network=args.network)
    program = "token2022" if args.token2022 else "spl"
    sig = tk.tokens.mint_tokens(
        mint=args.mint,
        destination_owner=args.to,
        amount=args.amount,
        token_program=program,
    )
    print(f"Mint tx: {sig}")


def cmd_tokens(args):
    """Show all token balances."""
    tk = create_toolkit(keypair_path=args.keypair, network=args.network)
    owner = args.owner or str(tk.wallet.pubkey)
    balances = tk.tokens.get_token_balances(owner=owner)
    if not balances:
        print("No token accounts found.")
        return
    print(f"{'Mint':<50} {'Balance':>15} {'Program':>10}")
    print("-" * 78)
    for b in balances:
        print(f"{b['mint']:<50} {b['balance']:>15.6f} {b['program']:>10}")


def cmd_mint_nft(args):
    """Mint a soulbound NFT."""
    tk = create_toolkit(keypair_path=args.keypair, network=args.network)
    recipient = args.to or str(tk.wallet.pubkey)
    result = tk.nfts.mint_soulbound_nft(
        recipient=recipient,
        nft_type=args.type,
        name=args.name,
        symbol=args.symbol,
        uri=args.uri,
    )
    print(json.dumps(result, indent=2))


def cmd_dao_info(args):
    """Show DAO realm information."""
    tk = create_toolkit(keypair_path=args.keypair, network=args.network, realm=args.realm)
    print("=== Realm Info ===")
    info = tk.dao.get_realm_info()
    for k, v in info.items():
        print(f"  {k}: {v}")

    print("\n=== Token Owner Records ===")
    records = tk.dao.get_token_owner_records()
    if records:
        for r in records:
            print(f"  Owner: {r['governing_token_owner']}, Deposit: {r.get('governing_token_deposit_amount', '?')}")
    else:
        print("  (none found)")

    print("\n=== Proposals ===")
    proposals = tk.dao.get_proposals()
    if proposals:
        for p in proposals:
            print(f"  [{p['state']}] {p.get('name', '(unnamed)')} — {p['pubkey'][:16]}...")
    else:
        print("  (none found)")


def cmd_history(args):
    """Show recent transactions."""
    tk = create_toolkit(keypair_path=args.keypair, network=args.network)
    txs = tk.wallet.get_recent_transactions(limit=args.limit)
    if not txs:
        print("No recent transactions.")
        return
    for tx in txs:
        err = " ❌" if tx["err"] else " ✅"
        ts = tx["block_time"] or "?"
        print(f"  {tx['signature'][:32]}...  slot={tx['slot']}  time={ts}{err}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="ResonantOS Solana Toolkit")
    parser.add_argument("--keypair", default="~/.config/solana/id.json", help="Path to keypair file")
    parser.add_argument("--network", default="devnet", help="Solana network")

    sub = parser.add_subparsers(dest="command", required=True)

    # balance
    sub.add_parser("balance", help="Show SOL balance")

    # airdrop
    p = sub.add_parser("airdrop", help="Request SOL airdrop")
    p.add_argument("amount", type=float, default=1.0, nargs="?", help="Amount in SOL")

    # create-token
    p = sub.add_parser("create-token", help="Create a new token mint")
    p.add_argument("--type", choices=["spl", "token2022"], default="spl", help="Token program type")
    p.add_argument("--decimals", type=int, default=6, help="Decimal places")

    # mint
    p = sub.add_parser("mint", help="Mint tokens")
    p.add_argument("--mint", required=True, help="Mint pubkey")
    p.add_argument("--to", required=True, help="Destination owner pubkey")
    p.add_argument("--amount", type=int, required=True, help="Raw token amount")
    p.add_argument("--token2022", action="store_true", help="Use Token-2022 program")

    # tokens
    p = sub.add_parser("tokens", help="Show all token balances")
    p.add_argument("--owner", help="Owner pubkey (default: own wallet)")

    # mint-nft
    p = sub.add_parser("mint-nft", help="Mint a soulbound NFT")
    p.add_argument("--to", help="Recipient pubkey (default: own wallet)")
    p.add_argument("--type", default="identity", choices=["identity", "alpha_tester"], help="NFT type")
    p.add_argument("--name", help="Override NFT name")
    p.add_argument("--symbol", help="Override NFT symbol")
    p.add_argument("--uri", help="Override metadata URI")

    # dao-info
    p = sub.add_parser("dao-info", help="Show DAO realm info")
    p.add_argument("--realm", default="42sRg1Spzu3YxwXTduDFLWPtb4JJQhmMmDMbPPmnvoTY", help="Realm pubkey")

    # history
    p = sub.add_parser("history", help="Show recent transactions")
    p.add_argument("--limit", type=int, default=10, help="Max transactions")

    args = parser.parse_args()
    cmd_map = {
        "balance": cmd_balance,
        "airdrop": cmd_airdrop,
        "create-token": cmd_create_token,
        "mint": cmd_mint,
        "tokens": cmd_tokens,
        "mint-nft": cmd_mint_nft,
        "dao-info": cmd_dao_info,
        "history": cmd_history,
    }
    try:
        cmd_map[args.command](args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
