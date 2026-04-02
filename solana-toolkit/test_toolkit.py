#!/usr/bin/env python3
"""Integration tests for ResonantOS Solana Toolkit against devnet."""

import time
import unittest

from wallet import SolanaWallet
from token_manager import TokenManager
from nft_minter import NFTMinter
from dao_reader import DAOReader
from toolkit import create_toolkit, ResonantToolkit


class TestWallet(unittest.TestCase):
    """Test SolanaWallet basic operations."""

    def setUp(self):
        self.wallet = SolanaWallet()

    def test_wallet_loads(self):
        """Wallet loads keypair and has a valid pubkey."""
        self.assertIsNotNone(self.wallet.pubkey)
        pubkey_str = str(self.wallet.pubkey)
        self.assertGreater(len(pubkey_str), 20)
        print(f"  Wallet pubkey: {pubkey_str}")

    def test_get_balance(self):
        """Can query SOL balance from devnet."""
        balance = self.wallet.get_balance()
        self.assertIsInstance(balance, float)
        self.assertGreaterEqual(balance, 0.0)
        print(f"  SOL balance: {balance:.9f}")

    def test_recent_transactions(self):
        """Can query recent transactions."""
        txs = self.wallet.get_recent_transactions(limit=5)
        self.assertIsInstance(txs, list)
        print(f"  Recent txs: {len(txs)}")


class TestTokenManager(unittest.TestCase):
    """Test TokenManager operations."""

    def setUp(self):
        self.wallet = SolanaWallet()
        self.tm = TokenManager(wallet=self.wallet)

    def test_init(self):
        """TokenManager initializes with wallet."""
        self.assertIsNotNone(self.tm.client)
        self.assertIsNotNone(self.tm.payer)

    def test_get_token_balances(self):
        """Can query token balances."""
        balances = self.tm.get_token_balances()
        self.assertIsInstance(balances, list)
        print(f"  Token accounts: {len(balances)}")
        for b in balances:
            print(f"    {b['mint'][:16]}... = {b['balance']} ({b['program']})")

    def test_create_spl_token(self):
        """Create a standard SPL token mint on devnet."""
        # Ensure we have SOL
        balance = self.wallet.get_balance()
        if balance < 0.01:
            print("  Requesting airdrop for test...")
            self.wallet.airdrop(1.0)
            time.sleep(15)

        mint = self.tm.create_spl_token(decimals=6)
        self.assertIsNotNone(mint)
        self.assertGreater(len(mint), 20)
        print(f"  Created SPL mint: {mint}")


class TestNFTMinter(unittest.TestCase):
    """Test NFTMinter initialization."""

    def test_init(self):
        """NFTMinter initializes correctly."""
        minter = NFTMinter()
        self.assertIsNotNone(minter.client)
        self.assertIsNotNone(minter.payer)
        print(f"  NFTMinter ready, payer: {minter.payer.pubkey()}")


class TestDAOReader(unittest.TestCase):
    """Test DAOReader operations."""

    def setUp(self):
        self.dao = DAOReader()

    def test_init(self):
        """DAOReader initializes with default realm."""
        self.assertEqual(
            str(self.dao.realm_pubkey),
            "42sRg1Spzu3YxwXTduDFLWPtb4JJQhmMmDMbPPmnvoTY",
        )

    def test_get_realm_info(self):
        """Can fetch realm info from devnet."""
        info = self.dao.get_realm_info()
        self.assertIn("realm", info)
        print(f"  Realm: {info.get('name', '?')}")
        print(f"  Community mint: {info.get('community_mint', '?')}")


class TestToolkit(unittest.TestCase):
    """Test the unified toolkit."""

    def test_create_toolkit(self):
        """create_toolkit() returns a working ResonantToolkit."""
        tk = create_toolkit()
        self.assertIsInstance(tk, ResonantToolkit)
        self.assertIsNotNone(tk.wallet)
        self.assertIsNotNone(tk.tokens)
        self.assertIsNotNone(tk.nfts)
        self.assertIsNotNone(tk.dao)
        print(f"  Toolkit pubkey: {tk.pubkey}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
