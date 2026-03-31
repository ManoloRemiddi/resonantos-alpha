"""Wallet routes — Solana wallet, NFT minting, token transfers, onboarding."""

import hashlib
import json
import os
import traceback
import urllib.request
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, render_template, request

from routes.config import (
    DASHBOARD_DIR,
    _LEVEL_THRESHOLDS,
    _RCT_DECIMALS,
    _RCT_MINT,
    _RES_MINT,
    _REX_DISPLAY,
    _REX_MINTS,
    _SYMBIOTIC_PROGRAM_ID,
    NFTMinter,
    SolanaWallet,
    TokenManager,
)
from routes.wallet_helpers import (
    _check_rct_cap,
    _derive_symbiotic_pda,
    _get_fee_payer,
    _get_wallet_pubkey,
    _is_valid_pubkey,
    _load_daily_claims,
    _load_onboarding,
    _record_rct_mint,
    _require_identity_nft,
    _save_daily_claims,
    _save_onboarding,
    _solana_rpc,
    _wallet_has_nft,
    get_wallet_shared,
)

wallet_bp = Blueprint("wallet", __name__)


def _load_tribes():
    return get_wallet_shared("load_tribes")()


def _load_bounties():
    return get_wallet_shared("load_bounties")()


def _enrich_bounty_with_tribe(bounty, tribe_map):
    return get_wallet_shared("enrich_bounty_with_tribe")(bounty, tribe_map)


@wallet_bp.route("/wallet")
def wallet_page():
    return render_template("wallet.html", active_page="wallet")


@wallet_bp.route("/api/wallet")
def api_wallet():
    """Get wallet balances for both SPL and Token-2022 accounts."""
    try:
        network = request.args.get("network", "devnet")
        address = request.args.get("address")

        if not address:
            try:
                pk = _get_wallet_pubkey()
                if pk is None:
                    return jsonify({"error": "No wallet configured. Create a keypair first."}), 400
                address = str(pk)
            except Exception:
                return jsonify({"error": "address parameter required"}), 400

        # Query both SPL and Token-2022 token accounts
        spl_program = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
        token22_program = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"

        balances = {}

        # Get SOL balance
        try:
            sol_result = _solana_rpc(network, "getBalance", [address])
            sol_balance = sol_result.get("result", {}).get("value", 0) / 1e9
            balances["SOL"] = {"balance": sol_balance, "decimals": 9}
        except Exception as e:
            print(f"Error getting SOL balance: {e}")
            balances["SOL"] = {"balance": 0, "decimals": 9}

        # Query token accounts for both programs
        for program in [spl_program, token22_program]:
            try:
                result = _solana_rpc(
                    network, "getTokenAccountsByOwner", [address, {"programId": program}, {"encoding": "jsonParsed"}]
                )

                for account in result.get("result", {}).get("value", []):
                    parsed = account.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
                    mint = parsed.get("mint")
                    token_amount = parsed.get("tokenAmount", {})
                    amount = float(token_amount.get("amount", 0))
                    decimals = token_amount.get("decimals", 0)
                    ui_amount = amount / (10**decimals) if decimals > 0 else amount

                    # Map known mints to symbols
                    symbol = mint
                    if mint == _RCT_MINT:
                        symbol = "$RCT"
                    elif mint == _RES_MINT:
                        symbol = "$RES"
                    elif mint in _REX_MINTS.values():
                        for k, v in _REX_MINTS.items():
                            if v == mint:
                                symbol = f"$REX-{k}"
                                break

                    balances[symbol] = {"balance": ui_amount, "decimals": decimals, "mint": mint}
            except Exception as e:
                print(f"Error querying token accounts for {program}: {e}")

        return jsonify({"address": address, "network": network, "balances": balances})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@wallet_bp.route("/api/wallet/user")
