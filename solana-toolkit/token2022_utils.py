"""Shared helpers for Token-2022 minting and NFT operations."""

import hashlib
import json
import struct
import time
from pathlib import Path
from typing import Dict, Union

from solana.rpc.api import Client
from solana.rpc.types import TokenAccountOpts, TxOpts
from solders.instruction import AccountMeta, Instruction
from solders.keypair import Keypair
from solders.message import Message
from solders.pubkey import Pubkey
from solders.system_program import CreateAccountParams, TransferParams, create_account, transfer
from solders.transaction import Transaction
from spl.token.constants import TOKEN_2022_PROGRAM_ID
from spl.token.instructions import (
    InitializeMintParams,
    MintToParams,
    create_idempotent_associated_token_account,
    get_associated_token_address,
    initialize_mint,
    mint_to,
)


DEVNET_RPC_URL = "https://api.devnet.solana.com"
_METADATA_INIT_DISCRIMINATOR = hashlib.sha256(
    b"spl_token_metadata_interface:initialize_account"
).digest()[:8]


def _to_pubkey(value: Union[str, Pubkey]) -> Pubkey:
    return value if isinstance(value, Pubkey) else Pubkey.from_string(value)


def load_keypair_from_path(keypair_path: str) -> Keypair:
    """Load a Solana keypair from a JSON array file."""
    path = Path(keypair_path).expanduser()
    with path.open("r", encoding="utf-8") as f:
        secret_key = json.load(f)
    return Keypair.from_bytes(bytes(secret_key))


def _ensure_devnet(client: Client) -> None:
    provider = getattr(client, "_provider", None)
    endpoint_uri = getattr(provider, "endpoint_uri", "")
    if endpoint_uri and DEVNET_RPC_URL not in endpoint_uri:
        raise ValueError(f"Token-2022 helpers are restricted to devnet: {endpoint_uri}")


def _send_tx(
    client: Client,
    payer: Keypair,
    ixs: list[Instruction],
    extra_signers: list[Keypair] | None = None,
) -> str:
    _ensure_devnet(client)
    signers = [payer, *(extra_signers or [])]

    blockhash_resp = client.get_latest_blockhash()
    blockhash = blockhash_resp.value.blockhash
    msg = Message.new_with_blockhash(ixs, payer.pubkey(), blockhash)
    tx = Transaction.new_unsigned(msg)
    tx.sign(signers, blockhash)

    resp = client.send_transaction(
        tx,
        opts=TxOpts(skip_preflight=True, preflight_commitment="confirmed"),
    )
    sig = resp.value
    if sig is None:
        raise RuntimeError(f"Transaction send failed: {resp}")

    for _ in range(30):
        status = client.get_signature_statuses([sig])
        status_info = status.value[0] if status.value else None
        if status_info is not None:
            if status_info.err:
                raise RuntimeError(f"Transaction error: {status_info.err}")
            return str(sig)
        time.sleep(1)
    return str(sig)


def _initialize_non_transferable_mint_ix(mint: Pubkey) -> Instruction:
    """InitializeNonTransferableMint — instruction index 32 in Token-2022."""
    data = struct.pack("<B", 32)
    accounts = [AccountMeta(pubkey=mint, is_signer=False, is_writable=True)]
    return Instruction(TOKEN_2022_PROGRAM_ID, data, accounts)


def _initialize_metadata_pointer_ix(mint: Pubkey, authority: Pubkey) -> Instruction:
    """InitializeMetadataPointer — extension instruction 39, sub-instruction 0.

    Uses OptionalNonZeroPubkey format (raw 32 bytes, all-zeros = None).
    """
    data = struct.pack("<BB", 39, 0)  # extension type + Initialize sub-instruction
    data += bytes(authority)          # 32 bytes: metadata authority
    data += bytes(mint)               # 32 bytes: metadata address (mint itself)
    accounts = [AccountMeta(pubkey=mint, is_signer=False, is_writable=True)]
    return Instruction(TOKEN_2022_PROGRAM_ID, data, accounts)


def _borsh_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack("<I", len(encoded)) + encoded


def _calculate_mint_space(
    enable_non_transferable: bool = False,
    enable_metadata: bool = False,
) -> int:
    """Calculate the correct account size for a Token-2022 mint.

    Token-2022 layout:
    - No extensions: Mint::LEN = 82 bytes
    - With extensions: BASE (165) + AccountType (1) + TLV extensions
      - NonTransferable TLV: 2 (type) + 2 (len) + 0 (data) = 4
      - MetadataPointer TLV: 2 (type) + 2 (len) + 32 (authority) + 32 (address) = 68
    """
    if not enable_non_transferable and not enable_metadata:
        return 82  # Mint::LEN, no extensions

    # Base for extension accounts: Account::LEN (165) + AccountType (1) = 166
    space = 166
    if enable_non_transferable:
        space += 4   # NonTransferable TLV (no data)
    if enable_metadata:
        space += 68  # MetadataPointer TLV (authority + address)
    return space


