#!/usr/bin/env python3
"""Warframe Discord rotation tracker.

Tracks:
- Eleanor's Technocyte Coda weapon batch (4-day rotation)
- Bird 3's weekly Archon Shard
- Weekly Archon Hunt (live WFCD API: boss, shard color, missions)

Designed to run from GitHub Actions and post through a Discord webhook.
Uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
STATE_PATH = ROOT / "data" / "state.json"

USER_AGENT = "warframe-rotation-tracker/1.0 (+https://github.com/)"

# Discord embed colors (decimal RGB values)
COLORS = {
    "coda": 0x6E3CBC,
    "bird3": 0xE9B949,
    "archon": 0xD94B4B,
}

ARCHON_SHARDS = {
    "Archon Amar": "Crimson Archon Shard",
    "Archon Nira": "Amber Archon Shard",
    "Archon Boreal": "Azure Archon Shard",
}

ARCHON_EMOJI = {
    "Archon Amar": "🐺",
    "Archon Nira": "🐍",
    "Archon Boreal": "🦉",
}

SHARD_EMOJI = {
    "Crimson Archon Shard": "🔴",
    "Amber Archon Shard": "🟡",
    "Azure Archon Shard": "🔵",
}


@dataclass
class Rotation:
    key: str
    name: str
    starts: datetime
    expires: datetime
    payload: dict[str, Any]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso(value: str) -> datetime:
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def discord_time(dt: datetime, style: str = "R") -> str:
    return f"<t:{int(dt.timestamp())}:{style}>"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")
    temp.replace(path)


def get_json(url: str, timeout: int = 20) -> Any:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} while requesting {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error while requesting {url}: {exc.reason}") from exc


def post_webhook(webhook: str, body: dict[str, Any], dry_run: bool) -> None:
    if dry_run:
        print("\n--- Discord payload (dry run) ---")
        print(json.dumps(body, indent=2, ensure_ascii=False))
        return

    raw = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        webhook,
        data=raw,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            # Discord webhooks commonly return 204 No Content.
            if response.status not in (200, 204):
                raise RuntimeError(f"Discord webhook returned HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Discord webhook failed: HTTP {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Discord webhook network error: {exc.reason}") from exc


def scheduled_rotation(
    now: datetime,
    ref: datetime,
    duration: timedelta,
    values: list[Any],
) -> tuple[int, Any, datetime, datetime]:
    if now < ref:
        raise ValueError(f"Current time {now.isoformat()} is before rotation reference {ref.isoformat()}")

    elapsed = now - ref
    index = int(elapsed.total_seconds() // duration.total_seconds())
    starts = ref + duration * index
    expires = starts + duration
    value = values[index % len(values)]
    return index, value, starts, expires


def get_coda_rotation(config: dict[str, Any], now: datetime) -> Rotation:
    coda = config["coda"]
    ref = parse_iso(coda["reference_utc"])
    duration = timedelta(hours=int(coda.get("rotation_hours", 96)))
    batches = coda["batches"]
    order = coda.get("order", ["A", "B"])

    index, batch_name, starts, expires = scheduled_rotation(now, ref, duration, order)
    weapons = batches[batch_name]

    return Rotation(
        key=f"coda:{starts.isoformat()}",
        name="coda",
        starts=starts,
        expires=expires,
        payload={
            "index": index,
            "batch": batch_name,
            "weapons": weapons,
        },
    )


def get_bird3_rotation(config: dict[str, Any], now: datetime) -> Rotation:
    bird = config["bird3"]
    ref = parse_iso(bird["reference_utc"])
    duration = timedelta(days=7)
    order = bird["order"]

    index, shard, starts, expires = scheduled_rotation(now, ref, duration, order)

    return Rotation(
        key=f"bird3:{starts.isoformat()}",
        name="bird3",
        starts=starts,
        expires=expires,
        payload={
            "index": index,
            "shard": shard,
        },
    )


def get_archon_hunt(config: dict[str, Any]) -> Rotation:
    platform = config.get("platform", "pc")
    url = f"https://api.warframestat.us/{platform}/archonHunt"
    data = get_json(url)

    activation = parse_iso(data["activation"])
    expiry = parse_iso(data["expiry"])
    boss = data.get("boss", "Unknown Archon")
    shard = ARCHON_SHARDS.get(boss, "Archon Shard")
    missions = data.get("missions", [])

    # Prefer the API's stable ID, but fall back to activation if it is absent.
    api_id = data.get("id") or activation.isoformat()

    return Rotation(
        key=f"archon:{api_id}",
        name="archon",
        starts=activation,
        expires=expiry,
        payload={
            "boss": boss,
            "shard": shard,
            "faction": data.get("faction", "Narmer"),
            "missions": missions,
            "api_url": url,
        },
    )


def coda_embed(rotation: Rotation) -> dict[str, Any]:
    batch = rotation.payload["batch"]
    weapons = rotation.payload["weapons"]
    lines = "\n".join(f"• **{weapon}**" for weapon in weapons)

    return {
        "title": f"🦠 Eleanor Coda Rotation — Batch {batch}",
        "description": lines,
        "color": COLORS["coda"],
        "fields": [
            {
                "name": "Next rotation",
                "value": f"{discord_time(rotation.expires)}\n{discord_time(rotation.expires, 'F')}",
                "inline": False,
            },
            {
                "name": "Where",
                "value": "Eleanor Nightingale — Höllvania Central Mall",
                "inline": False,
            },
        ],
        "footer": {
            "text": "Coda batches rotate every 4 days at 00:00 UTC. Valence element/% must be checked in Eleanor's shop."
        },
        "timestamp": rotation.starts.isoformat().replace("+00:00", "Z"),
    }


def bird3_embed(rotation: Rotation) -> dict[str, Any]:
    shard = rotation.payload["shard"]
    emoji = SHARD_EMOJI.get(shard, "💠")
    return {
        "title": f"🐦 Bird 3 Weekly Shard — {shard}",
        "description": f"{emoji} **{shard}** is this week's Bird 3 offering for **30,000 Cavia Standing**.",
        "color": COLORS["bird3"],
        "fields": [
            {
                "name": "Resets",
                "value": f"{discord_time(rotation.expires)}\n{discord_time(rotation.expires, 'F')}",
                "inline": False,
            },
            {
                "name": "Where",
                "value": "Bird 3 → Shiny Treasures — Sanctum Anatomica",
                "inline": False,
            },
        ],
        "footer": {"text": "Bird 3 rotates weekly at Monday 00:00 UTC."},
        "timestamp": rotation.starts.isoformat().replace("+00:00", "Z"),
    }


def archon_embed(rotation: Rotation) -> dict[str, Any]:
    boss = rotation.payload["boss"]
    shard = rotation.payload["shard"]
    boss_emoji = ARCHON_EMOJI.get(boss, "⚔️")
    shard_emoji = SHARD_EMOJI.get(shard, "💠")

    fields: list[dict[str, Any]] = [
        {
            "name": "Reward",
            "value": f"{shard_emoji} **{shard}** (normal or Tauforged roll)",
            "inline": False,
        }
    ]

    for i, mission in enumerate(rotation.payload["missions"], start=1):
        mission_type = mission.get("type", "Unknown")
        node = mission.get("node", "Unknown node")
        fields.append(
            {
                "name": f"Mission {i}",
                "value": f"**{mission_type}** — {node}",
                "inline": False,
            }
        )

    fields.append(
        {
            "name": "Ends",
            "value": f"{discord_time(rotation.expires)}\n{discord_time(rotation.expires, 'F')}",
            "inline": False,
        }
    )

    return {
        "title": f"{boss_emoji} Weekly Archon Hunt — {boss}",
        "description": f"A new weekly Archon Hunt is active against **{boss}**.",
        "color": COLORS["archon"],
        "fields": fields,
        "footer": {"text": "Live data: WarframeStat.us / WFCD"},
        "timestamp": rotation.starts.isoformat().replace("+00:00", "Z"),
    }


def build_message(config: dict[str, Any], embed: dict[str, Any], mention: str | None) -> dict[str, Any]:
    message: dict[str, Any] = {
        "username": config.get("discord_username", "Warframe Rotation Tracker"),
        "embeds": [embed],
        "allowed_mentions": {"parse": []},
    }

    if mention:
        # Mention is intentionally explicit/configured. allowed_mentions is switched
        # to roles only when a role mention is configured.
        message["content"] = mention
        if mention.startswith("<@&"):
            role_id = mention[3:-1]
            message["allowed_mentions"] = {"roles": [role_id]}
        elif mention.startswith("<@"):
            user_id = mention[2:-1]
            message["allowed_mentions"] = {"users": [user_id]}

    return message


def tracker_mention(config: dict[str, Any], tracker_name: str) -> str | None:
    mentions = config.get("mentions", {})
    value = mentions.get(tracker_name) or mentions.get("all")
    if not value:
        return None
    return str(value).strip() or None


def main() -> int:
    parser = argparse.ArgumentParser(description="Post Warframe rotation changes to Discord.")
    parser.add_argument("--dry-run", action="store_true", help="Print Discord payloads instead of sending them.")
    parser.add_argument("--force", action="store_true", help="Send selected trackers even if state says they were already sent.")
    parser.add_argument(
        "--only",
        choices=["all", "coda", "bird3", "archon"],
        default="all",
        help="Run only one tracker.",
    )
    args = parser.parse_args()

    config = load_json(CONFIG_PATH, None)
    if not config:
        print(f"Missing or invalid config: {CONFIG_PATH}", file=sys.stderr)
        return 2

    webhook = os.getenv("DISCORD_WEBHOOK", "").strip()
    if not args.dry_run and not webhook:
        print("DISCORD_WEBHOOK environment variable is required (or use --dry-run).", file=sys.stderr)
        return 2

    state = load_json(STATE_PATH, {})
    now = utc_now()

    enabled: list[str]
    if args.only == "all":
        enabled = ["coda", "bird3", "archon"]
    else:
        enabled = [args.only]

    jobs: list[tuple[str, Rotation, dict[str, Any]]] = []

    try:
        if "coda" in enabled and config.get("coda", {}).get("enabled", True):
            r = get_coda_rotation(config, now)
            jobs.append(("coda", r, coda_embed(r)))

        if "bird3" in enabled and config.get("bird3", {}).get("enabled", True):
            r = get_bird3_rotation(config, now)
            jobs.append(("bird3", r, bird3_embed(r)))

        if "archon" in enabled and config.get("archon_hunt", {}).get("enabled", True):
            r = get_archon_hunt(config)
            jobs.append(("archon", r, archon_embed(r)))
    except Exception as exc:
        print(f"Failed to calculate/fetch rotations: {exc}", file=sys.stderr)
        return 1

    sent = 0
    for tracker_name, rotation, embed in jobs:
        previous_key = state.get(tracker_name)
        changed = previous_key != rotation.key

        print(
            f"[{tracker_name}] current={rotation.key} previous={previous_key!r} "
            f"changed={changed} force={args.force}"
        )

        if not changed and not args.force:
            continue

        mention = tracker_mention(config, tracker_name)
        message = build_message(config, embed, mention)

        try:
            post_webhook(webhook, message, args.dry_run)
        except Exception as exc:
            print(f"Failed to post {tracker_name}: {exc}", file=sys.stderr)
            return 1

        sent += 1
        if not args.dry_run:
            state[tracker_name] = rotation.key

    if not args.dry_run and sent > 0:
        state["updated_at"] = now.isoformat().replace("+00:00", "Z")
        save_json(STATE_PATH, state)

    print(f"Done. Sent {sent} notification(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
