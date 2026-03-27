"""Symbiotic wallet routes."""

from __future__ import annotations

import hashlib
import json
import traceback
import urllib.request
from typing import Any

from flask import Blueprint, Response, jsonify, request

from routes.config import _SOLANA_RPCS, _SYMBIOTIC_PROGRAM_ID
from routes.wallet_helpers import _get_wallet_pubkey

symbiotic_bp = Blueprint("symbiotic", __name__)


@symbiotic_bp.route("/api/symbiotic/build-init-tx", methods=["POST"])
def symbiotic_build_init_tx() -> Response:
    """Build an unsigned symbiotic initialize transaction.

    Validate the incoming wallet request, derive the PDA for the human and AI
    pair, and construct the Solana instruction payload for Phantom to sign.
    Fetch the latest blockhash so the client receives a ready-to-sign
    transaction blob.

    Dependencies:
        request.get_json(), _SOLANA_RPCS, _SYMBIOTIC_PROGRAM_ID, and _get_wallet_pubkey().

    Returns:
        Response: JSON response containing the base64 transaction and PDA metadata.
    """
    try:
        data: dict[str, Any] = request.get_json(force=True)
        human_str = data.get("humanPubkey", "").strip()
        network = data.get("network", "devnet")

        if network != "devnet":
            return jsonify({"error": "Alpha: devnet only"}), 400
        if not human_str:
            return jsonify({"error": "humanPubkey required"}), 400

        import base64 as _b64
        import struct as _struct

        from solana.rpc.api import Client as _Client
        from solders.instruction import AccountMeta as _AM, Instruction as _Ix
        from solders.message import Message as _Msg
        from solders.pubkey import Pubkey as _Pubkey
        from solders.system_program import ID as _SYS
        from solders.transaction import Transaction as _Tx

        program_id = _Pubkey.from_string(_SYMBIOTIC_PROGRAM_ID)
        human = _Pubkey.from_string(human_str)
        ai_pubkey = _get_wallet_pubkey()
        ai_pubkey_str = str(ai_pubkey) if ai_pubkey is not None else None
        ai = _Pubkey.from_string(ai_pubkey_str)
        pair_nonce = 0

        seeds = [b"symbiotic", bytes(human), bytes([pair_nonce])]
        pda, bump = _Pubkey.find_program_address(seeds, program_id)

        disc = hashlib.sha256(b"global:initialize_pair").digest()[:8]
        ix_data = disc + _struct.pack("<B", pair_nonce)

        accounts = [
            _AM(pubkey=pda, is_signer=False, is_writable=True),
            _AM(pubkey=human, is_signer=True, is_writable=True),
            _AM(pubkey=ai, is_signer=False, is_writable=False),
            _AM(pubkey=_SYS, is_signer=False, is_writable=False),
        ]

        ix = _Ix(program_id, ix_data, accounts)

        rpc_url = _SOLANA_RPCS.get(network, _SOLANA_RPCS["devnet"])
        client = _Client(rpc_url)
        bh_resp = client.get_latest_blockhash()
        blockhash = bh_resp.value.blockhash

        msg = _Msg.new_with_blockhash([ix], human, blockhash)
        tx = _Tx.new_unsigned(msg)

        tx_bytes = bytes(tx)
        tx_b64 = _b64.b64encode(tx_bytes).decode("ascii")

        return jsonify(
            {
                "transaction": tx_b64,
                "pda": str(pda),
                "bump": bump,
                "aiPubkey": ai_pubkey_str,
                "humanPubkey": human_str,
            }
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@symbiotic_bp.route("/api/symbiotic/pair-info")
def symbiotic_pair_info() -> Response:
    """Return on-chain symbiotic pair data for a wallet.

    Derive the expected PDA from the supplied human wallet and query the Solana
    RPC for account data. Decode the returned binary payload into a structured
    JSON document when the pair account exists.

    Dependencies:
        request.args, _SOLANA_RPCS, _SYMBIOTIC_PROGRAM_ID, and urllib.request.

    Returns:
        Response: JSON response describing the pair account or an error payload.
    """
    try:
        human_str = request.args.get("humanPubkey", "").strip()
        network = request.args.get("network", "devnet")

        if not human_str:
            return jsonify({"error": "humanPubkey required"}), 400

        from solders.pubkey import Pubkey as _Pubkey

        program_id = _Pubkey.from_string(_SYMBIOTIC_PROGRAM_ID)
        human = _Pubkey.from_string(human_str)

        seeds = [b"symbiotic", bytes(human), bytes([0])]
        pda, bump = _Pubkey.find_program_address(seeds, program_id)

        rpc_url = _SOLANA_RPCS.get(network, _SOLANA_RPCS["devnet"])
        rpc_data = json.loads(
            urllib.request.urlopen(
                urllib.request.Request(
                    rpc_url,
                    data=json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "getAccountInfo",
                            "params": [str(pda), {"encoding": "base64"}],
                        }
                    ).encode(),
                    headers={"Content-Type": "application/json"},
                ),
                timeout=10,
            ).read()
        )

        account = rpc_data.get("result", {}).get("value")
        if account is None:
            return jsonify({"exists": False, "pda": str(pda)})

        import base64 as _b64
        import struct as _struct

        from solders.pubkey import Pubkey as _P

        raw = _b64.b64decode(account["data"][0])
        if len(raw) < 93:
            return jsonify({"exists": False, "pda": str(pda)})

        d = raw[8:]
        pair_data = {
            "exists": True,
            "pda": str(pda),
            "human": str(_P.from_bytes(d[0:32])),
            "ai": str(_P.from_bytes(d[32:64])),
            "pairNonce": d[64],
            "bump": d[65],
            "frozen": bool(d[66]),
            "lastClaim": _struct.unpack("<q", d[67:75])[0],
            "createdAt": _struct.unpack("<q", d[75:83])[0],
            "aiRotations": _struct.unpack("<H", d[83:85])[0],
        }
        return jsonify(pair_data)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