def create_token2022_mint(
    client: Client,
    payer: Keypair,
    *,
    decimals: int = 0,
    enable_non_transferable: bool = False,
    enable_metadata: bool = False,
) -> Dict[str, str]:
    """Create a Token-2022 mint with optional extensions."""
    mint_keypair = Keypair()
    mint_pubkey = mint_keypair.pubkey()

    mint_space = _calculate_mint_space(enable_non_transferable, enable_metadata)
    rent = client.get_minimum_balance_for_rent_exemption(mint_space)
    lamports = rent.value

    ixs = [
        create_account(
            CreateAccountParams(
                from_pubkey=payer.pubkey(),
                to_pubkey=mint_pubkey,
                lamports=lamports,
                space=mint_space,
                owner=TOKEN_2022_PROGRAM_ID,
            )
        )
    ]

    if enable_non_transferable:
        ixs.append(_initialize_non_transferable_mint_ix(mint_pubkey))
    if enable_metadata:
        ixs.append(_initialize_metadata_pointer_ix(mint_pubkey, payer.pubkey()))

    ixs.append(
        initialize_mint(
            InitializeMintParams(
                program_id=TOKEN_2022_PROGRAM_ID,
                mint=mint_pubkey,
                decimals=decimals,
                mint_authority=payer.pubkey(),
                freeze_authority=payer.pubkey(),
            )
        )
    )

    sig = _send_tx(client, payer, ixs, extra_signers=[mint_keypair])
    return {"mint": str(mint_pubkey), "signature": sig}


def initialize_metadata(
    client: Client,
    payer: Keypair,
    mint: Union[str, Pubkey],
    name: str,
    symbol: str,
    uri: str,
    update_authority: Union[str, Pubkey, None] = None,
) -> str:
    """Initialize token metadata interface fields on a Token-2022 mint.

    Pre-transfers additional lamports for rent exemption after realloc,
    matching how spl-token CLI handles metadata initialization.
    """
    mint_pubkey = _to_pubkey(mint)
    update_authority_pubkey = _to_pubkey(update_authority) if update_authority else payer.pubkey()

    # Calculate metadata TLV size:
    # TokenMetadata struct: update_authority(32) + mint(32) + name(4+len) +
    # symbol(4+len) + uri(4+len) + additional_metadata(4 for empty Vec)
    # TLV header: 4 bytes (2 type + 2 length)
    # Add 200 bytes padding — Token-2022 may reallocate more than the strict
    # minimum due to internal alignment and future-proofing.
    metadata_data_len = (32 + 32
                         + (4 + len(name.encode()))
                         + (4 + len(symbol.encode()))
                         + (4 + len(uri.encode()))
                         + 4)  # empty additional_metadata Vec
    metadata_tlv_size = 4 + metadata_data_len + 200  # generous padding

    # Fetch current mint account to calculate rent difference
    from solana.rpc.commitment import Confirmed
    for _attempt in range(5):
        acct_resp = client.get_account_info(mint_pubkey, commitment=Confirmed)
        if acct_resp.value is not None:
            break
        time.sleep(2)
    if acct_resp.value is None:
        raise RuntimeError(f"Mint account {mint_pubkey} not found")
    current_len = len(acct_resp.value.data)
    current_lamports = acct_resp.value.lamports

    new_len = current_len + metadata_tlv_size
    new_rent = client.get_minimum_balance_for_rent_exemption(new_len).value
    additional_lamports = max(0, new_rent - current_lamports)

    ixs = []
    if additional_lamports > 0:
        ixs.append(transfer(TransferParams(
            from_pubkey=payer.pubkey(),
            to_pubkey=mint_pubkey,
            lamports=additional_lamports,
        )))

    data = _METADATA_INIT_DISCRIMINATOR
    data += _borsh_string(name)
    data += _borsh_string(symbol)
    data += _borsh_string(uri)

    accounts = [
        AccountMeta(pubkey=mint_pubkey, is_signer=False, is_writable=True),
        AccountMeta(pubkey=update_authority_pubkey, is_signer=False, is_writable=False),
        AccountMeta(pubkey=mint_pubkey, is_signer=False, is_writable=False),
        AccountMeta(pubkey=payer.pubkey(), is_signer=True, is_writable=False),
    ]
    ixs.append(Instruction(TOKEN_2022_PROGRAM_ID, data, accounts))
    return _send_tx(client, payer, ixs)


def create_ata_and_mint(
    client: Client,
    payer: Keypair,
    mint: Union[str, Pubkey],
    owner: Union[str, Pubkey],
    *,
    amount: int = 1,
) -> Dict[str, str]:
    """Create owner ATA for Token-2022 mint (idempotent) and mint tokens."""
    mint_pubkey = _to_pubkey(mint)
    owner_pubkey = _to_pubkey(owner)
    ata = get_associated_token_address(owner_pubkey, mint_pubkey, TOKEN_2022_PROGRAM_ID)

    ixs = [
        create_idempotent_associated_token_account(
            payer.pubkey(),
            owner_pubkey,
            mint_pubkey,
            TOKEN_2022_PROGRAM_ID,
        ),
        mint_to(
            MintToParams(
                program_id=TOKEN_2022_PROGRAM_ID,
                mint=mint_pubkey,
                dest=ata,
                mint_authority=payer.pubkey(),
                amount=amount,
                signers=[payer.pubkey()],
            )
        ),
    ]

    sig = _send_tx(client, payer, ixs)
    return {"ata": str(ata), "signature": sig}


def get_token_balance(client: Client, owner: Union[str, Pubkey], mint: Union[str, Pubkey]) -> float:
    """Return total token balance for owner+mint under Token-2022.

    Uses program_id filter (not mint filter) to query Token-2022 accounts,
    then filters by mint client-side. Uses confirmed commitment for
    recently created accounts.
    """
    from solana.rpc.commitment import Confirmed

    owner_pubkey = _to_pubkey(owner)
    mint_str = str(_to_pubkey(mint))

    resp = client.get_token_accounts_by_owner_json_parsed(
        owner_pubkey,
        TokenAccountOpts(program_id=TOKEN_2022_PROGRAM_ID),
        commitment=Confirmed,
    )

    total = 0.0
    for account in resp.value or []:
        parsed = account.account.data.parsed
        info = parsed["info"]
        if info.get("mint") == mint_str:
            total += float(info["tokenAmount"]["uiAmountString"])
    return total
