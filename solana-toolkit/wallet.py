import json
import time
from pathlib import Path
from typing import List, Dict, Any

from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.message import Message
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer as transfer_ix
from solders.transaction import Transaction


class SolanaWallet:
    """A Solana wallet wrapper for keypair management and basic RPC operations."""
    
    def __init__(self, keypair_path: str = "~/.config/solana/id.json", network: str = "devnet"):
        """
        Initialize the Solana wallet by loading a keypair and setting up the RPC client.
        
        Args:
            keypair_path: Path to the JSON keypair file. Defaults to ~/.config/solana/id.json.
            network: Network to connect to ('devnet', 'testnet', 'mainnet-beta'). Defaults to 'devnet'.
        
        Raises:
            FileNotFoundError: If the keypair file does not exist.
            ValueError: If the keypair file contains invalid data.
        """
        expanded_path = Path(keypair_path).expanduser()
        
        if not expanded_path.exists():
            raise FileNotFoundError(f"Keypair file not found: {expanded_path}")
        
        try:
            with open(expanded_path, 'r') as f:
                secret_key = json.load(f)
            
            keypair_bytes = bytes(secret_key)
            self.keypair = Keypair.from_bytes(keypair_bytes)
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            raise ValueError(f"Invalid keypair file format: {e}")
        
        if network == "devnet":
            rpc_url = "https://api.devnet.solana.com"
        elif network == "testnet":
            rpc_url = "https://api.testnet.solana.com"
        elif network == "mainnet-beta":
            rpc_url = "https://api.mainnet-beta.solana.com"
        else:
            rpc_url = network
        
        self.client = Client(rpc_url)
        self.network = network
        self.pubkey = self.keypair.pubkey()
    
    def get_balance(self) -> float:
        """
        Get the SOL balance of the wallet.
        
        Returns:
            float: The balance in SOL (9 decimal places).
        
        Raises:
            Exception: If the RPC request fails or returns no value.
        """
        response = self.client.get_balance(self.pubkey)
        
        if response.value is None:
            raise Exception("Failed to retrieve balance from RPC")
        
        return float(response.value) / 1e9
    
    def airdrop(self, amount_sol: float, retries: int = 3, delay: float = 2.0) -> str:
        """
        Request an airdrop of SOL (devnet/testnet only).
        
        Args:
            amount_sol: Amount of SOL to request.
            retries: Number of attempts before failing.
            delay: Initial delay between retries in seconds.
        
        Returns:
            str: The transaction signature as a base58-encoded string.
        
        Raises:
            Exception: If the airdrop request fails.
        """
        lamports = int(amount_sol * 1e9)
        current_delay = delay
        last_error = None

        for attempt in range(1, retries + 1):
            try:
                response = self.client.request_airdrop(self.pubkey, lamports)
                if response.value is None:
                    raise Exception(f"Airdrop request failed: {response}")
                return str(response.value)
            except Exception as e:
                last_error = e
                if attempt < retries:
                    print(f"Airdrop attempt {attempt}/{retries} failed: {e}")
                    time.sleep(current_delay)
                    current_delay *= 1.5

        raise Exception(f"Airdrop request failed after {retries} attempts: {last_error}")

    def transfer(self, to: str, amount_sol: float) -> str:
        """
        Transfer SOL from this wallet to a recipient.

        Args:
            to: Recipient wallet public key (base58).
            amount_sol: Amount of SOL to transfer.

        Returns:
            str: The transaction signature as a base58-encoded string.

        Raises:
            ValueError: If amount is not positive or recipient pubkey is invalid.
            Exception: If transaction submission or confirmation fails.
        """
        lamports = int(amount_sol * 1e9)
        if lamports <= 0:
            raise ValueError("Transfer amount must be greater than zero")

        recipient = Pubkey.from_string(to)
        blockhash_resp = self.client.get_latest_blockhash()
        blockhash = blockhash_resp.value.blockhash

        ix = transfer_ix(
            TransferParams(
                from_pubkey=self.keypair.pubkey(),
                to_pubkey=recipient,
                lamports=lamports,
            )
        )
        msg = Message.new_with_blockhash([ix], self.keypair.pubkey(), blockhash)
        tx = Transaction.new_unsigned(msg)
        tx.sign([self.keypair], blockhash)

        send_resp = self.client.send_transaction(tx)
        sig = send_resp.value
        if sig is None:
            raise Exception(f"Transfer transaction failed: {send_resp}")

        for _ in range(30):
            status = self.client.get_signature_statuses([sig])
            if status.value and status.value[0] is not None:
                if status.value[0].err:
                    raise Exception(f"Transfer transaction error: {status.value[0].err}")
                return str(sig)
            time.sleep(1)

        return str(sig)
    
    def get_recent_transactions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent transaction signatures for the wallet address.
        
        Args:
            limit: Maximum number of transactions to return. Defaults to 10.
        
        Returns:
            List[Dict]: List of transaction info dicts with signature, slot, err, block_time.
        
        Raises:
            Exception: If the RPC request fails.
        """
        response = self.client.get_signatures_for_address(self.pubkey, limit=limit)
        
        if response.value is None:
            raise Exception("Failed to retrieve transactions from RPC")
        
        transactions = []
        for tx in response.value:
            transactions.append({
                "signature": str(tx.signature),
                "slot": tx.slot,
                "err": tx.err,
                "block_time": tx.block_time
            })
        
        return transactions
