"""Protocol store routes."""

from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request

from routes.config import (
    PROTOCOL_NFTS,
    ProtocolNFTMinter,
    _MARKETPLACE_PROGRAM_ID,
    _REGISTRATION_BASKET_KEYPAIR,
    _RES_MINT,
    _SOLANA_RPCS,
    _SYMBIOTIC_PROGRAM_ID,
)
from routes.wallet_helpers import _require_identity_nft

protocols_bp = Blueprint("protocols", __name__)

# Track minted protocol NFTs: {protocol_id: {wallet: mint_address}}
_PROTOCOL_MINTS_FILE: Path = Path(__file__).parent.parent / "data" / "protocol_mints.json"


def _load_protocol_mints() -> dict[str, Any]:
    """Load locally recorded protocol mint ownership data.

    Read the protocol mint registry file when it exists and decode it into the
    in-memory structure used by the protocol store routes. Failures fall back
    to an empty mapping so read errors do not crash the API.

    Called by:
        Purchase, ownership, and content routes in this module.

    Side effects:
        Reads `_PROTOCOL_MINTS_FILE` from disk.

    Returns:
        dict[str, Any]: Wallet-to-protocol mint records or an empty mapping.
    """
    try:
        if _PROTOCOL_MINTS_FILE.exists():
            return json.loads(_PROTOCOL_MINTS_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_protocol_mints(data: dict[str, Any]) -> None:
    """Persist protocol mint ownership data to disk.

    Ensure the backing data directory exists, then overwrite the JSON file with
    the latest mint registry structure. The helper keeps protocol purchase state
    in a simple local file.

    Called by:
        `api_protocol_store_purchase()` after a successful mint.

    Side effects:
        Creates the parent directory if needed and writes
        `_PROTOCOL_MINTS_FILE`.

    Returns:
        None: This helper only performs file-system persistence.
    """
    _PROTOCOL_MINTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PROTOCOL_MINTS_FILE.write_text(json.dumps(data, indent=2))


@protocols_bp.route("/api/protocol-store/list", methods=["GET"])
def api_protocol_store_list() -> Response:
    """Return the catalog of purchasable protocols.

    Copy the configured protocol metadata and attach the canonical creator
    wallet expected by the frontend marketplace view. The route is read-only
    and does not inspect wallet ownership or on-chain state.

    Dependencies:
        `PROTOCOL_NFTS` and `jsonify()`.

    Returns:
        Response: JSON object keyed by protocol id with catalog metadata.
    """
    # Add creator to each protocol (Manolo's wallet for all official ones)
    enriched = {}
    for pid, pdata in PROTOCOL_NFTS.items():
        enriched[pid] = {**pdata, "creator": "vbYQ7rZu19Rjtro9obQxFeHq5UPNF5RQXA8jP8qywfF"}
    return jsonify({"protocols": enriched})


@protocols_bp.route("/api/protocol-store/purchase", methods=["POST"])
def api_protocol_store_purchase() -> Response:
    """Mint a purchased protocol NFT for an eligible wallet.

    Validate the request body, enforce devnet-only purchase rules, require an
    Identity NFT, and prevent duplicate local purchases before minting. For
    priced protocols, the route also checks the buyer's Symbiotic PDA balance
    before delegating the actual mint to `ProtocolNFTMinter`.

    Dependencies:
        request JSON payload, `PROTOCOL_NFTS`, `_require_identity_nft()`,
        `_load_protocol_mints()`, `_save_protocol_mints()`, Solana helpers, and
        `ProtocolNFTMinter`.

    Returns:
        Response: JSON payload describing the minted protocol NFT or an error
        response for validation, payment, or minting failures.
    """
    try:
        if not ProtocolNFTMinter:
            return jsonify({"error": "Protocol NFT minter not available"}), 500

        data = request.get_json() or {}
        protocol_id = data.get("protocol_id")
        wallet_address = data.get("wallet_address")
        network = data.get("network", "devnet")

        if network != "devnet":
            return jsonify({"error": "Only devnet supported during alpha"}), 400

        if not protocol_id or not wallet_address:
            return jsonify({"error": "protocol_id and wallet_address required"}), 400

        # Require Identity NFT
        if not _require_identity_nft(wallet_address):
            return jsonify({"error": "Identity NFT required. Complete onboarding first."}), 403

        if protocol_id not in PROTOCOL_NFTS:
            return jsonify({"error": f"Unknown protocol: {protocol_id}"}), 400

        # Check if already purchased
        mints = _load_protocol_mints()
        wallet_mints = mints.get(wallet_address, {})
        if protocol_id in wallet_mints:
            return jsonify({"error": "Already purchased", "mint": wallet_mints[protocol_id]}), 409

        # ── Verify $RES payment: check Symbiotic PDA balance ──
        protocol_info = PROTOCOL_NFTS[protocol_id]
        price_res = protocol_info.get("price_res", 0)  # price in $RES
        if price_res > 0:
            from solders.pubkey import Pubkey as _Pk
            from solana.rpc.api import Client as _Cl

            program_id = _Pk.from_string(_SYMBIOTIC_PROGRAM_ID)
            human_pk = _Pk.from_string(wallet_address)
            pda, _ = _Pk.find_program_address([b"symbiotic", bytes(human_pk), bytes([0])], program_id)
            res_mint = _Pk.from_string(_RES_MINT)
            res_prog = _Pk.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
            from spl.token.instructions import get_associated_token_address

            pda_ata = get_associated_token_address(pda, res_mint, res_prog)
            rpcs = {"devnet": "https://api.devnet.solana.com"}
            cl = _Cl(rpcs.get(network, network))
            ata_info = cl.get_account_info_json_parsed(pda_ata)
            pda_balance = 0
            if ata_info.value:
                try:
                    pda_balance = int(ata_info.value.data.parsed["info"]["tokenAmount"]["amount"]) / 1e6
                except Exception:
                    pass
            if pda_balance < price_res:
                return jsonify(
                    {
                        "error": f"Insufficient $RES balance. Need {price_res}, have {pda_balance:.2f}",
                        "required": price_res,
                        "balance": pda_balance,
                    }
                ), 402

            # TODO: Actual $RES burn/transfer via on-chain escrow program
            # Currently: balance check only (gate). Deduction requires Anchor
            # marketplace program CPI (5wpGj4EG6J5uEqozLqUyHzEQbU26yjaL5aUE5FwBiYe5).
            # For alpha: balance check prevents abuse; users can't purchase
            # without sufficient $RES in their Symbiotic PDA.
            current_app.logger.info(
                f"Protocol purchase: {wallet_address} buying {protocol_id} "
                f"(price={price_res} $RES, balance={pda_balance:.2f} $RES) "
                f"— BALANCE CHECK PASSED, deduction pending on-chain escrow"
            )

        # Use Registration Basket as fee payer
        fee_payer = str(_REGISTRATION_BASKET_KEYPAIR)

        minter = ProtocolNFTMinter()
        result = minter.mint_protocol_nft(
            recipient=wallet_address,
            protocol_id=protocol_id,
            fee_payer_keypair=fee_payer,
        )

        # Record the mint
        if wallet_address not in mints:
            mints[wallet_address] = {}
        mints[wallet_address][protocol_id] = result["mint"]
        _save_protocol_mints(mints)

        return jsonify(
            {
                "success": True,
                "mint": result["mint"],
                "ata": result["ata"],
                "protocol_id": protocol_id,
                "name": result["name"],
                "symbol": result["symbol"],
                "signature": result["mint_signature"],
                "transferable": True,
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@protocols_bp.route("/api/protocol-store/owned", methods=["GET"])
def api_protocol_store_owned() -> Response:
    """List protocol NFTs owned by a wallet.

    Read the local mint registry for the requested wallet and, when the minter
    client is available, attempt an on-chain ownership confirmation for each
    stored mint. If verification fails, the route falls back to trusting the
    local record instead of hiding the asset.

    Dependencies:
        `request.args`, `_load_protocol_mints()`, and optional
        `ProtocolNFTMinter.check_ownership()`.

    Returns:
        Response: JSON object containing the wallet and its owned protocol
        entries, or an error payload.
    """
    try:
        wallet = request.args.get("wallet")
        if not wallet:
            return jsonify({"error": "wallet parameter required"}), 400

        mints = _load_protocol_mints()
        wallet_mints = mints.get(wallet, {})

        owned = []
        for protocol_id, mint_address in wallet_mints.items():
            # Optionally verify on-chain ownership
            if ProtocolNFTMinter:
                try:
                    minter = ProtocolNFTMinter()
                    if minter.check_ownership(wallet, mint_address):
                        owned.append({"protocol_id": protocol_id, "mint": mint_address})
                except Exception:
                    # If check fails, trust the local record
                    owned.append({"protocol_id": protocol_id, "mint": mint_address})
            else:
                owned.append({"protocol_id": protocol_id, "mint": mint_address})

        return jsonify({"wallet": wallet, "owned": owned})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@protocols_bp.route("/api/protocol-store/content/<protocol_id>", methods=["GET"])
def api_protocol_store_content(protocol_id: str) -> Response:
    """Return protocol markdown for an owning wallet.

    Verify the requested wallet and mint against the local purchase registry,
    optionally confirm ownership on-chain, and then read the protocol markdown
    file from the repository. The route denies access when ownership cannot be
    established for the supplied mint.

    Dependencies:
        `request.args`, `PROTOCOL_NFTS`, `_load_protocol_mints()`,
        optional `ProtocolNFTMinter`, and protocol markdown files on disk.

    Returns:
        Response: JSON payload with protocol metadata and content or an error
        response for missing ownership or missing files.
    """
    try:
        wallet = request.args.get("wallet")
        mint_address = request.args.get("mint")

        if not wallet or not mint_address:
            return jsonify({"error": "wallet and mint parameters required"}), 400

        if protocol_id not in PROTOCOL_NFTS:
            return jsonify({"error": f"Unknown protocol: {protocol_id}"}), 404

        # Verify ownership
        mints = _load_protocol_mints()
        wallet_mints = mints.get(wallet, {})
        if protocol_id not in wallet_mints or wallet_mints[protocol_id] != mint_address:
            return jsonify({"error": "You do not own this protocol NFT"}), 403

        # On-chain verification if available
        if ProtocolNFTMinter:
            try:
                minter = ProtocolNFTMinter()
                if not minter.check_ownership(wallet, mint_address):
                    return jsonify({"error": "On-chain ownership verification failed"}), 403
            except Exception:
                pass  # Fall through if RPC fails

        # Read protocol content
        protocol_file = Path(__file__).parent.parent / "protocols" / f"{protocol_id}.md"
        if not protocol_file.exists():
            return jsonify({"error": "Protocol content not available"}), 404

        content = protocol_file.read_text()
        return jsonify(
            {
                "protocol_id": protocol_id,
                "name": PROTOCOL_NFTS[protocol_id]["name"],
                "content": content,
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Marketplace API (secondary market — all state on-chain via escrow program)
# ---------------------------------------------------------------------------
# Program: 5wpGj4EG6J5uEqozLqUyHzEQbU26yjaL5aUE5FwBiYe5 (DevNet)
# No server-side state. Listings read from Solana. Transactions signed by Phantom.

_RCT_SELL_THRESHOLD = 500

try:
    from marketplace_client import get_all_listings, MARKETPLACE_PROGRAM_ID
except ImportError:
    get_all_listings = None
    MARKETPLACE_PROGRAM_ID = _MARKETPLACE_PROGRAM_ID


@protocols_bp.route("/api/protocol-store/marketplace", methods=["GET"])
def api_marketplace_list() -> Response:
    """Fetch active secondary-market listings from Solana.

    Resolve the requested network RPC, call the marketplace client for live
    listings, and enrich each listing with known protocol metadata when a local
    mint map is available. The route stays read-only and returns an empty list
    plus an error message when chain access fails.

    Dependencies:
        `request.args`, `_SOLANA_RPCS`, optional `get_all_listings()`,
        `PROTOCOL_NFTS`, and the local mint-record file.

    Returns:
        Response: JSON object containing marketplace listings and program id.
    """
    try:
        if get_all_listings is None:
            return jsonify({"listings": [], "warning": "marketplace_client not available"})

        network = request.args.get("network", "devnet")
        rpc = _SOLANA_RPCS.get(network, _SOLANA_RPCS["devnet"])
        listings = get_all_listings(rpc=rpc)

        # Enrich with protocol metadata from known mints
        mints_file = Path(__file__).parent.parent.parent / "data" / "protocol_mints.json"
        mint_to_protocol = {}
        if mints_file.exists():
            records = json.loads(mints_file.read_text())
            for r in records.get("mints", []):
                mint_to_protocol[r["mint"]] = r.get("protocol_id", "")

        for l in listings:
            pid = mint_to_protocol.get(l["nft_mint"], "")
            l["protocol_id"] = pid
            if pid in PROTOCOL_NFTS:
                l["protocol_name"] = PROTOCOL_NFTS[pid]["name"]
                l["symbol"] = PROTOCOL_NFTS[pid]["symbol"]
                l["description"] = PROTOCOL_NFTS[pid].get("description", "")
                l["image"] = PROTOCOL_NFTS[pid].get("image", "")

        return jsonify({"listings": listings, "program_id": _MARKETPLACE_PROGRAM_ID})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"listings": [], "error": str(e)})


@protocols_bp.route("/api/protocol-store/marketplace/config", methods=["GET"])
def api_marketplace_config() -> Response:
    """Expose static marketplace constants for the frontend.

    Return the program ids, token ids, decimals, and sell threshold that the
    client needs when constructing marketplace transactions. This endpoint is a
    read-only configuration surface with no wallet-specific logic.

    Dependencies:
        `_MARKETPLACE_PROGRAM_ID`, `_RES_MINT`, and `_RCT_SELL_THRESHOLD`.

    Returns:
        Response: JSON object with marketplace configuration constants.
    """
    return jsonify(
        {
            "program_id": _MARKETPLACE_PROGRAM_ID,
            "res_mint": _RES_MINT,
            "res_decimals": 6,
            "rct_sell_threshold": _RCT_SELL_THRESHOLD,
            "token_2022_program": "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
            "spl_token_program": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
            "associated_token_program": "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
        }
    )
