"""Fetch my clan and print its name, member count, and a members table."""
import os
import sys
from urllib.parse import quote

import httpx
from dotenv import load_dotenv

BASE_URL = "https://api.clashofclans.com/v1"

# The API uses internal role names; the game shows different labels.
ROLE_LABELS = {
    "leader": "Leader",
    "coLeader": "Co-Leader",
    "admin": "Elder",
    "member": "Member",
}


def print_members(members: list[dict]) -> None:
    """Print members as an aligned table: name, TH, role, donations given/received."""
    print(f"\n{'#':>2}  {'Name':<16} {'TH':>3}  {'Role':<10} {'Donated':>8} {'Received':>9}")
    print("-" * 54)
    for m in members:
        role = ROLE_LABELS.get(m["role"], m["role"])
        print(
            f"{m['clanRank']:>2}  {m['name']:<16} {m['townHallLevel']:>3}  "
            f"{role:<10} {m['donations']:>8} {m['donationsReceived']:>9}"
        )


def main() -> None:
    """Call GET /clans/{tag} and print basic clan info."""
    # Player names often contain Unicode (fancy fonts, emoji). On Windows,
    # Python may default to cp1252 output and crash, so force UTF-8.
    sys.stdout.reconfigure(encoding="utf-8")

    # 1. Load secrets from .env (never print the key)
    load_dotenv()
    api_key = os.getenv("COC_API_KEY")
    clan_tag = os.getenv("CLAN_TAG")
    if not api_key or not clan_tag:
        sys.exit("Missing COC_API_KEY or CLAN_TAG in .env")

    # 2. Encode the tag: '#' would otherwise be treated as a URL fragment
    encoded_tag = quote(clan_tag, safe="")  # "#ABC123" -> "%23ABC123"

    # 3. Build the URL
    url = f"{BASE_URL}/clans/{encoded_tag}"

    # 4. Send the request with the bearer token
    headers = {"Authorization": f"Bearer {api_key}"}
    response = httpx.get(url, headers=headers, timeout=10)

    # 5. Handle errors: CoC returns JSON like {"reason": ..., "message": ...}
    if response.status_code != 200:
        print(f"Error {response.status_code}: {response.text}")
        sys.exit(1)

    # 6. Parse and print
    clan = response.json()
    print(f"Clan:    {clan['name']} ({clan['tag']})")
    print(f"Members: {clan['members']}/50")

    # memberList comes back sorted by clanRank (i.e. trophies)
    print_members(clan["memberList"])


if __name__ == "__main__":
    main()
