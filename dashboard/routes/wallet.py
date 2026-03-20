"""
Wallet routes - Solana wallet integration.
"""

import json
import time
from pathlib import Path
from flask import jsonify, request

def register_wallet_routes(app):
    """Register wallet routes."""

    def _get_wallet():
        """Get SolanaWallet instance if available."""
        try:
            from shared import Config
            cfg = Config()
            keypair_path = cfg.get("solana", "keypairPath", default="~/.config/solana/id.json")
            from solana_toolkit import SolanaWallet
            return SolanaWallet(keypair_path=str(Path(keypair_path).expanduser()))
        except Exception as e:
            return None

    @app.route("/api/wallet", methods=["GET"])
    def api_wallet():
        """Get wallet info including SOL balance and tokens."""
        wallet = _get_wallet()
        if not wallet:
            return jsonify({
                "address": None,
                "balance": 0,
                "tokens": {},
                "error": "Wallet not configured"
            })
        try:
            balance = wallet.get_balance()
            return jsonify({
                "address": str(wallet.pubkey),
                "balance": balance,
                "tokens": {}
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/wallet/user", methods=["GET"])
    def api_wallet_user():
        """Get current user info from wallet."""
        wallet = _get_wallet()
        if not wallet:
            return jsonify({"wallet": None, "username": "anonymous", "xp": 0, "level": 1})
        try:
            from shared import WORKSPACE
            profiles_file = WORKSPACE / "profiles.json"
            if profiles_file.exists():
                profiles = json.loads(profiles_file.read_text())
                wallet_addr = str(wallet.pubkey)
                if wallet_addr in profiles:
                    return jsonify(profiles[wallet_addr])
            return jsonify({
                "wallet": str(wallet.pubkey),
                "username": "anonymous",
                "xp": 0,
                "level": 1
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/wallet/mint-nft", methods=["POST"])
    def api_wallet_mint_nft():
        """Mint a soulbound NFT."""
        data = request.get_json() or {}
        wallet = _get_wallet()
        if not wallet:
            return jsonify({"success": False, "error": "Wallet not configured"}), 400
        nft_type = data.get("type", "identity")  # identity, license, manifesto
        try:
            from solana_toolkit import NFTMinter
            minter = NFTMinter(wallet=wallet)
            if nft_type == "identity":
                result = minter.mint_identity_nft()
            elif nft_type == "license":
                result = minter.mint_license_nft()
            elif nft_type == "manifesto":
                result = minter.mint_manifesto_nft()
            else:
                return jsonify({"success": False, "error": "Unknown NFT type"}), 400
            return jsonify({"success": True, "result": str(result)})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/wallet/build-transfer-tx", methods=["POST"])
    def api_wallet_build_transfer_tx():
        """Build a token transfer transaction."""
        data = request.get_json() or {}
        wallet = _get_wallet()
        if not wallet:
            return jsonify({"success": False, "error": "Wallet not configured"}), 400
        to_address = data.get("to")
        amount = data.get("amount")
        token_mint = data.get("mint")
        if not all([to_address, amount]):
            return jsonify({"success": False, "error": "Missing required fields"}), 400
        try:
            from solana_toolkit import TokenManager
            tm = TokenManager(wallet=wallet)
            result = tm.build_transfer_tx(to_address, amount, mint=token_mint)
            return jsonify({"success": True, "tx": result})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/wallet/build-sol-transfer", methods=["POST"])
    def api_wallet_build_sol_transfer():
        """Build a SOL transfer transaction."""
        data = request.get_json() or {}
        wallet = _get_wallet()
        if not wallet:
            return jsonify({"success": False, "error": "Wallet not configured"}), 400
        to_address = data.get("to")
        amount = data.get("amount")
        if not all([to_address, amount]):
            return jsonify({"success": False, "error": "Missing required fields"}), 400
        try:
            result = wallet.build_transfer_tx(to_address, amount)
            return jsonify({"success": True, "tx": result})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/wallet/send-tokens", methods=["POST"])
    def api_wallet_send_tokens():
        """Send tokens (requires signed transaction)."""
        data = request.get_json() or {}
        wallet = _get_wallet()
        if not wallet:
            return jsonify({"success": False, "error": "Wallet not configured"}), 400
        signed_tx = data.get("signedTx")
        if not signed_tx:
            return jsonify({"success": False, "error": "Missing signed transaction"}), 400
        try:
            result = wallet.send_transaction(signed_tx)
            return jsonify({"success": True, "signature": str(result)})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/wallet/daily-claim", methods=["POST"])
    def api_wallet_daily_claim():
        """Claim daily reward."""
        wallet = _get_wallet()
        if not wallet:
            return jsonify({"success": False, "error": "Wallet not configured"}), 400
        try:
            from shared import WORKSPACE
            claims_file = WORKSPACE / "daily_claims.json"
            claims = {}
            if claims_file.exists():
                claims = json.loads(claims_file.read_text())
            today = str(time.time() // 86400)
            wallet_addr = str(wallet.pubkey)
            last_claim = claims.get(wallet_addr, {}).get("day")
            if last_claim == today:
                return jsonify({"success": False, "error": "Already claimed today"}), 400
            claims[wallet_addr] = {"day": today, "time": time.time()}
            claims_file.write_text(json.dumps(claims, indent=2))
            return jsonify({"success": True, "reward": 10})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/wallet/onboarding-status", methods=["GET"])
    def api_wallet_onboarding_status():
        """Get onboarding status."""
        wallet = _get_wallet()
        if not wallet:
            return jsonify({"completed": False, "step": 1, "message": "Wallet not configured"})
        try:
            from shared import WORKSPACE
            onboarding_file = WORKSPACE / "onboarding.json"
            if onboarding_file.exists():
                data = json.loads(onboarding_file.read_text())
                return jsonify(data)
            return jsonify({"completed": False, "step": 1})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/wallet/agree-alpha", methods=["POST"])
    def api_wallet_agree_alpha():
        """Record alpha agreement."""
        wallet = _get_wallet()
        if not wallet:
            return jsonify({"success": False, "error": "Wallet not configured"}), 400
        try:
            from shared import WORKSPACE
            onboarding_file = WORKSPACE / "onboarding.json"
            data = {"agreed": True, "wallet": str(wallet.pubkey), "time": time.time()}
            onboarding_file.write_text(json.dumps(data, indent=2))
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/wallet/sign-license", methods=["POST"])
    def api_wallet_sign_license():
        """Sign license with wallet."""
        wallet = _get_wallet()
        if not wallet:
            return jsonify({"success": False, "error": "Wallet not configured"}), 400
        data = request.get_json() or {}
        license_hash = data.get("hash", "")
        try:
            signature = wallet.sign_message(license_hash)
            return jsonify({"success": True, "signature": str(signature)})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/wallet/sign-manifesto", methods=["POST"])
    def api_wallet_sign_manifesto():
        """Sign manifesto with wallet."""
        wallet = _get_wallet()
        if not wallet:
            return jsonify({"success": False, "error": "Wallet not configured"}), 400
        data = request.get_json() or {}
        manifesto_hash = data.get("hash", "")
        try:
            signature = wallet.sign_message(manifesto_hash)
            return jsonify({"success": True, "signature": str(signature)})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/wallet/reputation", methods=["GET"])
    def api_wallet_reputation():
        """Get reputation/XP info."""
        wallet = _get_wallet()
        if not wallet:
            return jsonify({"xp": 0, "level": 1, "reputation": 0})
        try:
            from shared import WORKSPACE
            rep_file = WORKSPACE / "reputation.json"
            if rep_file.exists():
                data = json.loads(rep_file.read_text())
                wallet_addr = str(wallet.pubkey)
                if wallet_addr in data:
                    return jsonify(data[wallet_addr])
            return jsonify({"xp": 0, "level": 1, "reputation": 0})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/wallet/grant-xp", methods=["POST"])
    def api_wallet_grant_xp():
        """Grant XP to a wallet (admin only)."""
        data = request.get_json() or {}
        wallet_addr = data.get("wallet")
        amount = data.get("amount", 0)
        if not wallet_addr or not amount:
            return jsonify({"success": False, "error": "Missing fields"}), 400
        try:
            from shared import WORKSPACE
            rep_file = WORKSPACE / "reputation.json"
            data = {}
            if rep_file.exists():
                data = json.loads(rep_file.read_text())
            if wallet_addr not in data:
                data[wallet_addr] = {"xp": 0, "level": 1, "reputation": 0}
            data[wallet_addr]["xp"] = data[wallet_addr].get("xp", 0) + amount
            data[wallet_addr]["level"] = data[wallet_addr]["xp"] // 100 + 1
            rep_file.write_text(json.dumps(data, indent=2))
            return jsonify({"success": True, "data": data[wallet_addr]})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/wallet/leaderboard", methods=["GET"])
    def api_wallet_leaderboard():
        """Get XP leaderboard."""
        try:
            from shared import WORKSPACE
            rep_file = WORKSPACE / "reputation.json"
            if not rep_file.exists():
                return jsonify({"leaders": []})
            data = json.loads(rep_file.read_text())
            leaders = sorted(data.items(), key=lambda x: x[1].get("xp", 0), reverse=True)[:10]
            return jsonify({"leaders": [{"wallet": k, **v} for k, v in leaders]})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/wallet/my-tribes", methods=["GET"])
    def api_wallet_my_tribes():
        """Get tribes for current wallet."""
        return jsonify([])

    @app.route("/api/wallet/my-bounties", methods=["GET"])
    def api_wallet_my_bounties():
        """Get bounties for current wallet."""
        return jsonify([])

    return app
