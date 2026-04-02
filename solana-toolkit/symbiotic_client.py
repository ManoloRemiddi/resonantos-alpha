"""Python client for the Symbiotic Wallet on-chain program.

Provides methods to interact with the deployed Anchor program:
initialize pairs, daily claims, freeze/unfreeze, rotate AI key, co-sign actions.

Uses solana-py + solders only (no Anchor Python SDK needed).
"""

import json
import struct
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any

from solana.rpc.api import Client
from solana.rpc.types import TxOpts
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
from solders.transaction import Transaction
from solders.message import Message
from solders.system_program import ID as SYSTEM_PROGRAM_ID
import time


# Anchor discriminators: sha256("global:<instruction_name>")[:8]
def _discriminator(name: str) -> bytes:
    """Compute Anchor instruction discriminator."""
    return hashlib.sha256(f"global:{name}".encode()).digest()[:8]


DISC_INITIALIZE_PAIR = _discriminator("initialize_pair")
DISC_DAILY_CLAIM = _discriminator("daily_claim")
DISC_EMERGENCY_FREEZE = _discriminator("emergency_freeze")
DISC_UNFREEZE = _discriminator("unfreeze")
DISC_ROTATE_AI_KEY = _discriminator("rotate_ai_key")
DISC_CO_SIGN_ACTION = _discriminator("co_sign_action")


