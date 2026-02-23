"""ResonantOS Solana Toolkit — unified entry point."""

from wallet import SolanaWallet
from token_manager import TokenManager
from nft_minter import NFTMinter
from dao_reader import DAOReader


class ResonantToolkit:
    """Facade combining all Solana toolkit components."""

    def __init__(
        self,
        keypair_path: str = "~/.config/solana/id.json",
        network: str = "devnet",
        realm: str = "42sRg1Spzu3YxwXTduDFLWPtb4JJQhmMmDMbPPmnvoTY",
    ):
        """
        Initialize all toolkit components with a shared wallet.

        Args:
            keypair_path: Path to Solana keypair JSON file.
            network: Solana network ('devnet', 'testnet', 'mainnet-beta').
            realm: DAO realm public key (base58).
        """
        self.wallet = SolanaWallet(keypair_path=keypair_path, network=network)
        self.tokens = TokenManager(wallet=self.wallet)
        self.nfts = NFTMinter(wallet=self.wallet)
        self.dao = DAOReader(wallet=self.wallet, realm=realm)

    @property
    def pubkey(self) -> str:
        """Return wallet public key as string."""
        return str(self.wallet.pubkey)


def create_toolkit(
    keypair_path: str = "~/.config/solana/id.json",
    network: str = "devnet",
    realm: str = "42sRg1Spzu3YxwXTduDFLWPtb4JJQhmMmDMbPPmnvoTY",
) -> ResonantToolkit:
    """
    Factory function to create a fully initialized ResonantToolkit.

    Args:
        keypair_path: Path to Solana keypair JSON file.
        network: Solana network.
        realm: DAO realm public key.

    Returns:
        ResonantToolkit: Initialized toolkit with wallet, tokens, nfts, dao.
    """
    return ResonantToolkit(keypair_path=keypair_path, network=network, realm=realm)
