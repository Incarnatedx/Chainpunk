"""Reads one punk from the Ethereum contracts. Uses the chain, not the website,
because the project's terms forbid scraping the site."""
import logging
import os

from web3 import Web3

from punkid import parse_soul, parse_token_uri

log = logging.getLogger("punkid.chain")

CHAINPUNKS = "0x469FBeDC6081fAfc07Ba1bCAEE3545D057037f03"
PUNKPROFILE = "0xAa8570744eE69Fd73A4c71Fce6CB224c9eb9D5b1"
MAX_ID = 3333
GAS = 12_000_000  # tokenURI and the soul are heavy eth_calls (about 2.3M gas), so raise the limit


def _fn(name, inputs, output):
    return {
        "type": "function",
        "name": name,
        "stateMutability": "view",
        "inputs": [{"name": n, "type": t} for n, t in inputs],
        "outputs": [{"name": "", "type": output}],
    }


PUNKS_ABI = [
    _fn("tokenURI", [("id", "uint256")], "string"),
    _fn("ownerOf", [("id", "uint256")], "address"),
    _fn("genomeOf", [("id", "uint256")], "bytes32"),
    _fn("heldSince", [("id", "uint256")], "uint256"),
]
# agents.md says the profile exposes metadata(tokenId, key) -> bytes. If the name differs
# on Etherscan's "Read Contract" tab, change it here.
PROFILE_ABI = [
    _fn("metadata", [("id", "uint256"), ("key", "string")], "bytes"),
    _fn("getMetadata", [("id", "uint256"), ("key", "string")], "bytes"),
]

_w3 = None


def _web3():
    global _w3
    if _w3 is None:
        url = os.environ["ETH_RPC_URL"]
        _w3 = Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 60}))
    return _w3


def _soul_text(w3, token_id):
    profile = w3.eth.contract(address=Web3.to_checksum_address(PUNKPROFILE), abi=PROFILE_ABI)
    for name in ("metadata", "getMetadata"):
        try:
            raw = getattr(profile.functions, name)(token_id, "context").call({"gas": GAS})
            return bytes(raw).decode("utf-8", errors="replace")
        except Exception as exc:  # try the next function name without logging RPC details
            log.warning("profile.%s failed (%s)", name, type(exc).__name__)
    return ""


def fetch_art(token_id):
    """Return only the on-chain SVG for indexing; avoids the other per-punk calls."""
    if not 1 <= token_id <= MAX_ID:
        raise ValueError("Punk numbers go from 1 to 3333.")
    w3 = _web3()
    punks = w3.eth.contract(address=Web3.to_checksum_address(CHAINPUNKS), abi=PUNKS_ABI)
    uri = punks.functions.tokenURI(token_id).call({"gas": GAS})
    _, svg = parse_token_uri(uri)
    return svg


def fetch_punk(token_id):
    """Returns (data dict for the card, svg bytes)."""
    if not 1 <= token_id <= MAX_ID:
        raise ValueError("Punk numbers go from 1 to 3333.")
    w3 = _web3()
    punks = w3.eth.contract(address=Web3.to_checksum_address(CHAINPUNKS), abi=PUNKS_ABI)

    uri = punks.functions.tokenURI(token_id).call({"gas": GAS})
    meta, svg = parse_token_uri(uri)
    traits = [
        (a.get("trait_type"), a.get("value"))
        for a in meta.get("attributes", [])
        if a.get("trait_type") and a.get("trait_type") != "Status"
    ]
    holder = punks.functions.ownerOf(token_id).call()
    genome = "0x" + bytes(punks.functions.genomeOf(token_id).call({"gas": GAS})).hex()
    held_since = punks.functions.heldSince(token_id).call()
    soul = parse_soul(_soul_text(w3, token_id))

    data = {
        "token_id": token_id,
        "traits": traits,
        "genome": genome,
        "holder": holder,
        "held_since": held_since,
        "soul": soul,
    }
    return data, svg
