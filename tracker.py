#!/usr/bin/env python3
"""Pazuul - Warframe Discord rotation/vendor tracker.

Tracks:
- Eleanor's Technocyte Coda weapon batch (4-day rotation)
- Bird 3's weekly Archon Shard
- Weekly Archon Hunt (live WarframeStat.us / WFCD)
- Baro Ki'Teer (live arrival + full inventory)
- Darvo's Daily Deal (live item, discount, price, stock)
- Teshin Steel Path Honors (live weekly reward + evergreen offerings)
- Steel Path Circuit Incarnon Genesis (9-week rotation)

Designed for GitHub Actions + a Discord webhook.
Uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
STATE_PATH = ROOT / "data" / "state.json"

USER_AGENT = "pazuul-warframe-tracker/2.1 (+https://github.com/)"

# Discord embed colors (decimal RGB values)
COLORS = {
    "coda": 0x6E3CBC,
    "bird3": 0xE9B949,
    "archon": 0xD94B4B,
    "baro": 0xC9A227,
    "darvo": 0x2E8B57,
    "teshin": 0x6B7280,
    "incarnon": 0x4F8FBF,
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

TRACKERS = ("coda", "bird3", "archon", "baro", "darvo", "teshin", "incarnon")


class TrackerNotReady(RuntimeError):
    """The upstream API has not published a fresh/current rotation yet."""


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
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} while requesting {url}: {details}") from exc
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


def stable_signature(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def ensure_current(starts: datetime, expires: datetime, now: datetime, label: str) -> None:
    if starts > now:
        raise TrackerNotReady(f"{label} API is showing a future rotation; retrying next check.")
    if expires <= now:
        raise TrackerNotReady(f"{label} API has not refreshed after reset yet; retrying next check.")


def chunk_lines(lines: list[str], max_chars: int = 950) -> list[str]:
    """Split lines into Discord field-sized chunks without cutting a line."""
    chunks: list[str] = []
    current = ""
    for line in lines:
        candidate = line if not current else current + "\n" + line
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        # Defensive fallback for an absurdly long item name.
        current = line[:max_chars]
    if current:
        chunks.append(current)
    return chunks


def fmt_num(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


# ---------------------------- Scheduled trackers ----------------------------


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
        payload={"index": index, "batch": batch_name, "weapons": weapons},
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
        payload={"index": index, "shard": shard},
    )


def get_incarnon_rotation(config: dict[str, Any], now: datetime) -> Rotation:
    """Calculate the current Steel Path Circuit Incarnon Genesis week."""
    incarnon = config["incarnon"]
    ref = parse_iso(incarnon["reference_utc"])
    reference_week = int(incarnon.get("reference_week", 9))
    weeks = incarnon["weeks"]

    week_numbers = sorted(int(key) for key in weeks.keys())
    if week_numbers != list(range(1, len(week_numbers) + 1)):
        raise ValueError("Incarnon weeks in config.json must be numbered consecutively starting at 1.")

    duration = timedelta(days=7)
    if now < ref:
        raise ValueError(
            f"Current time {now.isoformat()} is before Incarnon reference {ref.isoformat()}"
        )

    elapsed_weeks = int((now - ref).total_seconds() // duration.total_seconds())
    starts = ref + duration * elapsed_weeks
    expires = starts + duration

    total_weeks = len(week_numbers)
    current_week = ((reference_week - 1 + elapsed_weeks) % total_weeks) + 1
    next_week = (current_week % total_weeks) + 1

    weapons = weeks[str(current_week)]
    next_weapons = weeks[str(next_week)]

    return Rotation(
        key=f"incarnon:{starts.isoformat()}:week{current_week}",
        name="incarnon",
        starts=starts,
        expires=expires,
        payload={
            "week": current_week,
            "weapons": weapons,
            "next_week": next_week,
            "next_weapons": next_weapons,
        },
    )


# ------------------------------- Live trackers ------------------------------


def get_archon_hunt(config: dict[str, Any], now: datetime) -> Rotation:
    platform = config.get("platform", "pc")
    url = f"https://api.warframestat.us/{platform}/archonHunt?language=en"
    data = get_json(url)

    activation = parse_iso(data["activation"])
    expiry = parse_iso(data["expiry"])
    ensure_current(activation, expiry, now, "Archon Hunt")

    boss = data.get("boss", "Unknown Archon")
    shard = ARCHON_SHARDS.get(boss, "Archon Shard")
    missions = data.get("missions", []) or []
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


def get_baro(config: dict[str, Any], now: datetime) -> Rotation:
    platform = config.get("platform", "pc")
    url = f"https://api.warframestat.us/{platform}/voidTrader?language=en"
    data = get_json(url)

    activation = parse_iso(data["activation"])
    expiry = parse_iso(data["expiry"])
    active = bool(data.get("active")) and activation <= now < expiry
    inventory = data.get("inventory", []) or []
    api_id = data.get("id") or data.get("psId") or activation.isoformat()

    # Include the inventory signature so a just-arrived Baro whose inventory
    # populates a few minutes late can still trigger a fresh post.
    inventory_norm = [
        {
            "item": item.get("item", "Unknown item"),
            "ducats": item.get("ducats", 0),
            "credits": item.get("credits", 0),
        }
        for item in inventory
    ]
    signature = stable_signature(sorted(inventory_norm, key=lambda x: (x["item"], x["ducats"], x["credits"])))
    status = "active" if active else "inactive"

    return Rotation(
        key=f"baro:{api_id}:{status}:{signature}",
        name="baro",
        starts=activation,
        expires=expiry,
        payload={
            "active": active,
            "character": data.get("character", "Baro Ki'Teer"),
            "location": data.get("location", "Unknown Relay"),
            "inventory": inventory_norm,
            "api_url": url,
        },
    )


def get_darvo(config: dict[str, Any], now: datetime) -> Rotation:
    platform = config.get("platform", "pc")
    url = f"https://api.warframestat.us/{platform}/dailyDeals?language=en"
    data = get_json(url)
    if not isinstance(data, list) or not data:
        raise TrackerNotReady("Darvo API returned no deals; retrying next check.")

    parsed: list[tuple[dict[str, Any], datetime, datetime]] = []
    for deal in data:
        try:
            activation = parse_iso(deal["activation"])
            expiry = parse_iso(deal["expiry"])
        except (KeyError, TypeError, ValueError):
            continue
        parsed.append((deal, activation, expiry))

    active_deals = [entry for entry in parsed if entry[1] <= now < entry[2]]
    if not active_deals:
        raise TrackerNotReady("Darvo API has not published a current daily deal yet; retrying next check.")

    # Normally there is one current deal. If several exist, use the newest.
    deal, activation, expiry = max(active_deals, key=lambda x: x[1])
    api_id = deal.get("id") or f"{deal.get('item', 'unknown')}:{activation.isoformat()}"

    return Rotation(
        key=f"darvo:{api_id}",
        name="darvo",
        starts=activation,
        expires=expiry,
        payload={
            "item": deal.get("item", "Unknown item"),
            "original_price": deal.get("originalPrice", 0),
            "sale_price": deal.get("salePrice", 0),
            "discount": deal.get("discount", 0),
            "total": deal.get("total", 0),
            "sold": deal.get("sold", 0),
            "api_url": url,
        },
    )


def get_teshin(config: dict[str, Any], now: datetime) -> Rotation:
    platform = config.get("platform", "pc")
    url = f"https://api.warframestat.us/{platform}/steelPath?language=en"
    data = get_json(url)

    activation = parse_iso(data["activation"])
    expiry = parse_iso(data["expiry"])
    ensure_current(activation, expiry, now, "Steel Path")

    current = data.get("currentReward") or {}
    reward_name = current.get("name", "Unknown reward")
    reward_cost = current.get("cost", 0)
    rotation = data.get("rotation", []) or []
    evergreens = data.get("evergreens", []) or []

    next_reward: dict[str, Any] | None = None
    if rotation:
        current_index = next(
            (i for i, reward in enumerate(rotation) if reward.get("name") == reward_name),
            None,
        )
        if current_index is not None:
            next_reward = rotation[(current_index + 1) % len(rotation)]

    return Rotation(
        key=f"teshin:{activation.isoformat()}:{reward_name}:{reward_cost}",
        name="teshin",
        starts=activation,
        expires=expiry,
        payload={
            "reward": {"name": reward_name, "cost": reward_cost},
            "next_reward": next_reward,
            "evergreens": evergreens,
            "api_url": url,
        },
    )


# --------------------------------- Embeds -----------------------------------


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


def baro_embed(rotation: Rotation) -> dict[str, Any]:
    active = rotation.payload["active"]
    location = rotation.payload["location"]
    inventory = rotation.payload["inventory"]

    if not active:
        return {
            "title": "✨ Baro Ki'Teer — Not Here Yet",
            "description": f"Baro's next stop is **{location}**.",
            "color": COLORS["baro"],
            "fields": [
                {
                    "name": "Arrives",
                    "value": f"{discord_time(rotation.starts)}\n{discord_time(rotation.starts, 'F')}",
                    "inline": False,
                },
                {
                    "name": "Leaves",
                    "value": f"{discord_time(rotation.expires)}\n{discord_time(rotation.expires, 'F')}",
                    "inline": False,
                },
            ],
            "footer": {"text": "Automatic alerts post when Baro is active. This status appears on a forced manual push."},
        }

    lines = [
        f"• **{item['item']}** — 🪙 {fmt_num(item['ducats'])} Ducats • 💳 {fmt_num(item['credits'])} Credits"
        for item in inventory
    ]
    if not lines:
        lines = ["Inventory has not populated in the API yet. Pazuul will retry on the next check."]

    fields: list[dict[str, Any]] = []
    for i, chunk in enumerate(chunk_lines(lines), start=1):
        fields.append(
            {
                "name": "Inventory" if i == 1 else f"Inventory continued ({i})",
                "value": chunk,
                "inline": False,
            }
        )

    fields.append(
        {
            "name": "Leaves",
            "value": f"{discord_time(rotation.expires)}\n{discord_time(rotation.expires, 'F')}",
            "inline": False,
        }
    )

    return {
        "title": "✨ Baro Ki'Teer Has Arrived",
        "description": f"📍 **{location}**\n\n**{len(inventory)} item(s) available**",
        "color": COLORS["baro"],
        "fields": fields,
        "footer": {"text": "Live inventory: WarframeStat.us / WFCD"},
        "timestamp": rotation.starts.isoformat().replace("+00:00", "Z"),
    }


def darvo_embed(rotation: Rotation) -> dict[str, Any]:
    p = rotation.payload
    total = int(p.get("total") or 0)
    sold = int(p.get("sold") or 0)
    remaining = max(total - sold, 0)

    return {
        "title": "💰 Darvo's Daily Deal",
        "description": f"## {p['item']}\n**{fmt_num(p['discount'])}% OFF**",
        "color": COLORS["darvo"],
        "fields": [
            {
                "name": "Price",
                "value": f"~~{fmt_num(p['original_price'])} Platinum~~ → **{fmt_num(p['sale_price'])} Platinum**",
                "inline": False,
            },
            {
                "name": "Stock",
                "value": f"**{fmt_num(remaining)} / {fmt_num(total)}** remaining",
                "inline": True,
            },
            {
                "name": "Resets",
                "value": discord_time(rotation.expires),
                "inline": True,
            },
        ],
        "footer": {"text": "Live Darvo deal: WarframeStat.us / WFCD"},
        "timestamp": rotation.starts.isoformat().replace("+00:00", "Z"),
    }


def teshin_embed(rotation: Rotation, config: dict[str, Any]) -> dict[str, Any]:
    reward = rotation.payload["reward"]
    next_reward = rotation.payload.get("next_reward")
    evergreens = rotation.payload.get("evergreens", []) or []

    fields: list[dict[str, Any]] = [
        {
            "name": "Current weekly offering",
            "value": f"**{reward['name']}** — ⚙️ **{fmt_num(reward['cost'])} Steel Essence**",
            "inline": False,
        },
        {
            "name": "Resets",
            "value": f"{discord_time(rotation.expires)}\n{discord_time(rotation.expires, 'F')}",
            "inline": False,
        },
    ]

    if next_reward:
        fields.append(
            {
                "name": "Next in rotation",
                "value": f"**{next_reward.get('name', 'Unknown')}** — ⚙️ {fmt_num(next_reward.get('cost', 0))} Steel Essence",
                "inline": False,
            }
        )

    if config.get("teshin", {}).get("show_evergreens", True) and evergreens:
        lines = [
            f"• **{item.get('name', 'Unknown')}** — {fmt_num(item.get('cost', 0))} Steel Essence"
            for item in evergreens
        ]
        for i, chunk in enumerate(chunk_lines(lines), start=1):
            fields.append(
                {
                    "name": "Evergreen offerings" if i == 1 else f"Evergreens continued ({i})",
                    "value": chunk,
                    "inline": False,
                }
            )

    return {
        "title": "⚔️ Teshin — Steel Path Honors",
        "description": "The weekly Steel Path Honors rotation has updated.",
        "color": COLORS["teshin"],
        "fields": fields,
        "footer": {"text": "Live Steel Path data: WarframeStat.us / WFCD"},
        "timestamp": rotation.starts.isoformat().replace("+00:00", "Z"),
    }


def incarnon_embed(rotation: Rotation) -> dict[str, Any]:
    week = rotation.payload["week"]
    weapons = rotation.payload["weapons"]
    next_week = rotation.payload["next_week"]
    next_weapons = rotation.payload["next_weapons"]

    current_lines = "\n".join(f"• **{weapon} Incarnon Genesis**" for weapon in weapons)
    next_lines = ", ".join(next_weapons)

    return {
        "title": f"🌀 Steel Path Circuit — Incarnon Genesis Week {week}",
        "description": current_lines,
        "color": COLORS["incarnon"],
        "fields": [
            {
                "name": "Reward Path",
                "value": "Choose **2 of the 5** Incarnon Genesis adapters for this week's Steel Path Circuit reward path.",
                "inline": False,
            },
            {
                "name": "Next rotation",
                "value": f"{discord_time(rotation.expires)}\n{discord_time(rotation.expires, 'F')}",
                "inline": False,
            },
            {
                "name": f"Next week — Week {next_week}",
                "value": next_lines,
                "inline": False,
            },
        ],
        "footer": {
            "text": "Steel Path Circuit Incarnon Genesis • 9-week rotation • weekly reset at 00:00 UTC"
        },
        "timestamp": rotation.starts.isoformat().replace("+00:00", "Z"),
    }


# ------------------------------ Discord helpers -----------------------------


def build_message(config: dict[str, Any], embed: dict[str, Any], mention: str | None) -> dict[str, Any]:
    message: dict[str, Any] = {
        "username": config.get("discord_username", "Pazuul"),
        "embeds": [embed],
        "allowed_mentions": {"parse": []},
    }

    if mention:
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


def tracker_enabled(config: dict[str, Any], tracker: str) -> bool:
    section_name = "archon_hunt" if tracker == "archon" else tracker
    return bool(config.get(section_name, {}).get("enabled", True))


def build_tracker(
    tracker: str,
    config: dict[str, Any],
    now: datetime,
) -> tuple[Rotation, dict[str, Any]]:
    if tracker == "coda":
        rotation = get_coda_rotation(config, now)
        return rotation, coda_embed(rotation)
    if tracker == "bird3":
        rotation = get_bird3_rotation(config, now)
        return rotation, bird3_embed(rotation)
    if tracker == "archon":
        rotation = get_archon_hunt(config, now)
        return rotation, archon_embed(rotation)
    if tracker == "baro":
        rotation = get_baro(config, now)
        return rotation, baro_embed(rotation)
    if tracker == "darvo":
        rotation = get_darvo(config, now)
        return rotation, darvo_embed(rotation)
    if tracker == "teshin":
        rotation = get_teshin(config, now)
        return rotation, teshin_embed(rotation, config)
    if tracker == "incarnon":
        rotation = get_incarnon_rotation(config, now)
        return rotation, incarnon_embed(rotation)
    raise ValueError(f"Unknown tracker: {tracker}")


# ---------------------------------- Main ------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Post Warframe rotation/vendor changes to Discord.")
    parser.add_argument("--dry-run", action="store_true", help="Print Discord payloads instead of sending them.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Send selected trackers even if state says they were already sent. Intended for manual GitHub runs.",
    )
    parser.add_argument(
        "--only",
        choices=["all", *TRACKERS],
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

    selected = list(TRACKERS) if args.only == "all" else [args.only]
    jobs: list[tuple[str, Rotation, dict[str, Any]]] = []
    hard_errors: list[str] = []

    # Fetch/calculate each tracker independently so one delayed API endpoint
    # does not stop the other notifications from working.
    for tracker in selected:
        if not tracker_enabled(config, tracker):
            print(f"[{tracker}] disabled in config.json")
            continue
        try:
            rotation, embed = build_tracker(tracker, config, now)
            jobs.append((tracker, rotation, embed))
        except TrackerNotReady as exc:
            print(f"[{tracker}] {exc}")
        except Exception as exc:
            msg = f"[{tracker}] failed: {exc}"
            hard_errors.append(msg)
            print(msg, file=sys.stderr)

    sent = 0
    for tracker_name, rotation, embed in jobs:
        previous_key = state.get(tracker_name)
        changed = previous_key != rotation.key

        print(
            f"[{tracker_name}] current={rotation.key} previous={previous_key!r} "
            f"changed={changed} force={args.force}"
        )

        # Baro is special: automatic runs only notify when he is actually
        # present. A manual force push can still show his next arrival/status.
        if tracker_name == "baro" and not rotation.payload.get("active", False) and not args.force:
            print("[baro] inactive; waiting for arrival.")
            continue

        # If Baro is active but the upstream inventory has not populated yet,
        # wait rather than post an empty automatic alert.
        if (
            tracker_name == "baro"
            and rotation.payload.get("active", False)
            and not rotation.payload.get("inventory")
            and not args.force
        ):
            print("[baro] active but inventory is empty; retrying next check.")
            continue

        if not changed and not args.force:
            continue

        mention = tracker_mention(config, tracker_name)
        message = build_message(config, embed, mention)

        try:
            post_webhook(webhook, message, args.dry_run)
        except Exception as exc:
            print(f"Failed to post {tracker_name}: {exc}", file=sys.stderr)
            hard_errors.append(f"[{tracker_name}] Discord post failed: {exc}")
            continue

        sent += 1
        if not args.dry_run:
            state[tracker_name] = rotation.key

    if not args.dry_run and sent > 0:
        state["updated_at"] = now.isoformat().replace("+00:00", "Z")
        save_json(STATE_PATH, state)

    print(f"Done. Sent {sent} notification(s).")
    return 1 if hard_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
