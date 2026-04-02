"""Read-only DAO governance data from Solana Realms program."""

import struct
from typing import Dict, List, Any, Optional

from solana.rpc.api import Client
from solders.pubkey import Pubkey

from wallet import SolanaWallet

# SPL Governance program (Realms v3)
GOVERNANCE_PROGRAM_ID = Pubkey.from_string("GovER5Lthms3bLBqWub97yVrMmEogzX7xNjdXpPPCVZw")

# Default DAO realm
DEFAULT_REALM = "42sRg1Spzu3YxwXTduDFLWPtb4JJQhmMmDMbPPmnvoTY"


def _decode_string(data: bytes, offset: int) -> tuple:
    """Decode a Borsh string (u32 length prefix + utf-8 bytes). Returns (string, new_offset)."""
    if offset + 4 > len(data):
        return ("", offset)
    length = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    if offset + length > len(data):
        return ("", offset)
    s = data[offset:offset + length].decode("utf-8", errors="replace")
    return (s, offset + length)


class DAOReader:
    """Query DAO realm information from the SPL Governance (Realms) program on Solana."""

    def __init__(self, wallet: Optional[SolanaWallet] = None, realm: str = DEFAULT_REALM):
        """
        Initialize DAOReader.

        Args:
            wallet: SolanaWallet instance. Creates default if None.
            realm: Realm public key (base58). Defaults to ResonantOS devnet realm.
        """
        self.wallet = wallet or SolanaWallet()
        self.client = self.wallet.client
        self.realm_pubkey = Pubkey.from_string(realm)

    def get_realm_info(self) -> Dict[str, Any]:
        """
        Fetch and decode the Realm account data.

        Returns:
            Dict with realm name, authority, community_mint, council_mint, and raw config.

        Raises:
            Exception: If the realm account is not found or unreadable.
        """
        resp = self.client.get_account_info(self.realm_pubkey)
        if resp.value is None:
            raise Exception(f"Realm account not found: {self.realm_pubkey}")

        data = bytes(resp.value.data)
        owner = str(resp.value.owner)

        # Realm account layout (Borsh):
        # [0] account_type: u8 (should be 1 for Realm)
        # [1..33] community_mint: Pubkey (32 bytes)
        # [33] reserved_v1: u8
        # [34..66] authority: Option<Pubkey> (1 byte tag + 32 bytes if Some)
        # Then: name (Borsh string), config struct...
        result: Dict[str, Any] = {
            "realm": str(self.realm_pubkey),
            "owner_program": owner,
            "raw_data_len": len(data),
        }

        if len(data) < 34:
            result["error"] = "Account data too short to parse"
            return result

        account_type = data[0]
        result["account_type"] = account_type

        # Community mint
        community_mint = Pubkey.from_bytes(data[1:33])
        result["community_mint"] = str(community_mint)

        # reserved
        offset = 34

        # Authority (Option<Pubkey>)
        if offset < len(data):
            has_authority = data[offset]
            offset += 1
            if has_authority and offset + 32 <= len(data):
                authority = Pubkey.from_bytes(data[offset:offset + 32])
                result["authority"] = str(authority)
                offset += 32
            else:
                result["authority"] = None

        # Name (Borsh string)
        if offset + 4 <= len(data):
            name, offset = _decode_string(data, offset)
            result["name"] = name

        return result

    def get_governance_accounts(self) -> List[Dict[str, Any]]:
        """
        Fetch all governance accounts for this realm using getProgramAccounts.

        Returns:
            List of dicts with pubkey, data_len, and decoded fields where possible.
        """
        # Governance accounts have account_type = 2 at byte 0
        # and realm pubkey at bytes 1..33
        filters = [
            {"memcmp": {"offset": 0, "bytes": "2"}},  # account_type = Governance (rough)
        ]

        # Use getProgramAccounts with memcmp on realm
        # realm pubkey starts at offset 1 for Governance accounts
        realm_b58 = str(self.realm_pubkey)

        resp = self.client.get_program_accounts(
            GOVERNANCE_PROGRAM_ID,
            encoding="base64",
            filters=[
                {"dataSize": 108},  # Common governance account size (may vary)
            ],
        )

        accounts: List[Dict[str, Any]] = []
        if resp.value:
            for acct in resp.value:
                data = bytes(acct.account.data)
                # Check if realm matches at offset 1
                if len(data) >= 33:
                    acct_realm = Pubkey.from_bytes(data[1:33])
                    if acct_realm == self.realm_pubkey:
                        entry: Dict[str, Any] = {
                            "pubkey": str(acct.pubkey),
                            "data_len": len(data),
                            "account_type": data[0] if data else None,
                        }
                        # Governed account at offset 33..65
                        if len(data) >= 65:
                            governed = Pubkey.from_bytes(data[33:65])
                            entry["governed_account"] = str(governed)
                        accounts.append(entry)

        return accounts

    def get_proposals(self, governance: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch proposal accounts for this realm (optionally filtered by governance).

        Args:
            governance: If provided, only return proposals under this governance pubkey.

        Returns:
            List of dicts with pubkey, governance, name, and state info.
        """
        # Proposal accounts: account_type = 6 (ProposalV2)
        # Layout: [0] type, [1..33] governance, [33..65] governing_token_mint,
        # [65] state(u8), ...then Borsh strings for name/description
        resp = self.client.get_program_accounts(
            GOVERNANCE_PROGRAM_ID,
            encoding="base64",
        )

        proposals: List[Dict[str, Any]] = []
        if not resp.value:
            return proposals

        for acct in resp.value:
            data = bytes(acct.account.data)
            if len(data) < 66:
                continue
            acct_type = data[0]
            # ProposalV1=5, ProposalV2=6
            if acct_type not in (5, 6):
                continue

            prop_governance = Pubkey.from_bytes(data[1:33])

            # Check governance belongs to our realm by filtering if governance param given
            if governance and str(prop_governance) != governance:
                continue

            governing_mint = Pubkey.from_bytes(data[33:65])
            state = data[65]

            state_names = {
                0: "Draft", 1: "SigningOff", 2: "Voting", 3: "Succeeded",
                4: "Executing", 5: "Completed", 6: "Cancelled", 7: "Defeated",
                8: "ExecutingWithErrors",
            }

            entry: Dict[str, Any] = {
                "pubkey": str(acct.pubkey),
                "governance": str(prop_governance),
                "governing_token_mint": str(governing_mint),
                "state": state_names.get(state, f"Unknown({state})"),
                "state_code": state,
                "version": "v2" if acct_type == 6 else "v1",
            }

            # Try to decode name from remaining data
            # After state byte, there are several fields before the name string
            # This varies by version; try a best-effort parse
            offset = 66
            # Skip: signatory_count(u8), signatories_signed_off(u8), vote_type(?), ...
            # For ProposalV2 the layout is complex; try to find the name heuristically
            # by scanning for a reasonable Borsh string
            for try_offset in range(66, min(200, len(data) - 4)):
                name_candidate, end = _decode_string(data, try_offset)
                if 3 < len(name_candidate) < 200 and name_candidate.isprintable():
                    entry["name"] = name_candidate
                    break

            proposals.append(entry)

        return proposals

    def get_token_owner_records(self, governing_token_mint: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch TokenOwnerRecord accounts for this realm.

        Args:
            governing_token_mint: Filter by governing token mint (base58). Optional.

        Returns:
            List of dicts with owner, realm, governing_token_mint, token count info.
        """
        # TokenOwnerRecord: account_type=4
        # [0] type(u8), [1..33] realm, [33..65] governing_token_mint,
        # [65..97] governing_token_owner
        resp = self.client.get_program_accounts(
            GOVERNANCE_PROGRAM_ID,
            encoding="base64",
        )

        records: List[Dict[str, Any]] = []
        if not resp.value:
            return records

        for acct in resp.value:
            data = bytes(acct.account.data)
            if len(data) < 97:
                continue
            if data[0] != 4:  # TokenOwnerRecord
                continue

            rec_realm = Pubkey.from_bytes(data[1:33])
            if rec_realm != self.realm_pubkey:
                continue

            rec_mint = Pubkey.from_bytes(data[33:65])
            if governing_token_mint and str(rec_mint) != governing_token_mint:
                continue

            rec_owner = Pubkey.from_bytes(data[65:97])

            entry: Dict[str, Any] = {
                "pubkey": str(acct.pubkey),
                "realm": str(rec_realm),
                "governing_token_mint": str(rec_mint),
                "governing_token_owner": str(rec_owner),
            }

            # Governing token deposit amount (u64) at offset 97
            if len(data) >= 105:
                deposit = struct.unpack_from("<Q", data, 97)[0]
                entry["governing_token_deposit_amount"] = deposit

            records.append(entry)

        return records
