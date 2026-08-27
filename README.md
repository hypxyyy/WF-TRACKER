Pazuul — Warframe Rotation Tracker

Pazuul is a lightweight Warframe tracker that runs through GitHub Actions and posts updates to Discord through a webhook.

Trackers

🦠 Technocyte Coda / Eleanor

Tracks the active Coda weapon batch and posts when the 4-day rotation changes.

🐦 Bird 3 Archon Shard

Tracks Bird 3's weekly Azure, Amber, or Crimson Archon Shard offering.

⚔️ Weekly Archon Hunt

Uses live Warframe data to show the current Archon, shard reward, three missions, nodes, and reset time.

✨ Baro Ki'Teer

Uses live Warframe data to show Baro's relay, full active inventory, Credit prices, Ducat prices, and departure time.

💰 Darvo's Daily Deal

Uses live Warframe data to show Darvo's item, discount, normal/sale Platinum price, stock, and reset time.

⚔️ Teshin — Steel Path Honors

Tracks the current Steel Path Honors reward, Steel Essence price, and optional evergreen offerings.

🌀 Steel Path Circuit — Incarnon Genesis

Tracks the 9-week Incarnon Genesis rotation and displays the five current choices plus next week's set.

🌙 Nightwave

Uses live Warframe data and posts the current Weekly Acts and Elite Weekly Acts.

The Discord embed title is always:

🌙 Nightwave

By default, daily Acts are disabled so Pazuul does not post a new Nightwave notification every day.

Nightwave settings in config.json:

"nightwave": {
  "enabled": true,
  "show_weekly": true,
  "show_elite_weekly": true,
  "show_daily": false
}

Discord Role Mentions

Role mentions are configured in config.json.

"mentions": {
  "all": "<@&YOUR_ROLE_ID>",
  "coda": "",
  "bird3": "",
  "archon": "",
  "baro": "",
  "darvo": "",
  "teshin": "",
  "incarnon": "",
  "nightwave": ""
}

A role in "all" is used for every tracker unless you assign a tracker-specific mention.

Discord Webhook

Store the webhook URL as a GitHub Actions repository secret named:

DISCORD_WEBHOOK

Path:

GitHub → Settings → Secrets and variables → Actions

Never put the webhook URL directly in the repository.

Repository Layout

WF-TRACKER/
├── .github/
│   └── workflows/
│       └── warframe-tracker.yml
├── data/
│   └── state.json
├── config.json
├── tracker.py
├── .gitignore
└── README.md

Automatic Checks

The workflow checks several times per hour:

- cron: "7,22,37,52 * * * *"

Pazuul only posts when it detects a new rotation or new live data.

data/state.json stores what has already been posted.

Do not replace or delete data/state.json when installing an update.

Manual Push

Go to:

GitHub → Actions → Warframe Rotation Tracker → Run workflow

Available trackers:

all
coda
bird3
archon
baro
darvo
teshin
incarnon
nightwave

For a manual Nightwave post choose:

only: nightwave
force: true

Scheduled runs never force-post. force = true only applies to manual GitHub Actions runs.

Installing This Upgrade

Replace these files:

tracker.py
config.json
.github/workflows/warframe-tracker.yml
README.md

Leave this file alone:

data/state.json

Runtime

actions/checkout@v7
actions/setup-python@v7
Python 3.12

Notes

Discord webhook username: Pazuul

The Nightwave tracker title is fixed to 🌙 Nightwave.

Nightwave Weekly and Elite Weekly Acts come from live Warframe world-state data.

Daily Acts are disabled by default to avoid notification spam.

Live Warframe APIs can take a little time to refresh immediately after resets.

Pazuul is an unofficial community project and is not affiliated with Digital Extremes, Warframe, Discord, GitHub, Genesis, or WFCD.