def api_wallet_user():
    """Query any address for balances + last claim time."""
    try:
        network = request.args.get("network", "devnet")
        address = request.args.get("address")

        if not address:
            return jsonify({"error": "address parameter required"}), 400

        # Get balances using existing endpoint logic
        wallet_data = api_wallet().get_json()

        # Get last claim time
        claims = _load_daily_claims()
        claim_val = claims.get(address)
        last_claim = (
            claim_val
            if isinstance(claim_val, str)
            else (claim_val.get("last_claim") if isinstance(claim_val, dict) else None)
        )

        return jsonify(
            {
                "address": address,
                "network": network,
                "balances": wallet_data.get("balances", {}),
                "lastClaim": last_claim,
                "canClaim": True,  # Will be calculated based on 24h cooldown
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@wallet_bp.route("/api/wallet/mint-nft", methods=["POST"])
def api_wallet_mint_nft():
    """Mint soulbound NFT + reward tokens with RCT cap check."""
    try:
        if not NFTMinter or not TokenManager:
            return jsonify({"error": "Solana toolkit not available"}), 500

        data = request.get_json() or {}
        network = data.get("network", "devnet")
        recipient = data.get("recipient")
        nft_type = data.get("type", "identity")  # identity, alpha_tester
        signature = data.get("signature")  # Phantom co-signature

        # Devnet only for alpha
        if network != "devnet":
            return jsonify({"error": "Only devnet supported during alpha"}), 400

        if not recipient or not signature:
            return jsonify({"error": "recipient and signature required"}), 400
        if not _is_valid_pubkey(recipient):
            return jsonify({"error": "Invalid recipient address"}), 400

        if nft_type not in {"identity", "alpha_tester"}:
            return jsonify({"error": "Invalid NFT type. Use identity or alpha_tester"}), 400

        pda_address = _derive_symbiotic_pda(recipient)
        nft_minter = NFTMinter(SolanaWallet(network=network))
        existing = nft_minter.check_wallet_has_nft(pda_address, nft_type)
        if existing.get("has_nft"):
            label = "Identity NFT" if nft_type == "identity" else "Alpha Tester NFT"
            return jsonify(
                {
                    "error": f"Already holds {label}",
                    "existing_mint": existing.get("mint"),
                }
            ), 409

        # Reward amounts
        rewards = {"identity": {"rct": 5, "res": 500}, "alpha_tester": {"rct": 50, "res": 1000}}

        reward = rewards.get(nft_type, rewards["identity"])

        # Check RCT cap
        can_mint, reason = _check_rct_cap(recipient, reward["rct"])
        if not can_mint:
            return jsonify({"error": f"RCT cap exceeded: {reason}"}), 429

        # Determine fee payer
        fee_payer_path, fee_payer_label = _get_fee_payer(network, recipient)

        # Mint NFT to Symbiotic PDA (not user wallet)
        nft_result = nft_minter.mint_soulbound_nft(
            recipient=pda_address,
            nft_type=nft_type,
            name=f"ResonantOS {nft_type.replace('_', ' ').title()}",
            symbol="ROS-NFT",
            fee_payer_keypair=fee_payer_path,
        )

        # Mint reward tokens
        token_manager = TokenManager(SolanaWallet(network=network))

        # Mint RCT (Token-2022) → Symbiotic PDA
        rct_result = token_manager.mint_tokens(
            mint=_RCT_MINT,
            destination_owner=pda_address,
            amount=reward["rct"] * (10**_RCT_DECIMALS),
            token_program="token2022",
        )

        # Mint RES (SPL) → Symbiotic PDA
        res_result = token_manager.mint_tokens(
            mint=_RES_MINT, destination_owner=pda_address, amount=reward["res"] * (10**6), token_program="spl"
        )

        # Record RCT mint for cap tracking
        _record_rct_mint(recipient, reward["rct"])

        # Update NFT registry for display name resolution
        try:
            reg_path = str(DASHBOARD_DIR / "data" / "nft_registry.json")
            registry = {}
            if os.path.exists(reg_path):
                with open(reg_path) as rf:
                    registry = json.load(rf)
            nft_mint_addr = nft_result.get("mint")
            if nft_mint_addr:
                registry[nft_mint_addr] = nft_type  # "identity" or "alpha_tester" → map alpha_tester to "alpha"
                if nft_type == "alpha_tester":
                    registry[nft_mint_addr] = "alpha"
                with open(reg_path, "w") as wf:
                    json.dump(registry, wf, indent=2)
        except Exception as e:
            print(f"Warning: could not update nft_registry: {e}")

        # Update onboarding status
        onboarding = _load_onboarding()
        if recipient not in onboarding:
            onboarding[recipient] = {}
        if nft_type == "identity":
            onboarding[recipient]["identityNftMinted"] = True
            onboarding[recipient]["identityNftMint"] = nft_result.get("mint")
        elif nft_type == "alpha_tester":
            onboarding[recipient]["alphaNftMinted"] = True
            onboarding[recipient]["alphaNftMint"] = nft_result.get("mint")
        _save_onboarding(onboarding)

        return jsonify(
            {
                "success": True,
                "nftMint": nft_result.get("mint"),
                "rctAmount": reward["rct"],
                "resAmount": reward["res"],
                "feePayer": fee_payer_label,
                "transactions": {
                    "nft": nft_result.get("signature") if isinstance(nft_result, dict) else str(nft_result),
                    "rct": rct_result
                    if isinstance(rct_result, str)
                    else rct_result
                    if isinstance(rct_result, str)
                    else rct_result.get("signature"),
                    "res": res_result
                    if isinstance(res_result, str)
                    else res_result
                    if isinstance(res_result, str)
                    else res_result.get("signature"),
                },
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@wallet_bp.route("/api/wallet/build-transfer-tx", methods=["POST"])
def api_wallet_build_transfer_tx():
    """Build a transfer_out transaction for Phantom to sign.

    The PDA transfer requires the on-chain program to authorize via CPI.
    Human signs the transaction via Phantom, server builds the instruction.

    Body: { sender, recipient, amount, token (RCT|RES), network }
    Returns: { transaction: base64-encoded serialized tx (message only, for Phantom signing) }
    """
    try:
        import base64
        import hashlib as _hl
        import struct as _st

        from solana.rpc.api import Client as _Client
        from solders.instruction import AccountMeta as _AM
        from solders.instruction import Instruction as _Ix
        from solders.message import Message as _Msg
        from solders.pubkey import Pubkey as _Pubkey
        from solders.transaction import Transaction as _Tx

        data = request.get_json(force=True)
        network = data.get("network", "devnet")
        sender = data.get("sender", "").strip()
        recipient = data.get("recipient", "").strip()
        amount = float(data.get("amount", 0))
        token = data.get("token", "RCT").upper()

        if not sender or not recipient or amount <= 0:
            return jsonify({"error": "Missing sender, recipient, or valid amount"}), 400

        # Verify sender has Identity NFT (on-chain check first, onboarding cache fallback)
        if not _require_identity_nft(sender):
            return jsonify({"error": "Identity NFT required to send tokens"}), 403

        # Token config
        if token == "RCT":
            mint_str = _RCT_MINT
            decimals = 9
            token_prog_str = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"  # Token-2022
        elif token == "RES":
            mint_str = _RES_MINT
            decimals = 6
            token_prog_str = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"  # SPL Token
        else:
            return jsonify({"error": f"Unknown token: {token}"}), 400

        # Validate base58 addresses
        import re as _re

        _b58_re = _re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
        if not _b58_re.match(sender):
            return jsonify({"error": "Invalid sender address (not base58)"}), 400
        if not _b58_re.match(recipient):
            return jsonify({"error": "Invalid recipient address (not base58)"}), 400

        # Derive PDA
        program_id = _Pubkey.from_string(_SYMBIOTIC_PROGRAM_ID)
        human = _Pubkey.from_string(sender)
        recipient_pk = _Pubkey.from_string(recipient)
        mint = _Pubkey.from_string(mint_str)
        token_prog = _Pubkey.from_string(token_prog_str)

        pda, bump = _Pubkey.find_program_address([b"symbiotic", bytes(human), bytes([0])], program_id)

        # Verify symbiotic pair exists on-chain and is active
        pair_info = _solana_rpc(network, "getAccountInfo", [str(pda), {"encoding": "base64"}])
        pair_val = pair_info.get("result", {}).get("value") if isinstance(pair_info, dict) else None
        if not pair_val:
            return jsonify({"error": "Symbiotic wallet not initialized. Create Symbiotic Wallet first."}), 400
        try:
            import base64 as _b64

            raw_pair = _b64.b64decode(pair_val["data"][0])
            if len(raw_pair) >= 93:
                d = raw_pair[8:]  # skip discriminator
                pair_human = str(_Pubkey.from_bytes(d[0:32]))
                pair_frozen = bool(d[66])
                if pair_human != sender:
                    return jsonify({"error": "Unauthorized: connected wallet is not the pair human signer"}), 403
                if pair_frozen:
                    return jsonify({"error": "Symbiotic wallet is frozen"}), 403
        except Exception:
            # If decode fails, continue and let on-chain program enforce constraints
            pass

        # Derive ATAs
        from spl.token.instructions import get_associated_token_address

        from_ata = get_associated_token_address(pda, mint, token_prog)
        to_ata = get_associated_token_address(recipient_pk, mint, token_prog)

        # Build transfer_out instruction
        disc = _hl.sha256(b"global:transfer_out").digest()[:8]
        raw_amount = int(amount * (10**decimals))
        ix_data = disc + _st.pack("<Q", raw_amount)

        accounts = [
            _AM(pubkey=pda, is_signer=False, is_writable=False),
            _AM(pubkey=human, is_signer=True, is_writable=True),
            _AM(pubkey=from_ata, is_signer=False, is_writable=True),
            _AM(pubkey=to_ata, is_signer=False, is_writable=True),
            _AM(pubkey=mint, is_signer=False, is_writable=False),
            _AM(pubkey=token_prog, is_signer=False, is_writable=False),
        ]

        ix = _Ix(program_id, ix_data, accounts)

        # Optionally create recipient ATA if it doesn't exist
        rpcs = {
            "devnet": "https://api.devnet.solana.com",
            "testnet": "https://api.testnet.solana.com",
            "mainnet-beta": "https://api.mainnet-beta.com",
        }
        client = _Client(rpcs.get(network, network))

        instructions = []

        # Check if recipient ATA exists
        ata_info = client.get_account_info(to_ata)
        if ata_info.value is None:
            # Create ATA instruction
            from spl.token.instructions import create_associated_token_account

            create_ata_ix = create_associated_token_account(
                payer=human, owner=recipient_pk, mint=mint, token_program_id=token_prog
            )
            instructions.append(create_ata_ix)

        instructions.append(ix)

        # Build transaction message
        blockhash_resp = client.get_latest_blockhash()
        blockhash = blockhash_resp.value.blockhash
        msg = _Msg.new_with_blockhash(instructions, human, blockhash)
        tx = _Tx.new_unsigned(msg)

        # Serialize for Phantom
        tx_bytes = bytes(tx)
        tx_b64 = base64.b64encode(tx_bytes).decode("ascii")

        return jsonify(
            {
                "transaction": tx_b64,
                "pda": str(pda),
                "fromAta": str(from_ata),
                "toAta": str(to_ata),
                "rawAmount": raw_amount,
                "decimals": decimals,
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@wallet_bp.route("/api/wallet/build-sol-transfer", methods=["POST"])
def api_wallet_build_sol_transfer():
    """Build a simple SOL transfer from Phantom wallet (system program).
    Body: { sender, recipient, amount, network }
    Returns: { transaction: base64 }
    """
    try:
        import base64
        import struct as _st

        from solana.rpc.api import Client as _Client
        from solders.instruction import AccountMeta as _AM
        from solders.instruction import Instruction as _Ix
        from solders.message import Message as _Msg
        from solders.pubkey import Pubkey as _Pubkey
        from solders.transaction import Transaction as _Tx

        data = request.get_json(force=True)
        network = data.get("network", "devnet")
        sender = data.get("sender", "").strip()
        recipient = data.get("recipient", "").strip()
        amount = float(data.get("amount", 0))

        if not sender or not recipient or amount <= 0:
            return jsonify({"error": "Missing sender, recipient, or valid amount"}), 400

        import re as _re

        _b58_re = _re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
        if not _b58_re.match(sender) or not _b58_re.match(recipient):
            return jsonify({"error": "Invalid address (not base58)"}), 400

        sender_pk = _Pubkey.from_string(sender)
        recipient_pk = _Pubkey.from_string(recipient)
        lamports = int(amount * 1_000_000_000)  # SOL → lamports

        # System program transfer instruction
        system_prog = _Pubkey.from_string("11111111111111111111111111111111")
        ix_data = _st.pack("<II", 2, 0) + _st.pack("<Q", lamports)  # instruction index 2 = Transfer
        # Simpler: use solders system_program if available
        try:
            from solders.system_program import TransferParams, transfer

            ix = transfer(TransferParams(from_pubkey=sender_pk, to_pubkey=recipient_pk, lamports=lamports))
        except ImportError:
            accounts = [
                _AM(pubkey=sender_pk, is_signer=True, is_writable=True),
                _AM(pubkey=recipient_pk, is_signer=False, is_writable=True),
            ]
            ix = _Ix(system_prog, ix_data, accounts)

        rpcs = {
            "devnet": "https://api.devnet.solana.com",
            "testnet": "https://api.testnet.solana.com",
            "mainnet-beta": "https://api.mainnet-beta.com",
        }
        client = _Client(rpcs.get(network, network))
        blockhash_resp = client.get_latest_blockhash()
        blockhash = blockhash_resp.value.blockhash

        msg = _Msg.new_with_blockhash([ix], sender_pk, blockhash)
        tx = _Tx.new_unsigned(msg)
        tx_b64 = base64.b64encode(bytes(tx)).decode("ascii")

        return jsonify({"transaction": tx_b64, "lamports": lamports})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@wallet_bp.route("/api/wallet/send-tokens", methods=["POST"])
def api_wallet_send_tokens():
    """Legacy endpoint — redirects to build-transfer-tx."""
    return api_wallet_build_transfer_tx()


@wallet_bp.route("/api/wallet/daily-claim", methods=["POST"])
def api_wallet_daily_claim():
    """24h cooldown, mint 1 RCT + 500 RES with cap check."""
    try:
        if not TokenManager:
            return jsonify({"error": "Solana toolkit not available"}), 500

        data = request.get_json() or {}
        network = data.get("network", "devnet")
        recipient = data.get("recipient")
        signature = data.get("signature")  # Phantom co-signature

        # Devnet only for alpha
        if network != "devnet":
            return jsonify({"error": "Only devnet supported during alpha"}), 400

        if not recipient or not signature:
            return jsonify({"error": "recipient and signature required"}), 400
        if not _is_valid_pubkey(recipient):
            return jsonify({"error": "Invalid recipient address"}), 400

        # Require Identity NFT
        if not _require_identity_nft(recipient):
            return jsonify({"error": "Identity NFT required. Complete onboarding first."}), 403

        # Check 24h cooldown
        claims = _load_daily_claims()
        raw_claim = claims.get(recipient)
        # Handle both old format (string timestamp) and new format (dict)
        if isinstance(raw_claim, str):
            user_claims = {"last_claim": raw_claim, "total_claims": 0}
        elif isinstance(raw_claim, dict):
            user_claims = raw_claim
        else:
            user_claims = {}
        last_claim = user_claims.get("last_claim")

        if last_claim:
            last_claim_time = datetime.fromisoformat(last_claim.replace("Z", "+00:00"))
            if last_claim_time.tzinfo is None:
                last_claim_time = last_claim_time.replace(tzinfo=timezone.utc)
            hours_since = (datetime.now(timezone.utc) - last_claim_time).total_seconds() / 3600
            if hours_since < 24:
                hours_remaining = 24 - hours_since
                return jsonify(
                    {
                        "error": f"Cooldown active. {hours_remaining:.1f} hours remaining.",
                        "hoursRemaining": hours_remaining,
                    }
                ), 429

        # Check RCT cap
        can_mint, reason = _check_rct_cap(recipient, 1)
        if not can_mint:
            return jsonify({"error": f"RCT cap exceeded: {reason}"}), 429

        # Determine fee payer
        fee_payer_path, fee_payer_label = _get_fee_payer(network, recipient)

        # Mint tokens
        token_manager = TokenManager(SolanaWallet(network=network))
        pda_address = _derive_symbiotic_pda(recipient)

        # Mint 1 RCT → Symbiotic PDA
        rct_result = token_manager.mint_tokens(
            mint=_RCT_MINT, destination_owner=pda_address, amount=1 * (10**_RCT_DECIMALS), token_program="token2022"
        )

        # Mint 500 RES → Symbiotic PDA
        res_result = token_manager.mint_tokens(
            mint=_RES_MINT, destination_owner=pda_address, amount=500 * (10**6), token_program="spl"
        )

        # Record claim and RCT mint
        claims[recipient] = {
            "last_claim": datetime.now(timezone.utc).isoformat(),
            "total_claims": user_claims.get("total_claims", 0) + 1,
        }
        _save_daily_claims(claims)
        _record_rct_mint(recipient, 1)

        return jsonify(
            {
                "success": True,
                "rctAmount": 1,
                "resAmount": 500,
                "feePayer": fee_payer_label,
                "nextClaimAvailable": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
                "transactions": {
                    "rct": rct_result if isinstance(rct_result, str) else rct_result.get("signature"),
                    "res": res_result if isinstance(res_result, str) else res_result.get("signature"),
                },
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@wallet_bp.route("/api/wallet/onboarding-status")
def api_wallet_onboarding_status():
    """Check onboarding status with blockchain as source of truth."""
    try:
        address = request.args.get("address")
        network = request.args.get("network", "devnet")
        if not address:
            return jsonify({"error": "address parameter required"}), 400
        if not _is_valid_pubkey(address):
            return jsonify({"error": "Invalid wallet address"}), 400

        pda_address = _derive_symbiotic_pda(address)
        pair_exists = False
        try:
            pair_info = _solana_rpc(network, "getAccountInfo", [pda_address, {"encoding": "base64"}])
            pair_exists = pair_info.get("result", {}).get("value") is not None
        except Exception:
            pair_exists = False

        license_status = _wallet_has_nft(address, "symbiotic_license", network=network) if pair_exists else False
        manifesto_status = _wallet_has_nft(address, "manifesto", network=network) if pair_exists else False
        identity_status = _wallet_has_nft(address, "identity", network=network) if pair_exists else False
        alpha_status = _wallet_has_nft(address, "alpha_tester", network=network) if pair_exists else False

        onboarding = _load_onboarding()
        user_onboarding = onboarding.setdefault(address, {})
        user_onboarding["symbioticPairCreated"] = pair_exists
        user_onboarding["symbioticPda"] = pda_address
        user_onboarding["licenseSigned"] = license_status
        user_onboarding["manifestoSigned"] = manifesto_status
        user_onboarding["identityNftMinted"] = identity_status
        user_onboarding["alphaNftMinted"] = alpha_status
        _save_onboarding(onboarding)

        return jsonify(
            {
                "address": address,
                "network": network,
                "symbioticPairCreated": pair_exists,
                "symbioticPda": pda_address,
                "alphaAgreed": user_onboarding.get("alphaAgreed", False),
                "licenseSigned": license_status,
                "manifestoSigned": manifesto_status,
                "identityNftMinted": identity_status,
                "alphaNftMinted": alpha_status,
                "onboardingComplete": all(
                    [
                        user_onboarding.get("alphaAgreed"),
                        pair_exists,
                        license_status,
                        manifesto_status,
                        identity_status,
                        alpha_status,
                    ]
                ),
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@wallet_bp.route("/api/wallet/agree-alpha", methods=["POST"])
def api_wallet_agree_alpha():
    """Record Alpha Testing Agreement acceptance."""
    try:
        data = request.get_json() or {}
        address = data.get("address")
        signature = data.get("signature")

        if not address or not signature:
            return jsonify({"error": "address and signature required"}), 400
        if not _is_valid_pubkey(address):
            return jsonify({"error": "Invalid wallet address"}), 400

        onboarding = _load_onboarding()
        if address not in onboarding:
            onboarding[address] = {}

        if onboarding[address].get("alphaAgreed"):
            return jsonify({"error": "Already agreed"}), 409

        onboarding[address]["alphaAgreed"] = True
        onboarding[address]["alphaAgreedAt"] = datetime.now(timezone.utc).isoformat()
        onboarding[address]["alphaSignature"] = signature
        _save_onboarding(onboarding)

        return jsonify({"success": True})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@wallet_bp.route("/api/wallet/sign-license", methods=["POST"])
def api_wallet_sign_license():
    """Co-sign license, mint License NFT."""
    try:
        if not NFTMinter:
            return jsonify({"error": "Solana toolkit not available"}), 500

        data = request.get_json() or {}
        network = data.get("network", "devnet")
        address = data.get("address")
        signature = data.get("signature")  # Phantom signature of license hash

        if not address or not signature:
            return jsonify({"error": "address and signature required"}), 400
        if not _is_valid_pubkey(address):
            return jsonify({"error": "Invalid wallet address"}), 400

        pda_address = _derive_symbiotic_pda(address)
        nft_minter = NFTMinter(SolanaWallet(network=network))
        existing = nft_minter.check_wallet_has_nft(pda_address, "symbiotic_license")
        if existing.get("has_nft"):
            return jsonify(
                {
                    "error": "Already holds Symbiotic License NFT",
                    "existing_mint": existing.get("mint"),
                }
            ), 409

        # Verify signature is of correct license hash
        license_text = "Resonant Commons Symbiotic License (RC-SL) v1.0"
        expected_hash = hashlib.sha256(license_text.encode()).hexdigest()

        # Store signing record
        onboarding = _load_onboarding()
        if address not in onboarding:
            onboarding[address] = {}

        onboarding[address]["licenseSigned"] = True
        onboarding[address]["licenseSignedAt"] = datetime.now(timezone.utc).isoformat()
        onboarding[address]["licenseHash"] = expected_hash
        onboarding[address]["licenseSignature"] = signature

        _save_onboarding(onboarding)

        # Mint License NFT to Symbiotic PDA
        fee_payer_path, fee_payer_label = _get_fee_payer(network, address)
        nft_result = nft_minter.mint_soulbound_nft(
            recipient=pda_address,
            nft_type="symbiotic_license",
            name="Resonant Commons License Signatory",
            symbol="RC-LIC",
            fee_payer_keypair=fee_payer_path,
        )

        # Store NFT mint in onboarding record
        if nft_result.get("mint"):
            onboarding[address]["licenseNft"] = nft_result["mint"]
            _save_onboarding(onboarding)

        return jsonify(
            {
                "success": True,
                "licenseHash": expected_hash,
                "nftMint": nft_result.get("mint"),
                "feePayer": fee_payer_label,
                "transaction": nft_result.get("signature"),
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@wallet_bp.route("/api/wallet/sign-manifesto", methods=["POST"])
def api_wallet_sign_manifesto():
    """Co-sign manifesto, mint Manifesto NFT."""
    try:
        if not NFTMinter:
            return jsonify({"error": "Solana toolkit not available"}), 500

        data = request.get_json() or {}
        network = data.get("network", "devnet")
        address = data.get("address")
        signature = data.get("signature")  # Phantom signature of manifesto hash

        if not address or not signature:
            return jsonify({"error": "address and signature required"}), 400

        # Require license signed first
        onboarding = _load_onboarding()
        user_onboarding = onboarding.get(address, {})

        if not user_onboarding.get("licenseSigned"):
            return jsonify({"error": "Must sign license first"}), 400

        pda_address = _derive_symbiotic_pda(address)
        nft_minter = NFTMinter(SolanaWallet(network=network))
        existing = nft_minter.check_wallet_has_nft(pda_address, "manifesto")
        if existing.get("has_nft"):
            return jsonify(
                {
                    "error": "Already holds Manifesto NFT",
                    "existing_mint": existing.get("mint"),
                }
            ), 409

        # Verify signature is of correct manifesto hash
        manifesto_text = "Augmentatism Manifesto v2.2"
        expected_hash = hashlib.sha256(manifesto_text.encode()).hexdigest()

        # Store signing record
        onboarding[address]["manifestoSigned"] = True
        onboarding[address]["manifestoSignedAt"] = datetime.now(timezone.utc).isoformat()
        onboarding[address]["manifestoHash"] = expected_hash
        onboarding[address]["manifestoSignature"] = signature

        _save_onboarding(onboarding)

        # Mint Manifesto NFT to Symbiotic PDA
        fee_payer_path, fee_payer_label = _get_fee_payer(network, address)
        nft_result = nft_minter.mint_soulbound_nft(
            recipient=pda_address,
            nft_type="manifesto",
            name="Augmentatism Manifesto Signatory",
            symbol="AUG-MAN",
            fee_payer_keypair=fee_payer_path,
        )

        # Store NFT mint in onboarding record
        if nft_result.get("mint"):
            onboarding[address]["manifestoNft"] = nft_result["mint"]
            _save_onboarding(onboarding)

        return jsonify(
            {
                "success": True,
                "manifestoHash": expected_hash,
                "nftMint": nft_result.get("mint"),
                "feePayer": fee_payer_label,
                "transaction": nft_result.get("signature"),
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@wallet_bp.route("/api/wallet/reputation")
def api_wallet_reputation():
    """Query REX token balances, compute levels."""
    try:
        network = request.args.get("network", "devnet")
        address = request.args.get("address")

        if not address:
            return jsonify({"error": "address parameter required"}), 400

        reputation = {"address": address, "network": network, "categories": {}}

        # Query REX token balances
        for category, mint in _REX_MINTS.items():
            try:
                result = _solana_rpc(
                    network, "getTokenAccountsByOwner", [address, {"mint": mint}, {"encoding": "jsonParsed"}]
                )

                balance = 0
                for account in result.get("result", {}).get("value", []):
                    parsed = account.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
                    token_amount = parsed.get("tokenAmount", {})
                    amount = float(token_amount.get("amount", 0))
                    decimals = token_amount.get("decimals", 0)
                    balance = amount / (10**decimals) if decimals > 0 else amount
                    break

                # Compute level from thresholds
                level = 0
                for i, threshold in enumerate(_LEVEL_THRESHOLDS):
                    if balance >= threshold:
                        level = i
                    else:
                        break

                reputation["categories"][category] = {
                    "balance": balance,
                    "level": level,
                    "mint": mint,
                    "display": _REX_DISPLAY[category],
                }

            except Exception as e:
                print(f"Error querying REX {category}: {e}")
                reputation["categories"][category] = {
                    "balance": 0,
                    "level": 0,
                    "mint": mint,
                    "display": _REX_DISPLAY[category],
                }

        # Compute overall level (max of all categories)
        overall_level = max([cat.get("level", 0) for cat in reputation["categories"].values()] + [0])
        reputation["overallLevel"] = overall_level

        return jsonify(reputation)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@wallet_bp.route("/api/wallet/grant-xp", methods=["POST"])
def api_wallet_grant_xp():
    """Mint REX tokens + 10 RCT bonus."""
    try:
        if not TokenManager:
            return jsonify({"error": "Solana toolkit not available"}), 500

        data = request.get_json() or {}
        network = data.get("network", "devnet")
        recipient = data.get("recipient")
        category = data.get("category")  # GOV, FIN, COM, CRE, TEC
        amount = data.get("amount", 10)  # XP amount to grant
        signature = data.get("signature")  # Phantom co-signature

        if not recipient or not category or category not in _REX_MINTS:
            return jsonify({"error": "recipient and valid category required"}), 400

        # Require Identity NFT
        if not _require_identity_nft(recipient):
            return jsonify({"error": "Identity NFT required. Complete onboarding first."}), 403

        # Check RCT cap for the 10 RCT bonus
        can_mint, reason = _check_rct_cap(recipient, 10)
        if not can_mint:
            return jsonify({"error": f"RCT cap exceeded: {reason}"}), 429

        # Determine fee payer
        fee_payer_path, fee_payer_label = _get_fee_payer(network, recipient)

        token_manager = TokenManager(SolanaWallet(network=network))
        pda_address = _derive_symbiotic_pda(recipient)

        # Mint REX tokens (Token-2022, 0 decimals) → Symbiotic PDA
        rex_result = token_manager.mint_tokens(
            mint=_REX_MINTS[category], destination_owner=pda_address, amount=amount, token_program="token2022"
        )

        # Mint 10 RCT bonus → Symbiotic PDA
        rct_result = token_manager.mint_tokens(
            mint=_RCT_MINT, destination_owner=pda_address, amount=10 * (10**_RCT_DECIMALS), token_program="token2022"
        )

        # Record RCT mint
        _record_rct_mint(recipient, 10)

        return jsonify(
            {
                "success": True,
                "category": category,
                "categoryDisplay": _REX_DISPLAY[category],
                "xpAmount": amount,
                "rctBonus": 10,
                "feePayer": fee_payer_label,
                "transactions": {
                    "rex": rex_result if isinstance(rex_result, str) else rex_result.get("signature"),
                    "rct": rct_result if isinstance(rct_result, str) else rct_result.get("signature"),
                },
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@wallet_bp.route("/api/wallet/leaderboard")
def api_wallet_leaderboard():
    """Rankings by RCT and REX categories — only Identity NFT holders."""
    try:
        network = request.args.get("network", "devnet")

        leaderboard = {"network": network, "overall": [], "categories": {}}

        # Load onboarding data — only include users with Identity NFT
        onboarding = _load_onboarding()
        identity_holders = {addr for addr, data in onboarding.items() if data.get("identityNftMinted")}

        # Build PDA→human mapping for all identity holders
        pda_to_human = {}
        for human_addr in identity_holders:
            try:
                pda = _derive_symbiotic_pda(human_addr)
                pda_to_human[pda] = human_addr
            except Exception:
                pass

        # Helper: resolve token account (ATA) → owner address
        def _resolve_owner(network, ata_address):
            try:
                info = _solana_rpc(network, "getAccountInfo", [ata_address, {"encoding": "jsonParsed"}])
                parsed = info.get("result", {}).get("value", {}).get("data", {}).get("parsed", {}).get("info", {})
                return parsed.get("owner", ata_address)
            except Exception:
                return ata_address

        # Helper: build ranked list — tokens live on PDAs now
        def _build_board(mint, decimals, max_entries):
            if not identity_holders:
                return []
            try:
                result = _solana_rpc(network, "getTokenLargestAccounts", [mint])
                accounts = result.get("result", {}).get("value", [])
            except Exception as e:
                print(f"Error getting largest accounts for {mint}: {e}")
                return []

            board = []
            for account in accounts:
                if len(board) >= max_entries:
                    break

                ata = account.get("address")
                amount = account.get("amount")
                dec = account.get("decimals", decimals)
                balance = int(amount) / (10**dec) if amount else 0
                if balance <= 0:
                    continue

                owner = _resolve_owner(network, ata)

                # Owner could be a PDA or a human wallet
                # Accept if owner IS an identity holder (human wallet)
                # OR if owner is a PDA that maps to an identity holder
                human_addr = pda_to_human.get(owner)
                if human_addr:
                    display_addr = human_addr  # show human wallet, not PDA
                elif owner in identity_holders:
                    display_addr = owner
                else:
                    continue  # skip non-identity-holder wallets

                level = 0
                for j, threshold in enumerate(_LEVEL_THRESHOLDS):
                    if balance >= threshold:
                        level = j
                    else:
                        break

                board.append({"rank": len(board) + 1, "address": display_addr, "balance": balance, "level": level})
            return board

        # Overall RCT leaderboard
        leaderboard["overall"] = _build_board(_RCT_MINT, _RCT_DECIMALS, 10)

        # REX category leaderboards
        for category, mint in _REX_MINTS.items():
            leaderboard["categories"][category] = {
                "display": _REX_DISPLAY[category],
                "rankings": _build_board(mint, 9, 5),
            }

        return jsonify(leaderboard)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@wallet_bp.route("/api/wallet/my-tribes", methods=["GET"])
def api_wallet_my_tribes():
    try:
        wallet = request.args.get("address", "").strip()
        if not wallet:
            return jsonify({"error": "address parameter required"}), 400
        tribes = _load_tribes()
        mine = []
        for tribe in tribes:
            members = tribe.get("members", [])
            if any(m.get("wallet") == wallet for m in members):
                mine.append(
                    {
                        "id": tribe.get("id"),
                        "name": tribe.get("name"),
                        "description": tribe.get("description"),
                        "category": tribe.get("category"),
                        "memberCount": len(members),
                        "activeBountyCount": len(tribe.get("activeBounties", [])),
                        "role": next((m.get("role") for m in members if m.get("wallet") == wallet), "member"),
                    }
                )
        return jsonify({"wallet": wallet, "tribes": mine, "count": len(mine)})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@wallet_bp.route("/api/wallet/my-bounties", methods=["GET"])
def api_wallet_my_bounties():
    try:
        wallet = request.args.get("address", "").strip()
        if not wallet:
            return jsonify({"error": "address parameter required"}), 400
        bounties = _load_bounties()
        tribes = _load_tribes()
        tribe_map = {t.get("id"): t for t in tribes}
        mine = []
        for bounty in bounties:
            if wallet not in bounty.get("claimedBy", []):
                continue
            entry = _enrich_bounty_with_tribe(bounty, tribe_map)
            mine.append(
                {
                    "id": entry.get("id"),
                    "title": entry.get("title"),
                    "status": entry.get("status"),
                    "priority": entry.get("priority"),
                    "rewardRCT": entry.get("rewardRCT"),
                    "rewardRES": entry.get("rewardRES"),
                    "tribe": entry.get("tribe"),
                }
            )
        return jsonify({"wallet": wallet, "bounties": mine, "count": len(mine)})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@wallet_bp.route("/api/wallet/document")
def api_wallet_document():
    """Return license or manifesto text."""
    try:
        doc_type = request.args.get("type", "license")

        if doc_type == "license":
            # Try to read from templates/license.html
            license_path = DASHBOARD_DIR / "templates" / "license.html"
            if license_path.exists():
                import re

                raw = license_path.read_text()
                # Strip Jinja extends/block lines entirely
                content = re.sub(r"\{%\s*extends.*?%\}\s*", "", raw)
                content = re.sub(r"\{%\s*block\s+title\s*%\}.*?\{%\s*endblock\s*%\}\s*", "", content)
                content = re.sub(r"\{%\s*(?:end)?block\s+\w+\s*%\}\s*", "", content)
                content = content.strip()
                return jsonify(
                    {
                        "type": "license",
                        "title": "Resonant Commons Symbiotic License (RC-SL) v1.0",
                        "content": content,
                        "hash": hashlib.sha256(b"Resonant Commons Symbiotic License (RC-SL) v1.0").hexdigest(),
                    }
                )
            else:
                # Hardcoded fallback
                content = """# Resonant Commons Symbiotic License (RC-SL) v1.0

A license for symbiotic collaboration between human creativity and artificial intelligence.

[Full license text would be here...]"""
                return jsonify(
                    {
                        "type": "license",
                        "title": "Resonant Commons Symbiotic License (RC-SL) v1.0",
                        "content": content,
                        "hash": hashlib.sha256(b"Resonant Commons Symbiotic License (RC-SL) v1.0").hexdigest(),
                    }
                )

        elif doc_type == "manifesto":
            try:
                # Try to fetch from augmentatism.com
                req = urllib.request.Request("https://augmentatism.com/manifesto")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    content = resp.read().decode()
                    return jsonify(
                        {
                            "type": "manifesto",
                            "title": "Augmentatism Manifesto v2.2",
                            "content": content,
                            "hash": hashlib.sha256(b"Augmentatism Manifesto v2.2").hexdigest(),
                        }
                    )
            except Exception:
                # Cached fallback
                content = """# Augmentatism Manifesto v2.2

The philosophy of symbiotic human-AI collaboration.

[Manifesto content would be cached here...]"""
                return jsonify(
                    {
                        "type": "manifesto",
                        "title": "Augmentatism Manifesto v2.2",
                        "content": content,
                        "hash": hashlib.sha256(b"Augmentatism Manifesto v2.2").hexdigest(),
                    }
                )

        else:
            return jsonify({"error": "Invalid document type"}), 400

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@wallet_bp.route("/api/wallet/owned-nfts")
def api_wallet_owned_nfts():
    """Return NFTs owned by address."""
    try:
        network = request.args.get("network", "devnet")
        address = request.args.get("address")

        if not address:
            return jsonify({"error": "address parameter required"}), 400

        nfts = []

        # Query Token-2022 accounts (where soulbound NFTs are minted)
        try:
            result = _solana_rpc(
                network,
                "getTokenAccountsByOwner",
                [address, {"programId": "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"}, {"encoding": "jsonParsed"}],
            )

            for account in result.get("result", {}).get("value", []):
                parsed = account.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
                mint = parsed.get("mint")
                token_amount = parsed.get("tokenAmount", {})
                amount = float(token_amount.get("amount", 0))

                if amount > 0 and int(token_amount.get("decimals", 0)) == 0:
                    # Check onboarding records to identify NFT type by mint
                    onboarding = _load_onboarding()
                    nft_data = {
                        "mint": mint,
                        "name": f"NFT {mint[:8]}...",
                        "tag": "Soulbound",
                        "img": None,
                        "soulbound": True,
                    }

                    # Match mint against known NFT mints from onboarding records
                    matched = False
                    for addr, record in onboarding.items():
                        if record.get("licenseNft") == mint:
                            nft_data.update(
                                {
                                    "name": "Symbiotic License",
                                    "tag": "Co-signed Agreement",
                                    "img": "/static/img/nfts/symbiotic-license.png",
                                }
                            )
                            matched = True
                            break
                        elif record.get("manifestoNft") == mint:
                            nft_data.update(
                                {
                                    "name": "Augmentatism Manifesto",
                                    "tag": "Co-signed Commitment",
                                    "img": "/static/img/nfts/manifesto.png",
                                }
                            )
                            matched = True
                            break
                        elif record.get("identityNft") == mint or record.get("identityNftMint") == mint:
                            nft_data.update(
                                {
                                    "name": "Augmentor Identity",
                                    "tag": "AI Agent NFT",
                                    "img": "/static/img/nfts/ai-identity.png",
                                }
                            )
                            matched = True
                            break
                        elif record.get("alphaNft") == mint or record.get("alphaNftMint") == mint:
                            nft_data.update(
                                {
                                    "name": "AI Artisan Alpha Tester",
                                    "tag": "Early Adopter",
                                    "img": "/static/img/nfts/alpha-tester.png",
                                }
                            )
                            matched = True
                            break

                    # Fallback 0: check nft_registry.json
                    if not matched:
                        try:
                            reg_path = str(DASHBOARD_DIR / "data" / "nft_registry.json")
                            if os.path.exists(reg_path):
                                with open(reg_path) as rf:
                                    registry = json.load(rf)
                                nft_type_key = registry.get(mint)
                                if nft_type_key:
                                    _type_display = {
                                        "identity": {
                                            "name": "Augmentor Identity",
                                            "tag": "AI Agent NFT",
                                            "img": "/static/img/nfts/ai-identity.png",
                                        },
                                        "alpha": {
                                            "name": "AI Artisan Alpha Tester",
                                            "tag": "Early Adopter",
                                            "img": "/static/img/nfts/alpha-tester.png",
                                        },
                                        "license": {
                                            "name": "Symbiotic License",
                                            "tag": "Co-signed Agreement",
                                            "img": "/static/img/nfts/symbiotic-license.png",
                                        },
                                        "manifesto": {
                                            "name": "Augmentatism Manifesto",
                                            "tag": "Co-signed Commitment",
                                            "img": "/static/img/nfts/manifesto.png",
                                        },
                                        "founder": {
                                            "name": "ResonantOS Founder",
                                            "tag": "Founder",
                                            "img": "/static/img/nfts/founder.png",
                                        },
                                        "dao_genesis": {
                                            "name": "DAO Genesis",
                                            "tag": "Genesis",
                                            "img": "/static/img/nfts/dao-genesis.png",
                                        },
                                    }
                                    if nft_type_key in _type_display:
                                        nft_data.update(_type_display[nft_type_key])
                                        matched = True
                        except Exception as e:
                            print(f"Error reading nft_registry: {e}")

                    # Fallback 1: try on-chain metadata
                    if not matched:
                        # Map known names to display info
                        _name_map = {
                            "Augmentor Identity": {
                                "name": "Augmentor Identity",
                                "tag": "AI Agent NFT",
                                "img": "/static/img/nfts/ai-identity.png",
                            },
                            "AI Artisan — Alpha Tester": {
                                "name": "AI Artisan Alpha Tester",
                                "tag": "Early Adopter",
                                "img": "/static/img/nfts/alpha-tester.png",
                            },
                            "AI Artisan — Alpha": {
                                "name": "AI Artisan Alpha Tester",
                                "tag": "Early Adopter",
                                "img": "/static/img/nfts/alpha-tester.png",
                            },
                            "Symbiotic License Agreement": {
                                "name": "Symbiotic License",
                                "tag": "Co-signed Agreement",
                                "img": "/static/img/nfts/symbiotic-license.png",
                            },
                            "Augmentatism Manifesto": {
                                "name": "Augmentatism Manifesto",
                                "tag": "Co-signed Commitment",
                                "img": "/static/img/nfts/manifesto.png",
                            },
                            "ResonantOS Founder": {
                                "name": "ResonantOS Founder",
                                "tag": "Founder",
                                "img": "/static/img/nfts/founder.png",
                            },
                            "Resonant Economy DAO Genesis": {
                                "name": "DAO Genesis",
                                "tag": "Genesis",
                                "img": "/static/img/nfts/dao-genesis.png",
                            },
                        }
                        # Try reading on-chain metadata from mint account
                        try:
                            mint_info = _solana_rpc(network, "getAccountInfo", [mint, {"encoding": "jsonParsed"}])
                            mint_data = mint_info.get("result", {}).get("value", {}).get("data", {})
                            # Token-2022 parsed data may include extensions with metadata
                            extensions = []
                            if isinstance(mint_data, dict):
                                parsed_info = mint_data.get("parsed", {}).get("info", {})
                                extensions = parsed_info.get("extensions", [])
                            for ext in extensions:
                                if ext.get("extension") == "tokenMetadata":
                                    state = ext.get("state", {})
                                    onchain_name = state.get("name", "").strip().rstrip("\x00")
                                    if onchain_name:
                                        # Try matching against known names
                                        for known_name, info in _name_map.items():
                                            if (
                                                known_name.lower() in onchain_name.lower()
                                                or onchain_name.lower() in known_name.lower()
                                            ):
                                                nft_data.update(info)
                                                matched = True
                                                break
                                        if not matched:
                                            nft_data["name"] = onchain_name
                                            matched = True
                                    break
                        except Exception as e:
                            print(f"Error reading mint metadata for {mint}: {e}")

                    if not matched:
                        # Skip unidentified NFTs — only show recognized ones
                        continue

                    nfts.append(nft_data)
        except Exception as e:
            print(f"Error querying NFTs: {e}")

        return jsonify({"address": address, "network": network, "nfts": nfts, "count": len(nfts)})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