class SymbioticClient:
    """Client for the Symbiotic Wallet program."""

    def __init__(
        self,
        program_id: str,
        keypair_path: str = "~/.config/solana/id.json",
        network: str = "devnet",
    ):
        """
        Initialize the client.

        Args:
            program_id: Deployed program public key (base58).
            keypair_path: Path to the signer keypair JSON.
            network: 'devnet', 'testnet', or 'mainnet-beta'.
        """
        self.program_id = Pubkey.from_string(program_id)

        expanded = Path(keypair_path).expanduser()
        with open(expanded, "r") as f:
            secret = json.load(f)
        self.keypair = Keypair.from_bytes(bytes(secret))

        rpcs = {
            "devnet": "https://api.devnet.solana.com",
            "testnet": "https://api.testnet.solana.com",
            "mainnet-beta": "https://api.mainnet-beta.com",
        }
        self.client = Client(rpcs.get(network, network))
        self.network = network

    def find_pair_pda(self, human: Pubkey, pair_nonce: int) -> tuple[Pubkey, int]:
        """Derive the PDA for a symbiotic pair.

        Returns:
            (pda_pubkey, bump)
        """
        seeds = [b"symbiotic", bytes(human), bytes([pair_nonce])]
        return Pubkey.find_program_address(seeds, self.program_id)

    def _send_tx(self, ixs: list[Instruction], signers: list[Keypair]) -> str:
        """Build, sign, send transaction. Returns signature."""
        blockhash_resp = self.client.get_latest_blockhash()
        blockhash = blockhash_resp.value.blockhash
        msg = Message.new_with_blockhash(ixs, signers[0].pubkey(), blockhash)
        tx = Transaction.new_unsigned(msg)
        tx.sign(signers, blockhash)
        resp = self.client.send_transaction(
            tx, opts=TxOpts(skip_preflight=True, preflight_commitment="confirmed")
        )
        sig = resp.value
        if sig is None:
            raise Exception(f"Transaction failed: {resp}")
        # Poll for confirmation
        for _ in range(30):
            status = self.client.get_signature_statuses([sig])
            if status.value and status.value[0] is not None:
                if status.value[0].err:
                    raise Exception(f"Transaction error: {status.value[0].err}")
                return str(sig)
            time.sleep(1)
        return str(sig)

    def initialize_pair(
        self,
        human_keypair: Keypair,
        ai_pubkey: Pubkey,
        pair_nonce: int = 0,
    ) -> Dict[str, Any]:
        """Create a new symbiotic pair.

        Args:
            human_keypair: Human wallet keypair (must sign).
            ai_pubkey: AI wallet public key (does not sign).
            pair_nonce: Nonce for PDA derivation (default 0).

        Returns:
            Dict with pair_pda, bump, signature.
        """
        pda, bump = self.find_pair_pda(human_keypair.pubkey(), pair_nonce)

        data = DISC_INITIALIZE_PAIR + struct.pack("<B", pair_nonce)

        accounts = [
            AccountMeta(pubkey=pda, is_signer=False, is_writable=True),
            AccountMeta(pubkey=human_keypair.pubkey(), is_signer=True, is_writable=True),
            AccountMeta(pubkey=ai_pubkey, is_signer=False, is_writable=False),
            AccountMeta(pubkey=SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
        ]

        ix = Instruction(self.program_id, data, accounts)
        sig = self._send_tx([ix], [human_keypair])

        return {"pair_pda": str(pda), "bump": bump, "signature": sig}

    def daily_claim(self, signer_keypair: Keypair, pair_pda: Pubkey) -> str:
        """Trigger daily claim. Signer must be human or AI of the pair."""
        pair_data = self._fetch_pair(pair_pda)

        data = DISC_DAILY_CLAIM
        accounts = [
            AccountMeta(pubkey=pair_pda, is_signer=False, is_writable=True),
            AccountMeta(pubkey=signer_keypair.pubkey(), is_signer=True, is_writable=False),
        ]

        ix = Instruction(self.program_id, data, accounts)
        return self._send_tx([ix], [signer_keypair])

    def emergency_freeze(self, signer_keypair: Keypair, pair_pda: Pubkey) -> str:
        """Freeze the pair. Either signer can trigger."""
        data = DISC_EMERGENCY_FREEZE
        accounts = [
            AccountMeta(pubkey=pair_pda, is_signer=False, is_writable=True),
            AccountMeta(pubkey=signer_keypair.pubkey(), is_signer=True, is_writable=False),
        ]
        ix = Instruction(self.program_id, data, accounts)
        return self._send_tx([ix], [signer_keypair])

    def unfreeze(self, human_keypair: Keypair, pair_pda: Pubkey) -> str:
        """Unfreeze the pair. Human only."""
        data = DISC_UNFREEZE
        accounts = [
            AccountMeta(pubkey=pair_pda, is_signer=False, is_writable=True),
            AccountMeta(pubkey=human_keypair.pubkey(), is_signer=True, is_writable=False),
        ]
        ix = Instruction(self.program_id, data, accounts)
        return self._send_tx([ix], [human_keypair])

    def rotate_ai_key(
        self, human_keypair: Keypair, pair_pda: Pubkey, new_ai: Pubkey
    ) -> str:
        """Rotate the AI key. Human only."""
        data = DISC_ROTATE_AI_KEY + bytes(new_ai)
        accounts = [
            AccountMeta(pubkey=pair_pda, is_signer=False, is_writable=True),
            AccountMeta(pubkey=human_keypair.pubkey(), is_signer=True, is_writable=False),
        ]
        ix = Instruction(self.program_id, data, accounts)
        return self._send_tx([ix], [human_keypair])

    def co_sign_action(
        self,
        human_keypair: Keypair,
        ai_keypair: Keypair,
        pair_pda: Pubkey,
        action_type: str,
        memo: str = "",
    ) -> str:
        """Co-signed action requiring both human and AI signatures."""
        # Borsh: discriminator + string(action_type) + string(memo)
        action_bytes = action_type.encode("utf-8")
        memo_bytes = memo.encode("utf-8")
        data = (
            DISC_CO_SIGN_ACTION
            + struct.pack("<I", len(action_bytes))
            + action_bytes
            + struct.pack("<I", len(memo_bytes))
            + memo_bytes
        )

        accounts = [
            AccountMeta(pubkey=pair_pda, is_signer=False, is_writable=False),
            AccountMeta(pubkey=human_keypair.pubkey(), is_signer=True, is_writable=False),
            AccountMeta(pubkey=ai_keypair.pubkey(), is_signer=True, is_writable=False),
        ]
        ix = Instruction(self.program_id, data, accounts)
        return self._send_tx([ix], [human_keypair, ai_keypair])

    def transfer_out(
        self,
        human_keypair: Keypair,
        pair_pda: Pubkey,
        pair_nonce: int,
        pair_bump: int,
        from_ata: Pubkey,
        to_ata: Pubkey,
        mint: Pubkey,
        amount: int,
        token_program_id: Pubkey,
    ) -> str:
        """Transfer SPL tokens out of the PDA to a recipient ATA.

        Args:
            human_keypair: Human wallet keypair (must sign).
            pair_pda: The symbiotic pair PDA.
            pair_nonce: Nonce used for PDA derivation.
            pair_bump: PDA bump seed.
            from_ata: PDA's associated token account (source).
            to_ata: Recipient's associated token account (destination).
            mint: Token mint address.
            amount: Raw token amount (with decimals applied).
            token_program_id: SPL Token or Token-2022 program ID.

        Returns:
            Transaction signature string.
        """
        data = _discriminator("transfer_out") + struct.pack("<Q", amount)

        accounts = [
            AccountMeta(pubkey=pair_pda, is_signer=False, is_writable=False),
            AccountMeta(pubkey=human_keypair.pubkey(), is_signer=True, is_writable=True),
            AccountMeta(pubkey=from_ata, is_signer=False, is_writable=True),
            AccountMeta(pubkey=to_ata, is_signer=False, is_writable=True),
            AccountMeta(pubkey=mint, is_signer=False, is_writable=False),
            AccountMeta(pubkey=token_program_id, is_signer=False, is_writable=False),
        ]

        ix = Instruction(self.program_id, data, accounts)
        return self._send_tx([ix], [human_keypair])

    def _fetch_pair(self, pair_pda: Pubkey) -> Optional[Dict]:
        """Fetch and decode pair account data (for diagnostics)."""
        resp = self.client.get_account_info(pair_pda)
        if resp.value is None:
            return None
        raw = resp.value.data
        if len(raw) < 93:
            return None
        # Skip 8-byte discriminator
        d = raw[8:]
        return {
            "human": str(Pubkey.from_bytes(d[0:32])),
            "ai": str(Pubkey.from_bytes(d[32:64])),
            "pair_nonce": d[64],
            "bump": d[65],
            "frozen": bool(d[66]),
            "last_claim": struct.unpack("<q", d[67:75])[0],
            "created_at": struct.unpack("<q", d[75:83])[0],
            "ai_rotations": struct.unpack("<H", d[83:85])[0],
        }

    def get_pair_info(self, human: Pubkey, pair_nonce: int = 0) -> Optional[Dict]:
        """Convenience: derive PDA and fetch pair data."""
        pda, _ = self.find_pair_pda(human, pair_nonce)
        data = self._fetch_pair(pda)
        if data:
            data["pda"] = str(pda)
        return data
