"""Fetch war and player endpoints and save the raw JSON to scripts/samples/.

Usage:
    python scripts/save_samples.py            # uses PLAYER_TAG from .env (if set)
    python scripts/save_samples.py "#ABC123"  # or pass a player tag
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import httpx
from dotenv import load_dotenv

BASE_URL = "https://api.clashofclans.com/v1"
SAMPLES_DIR = Path("scripts/samples")


def encode_tag(tag: str) -> str:
    """URL-encode a CoC tag so '#' (and anything else) can't break the path."""
    return quote(tag, safe="")


def get(client: httpx.Client, path: str) -> httpx.Response:
    """GET a path relative to BASE_URL. Doesn't raise on errors; the caller checks status."""
    return client.get(f"{BASE_URL}{path}")


def save(name: str, response: httpx.Response) -> Path:
    """Save a response body as pretty JSON. Error bodies are saved too, as samples."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    suffix = "" if response.status_code == 200 else f"_{response.status_code}"
    path = SAMPLES_DIR / f"{name}_{timestamp}{suffix}.json"

    with path.open("w", encoding="utf-8") as f:
        json.dump(response.json(), f, indent=2, ensure_ascii=False)
    return path


def main() -> None:
    """Fetch currentwar, warlog and one player, and save each response."""
    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv()

    api_key = os.getenv("COC_API_KEY")
    clan_tag = os.getenv("CLAN_TAG")
    if not api_key or not clan_tag:
        sys.exit("Missing COC_API_KEY or CLAN_TAG in .env")

    # Player tag: command-line argument first, then .env
    player_tag = sys.argv[1] if len(sys.argv) > 1 else os.getenv("PLAYER_TAG")

    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    clan = encode_tag(clan_tag)
    endpoints = {
        "currentwar": f"/clans/{clan}/currentwar",
        "warlog": f"/clans/{clan}/warlog?limit=5",
    }
    if player_tag:
        endpoints["player"] = f"/players/{encode_tag(player_tag)}"
    else:
        print("No player tag given, so skipping /players (pass one or set PLAYER_TAG)")

    # One Client reuses the connection and the auth header for every request
    headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client(headers=headers, timeout=10) as client:
        for name, path in endpoints.items():
            response = get(client, path)
            saved_to = save(name, response)

            note = ""
            if response.status_code == 200 and name == "currentwar":
                note = f"  state={response.json().get('state')}"
            elif response.status_code != 200:
                note = f"  reason={response.json().get('reason')}"
            print(f"{name:<11} {response.status_code}  {saved_to}{note}")


if __name__ == "__main__":
    main()
