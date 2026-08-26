Pazuul — Warframe Rotation Tracker

Pazuul is a lightweight Warframe tracker that runs through GitHub Actions and sends updates to Discord with a webhook. Your computer does not need to stay on.

What Pazuul Tracks

🦠 Technocyte Coda / Eleanor

Tracks the active Coda weapon batch.

Alternates between Batch A and Batch B every 96 hours.

Posts only when the rotation changes.

Supports manual force-posts.

🐦 Bird 3 Archon Shard

Tracks Bird 3's weekly Archon Shard.

Rotates between Azure, Amber, and Crimson.

Updates at the weekly reset.

⚔️ Weekly Archon Hunt

Uses live Warframe data.

Shows the current Archon, shard reward, all three missions, nodes, and reset time.

Ignores expired API data while waiting for a fresh weekly hunt.

✨ Baro Ki'Teer

Uses live Warframe data.

Shows his relay/location and full inventory when active.

Shows Credit and Ducat prices.

Shows his departure time.

A manual force-post can show his upcoming arrival when he is away.

💰 Darvo's Daily Deal

Uses live Warframe data.

Shows the item, discount, original price, sale price, stock remaining, and reset time.

Posts when the current deal changes.

⚔️ Teshin — Steel Path Honors

Uses live Warframe data.

Shows the current weekly Steel Path reward and Steel Essence cost.

Can show the next reward and evergreen offerings.

🌀 Steel Path Circuit — Incarnon Genesis

Tracks the current 9-week Incarnon Genesis rotation.

Shows all five adapters available that week.

Shows the next week's rotation.

Updates at the weekly reset.

The schedule is anchored to Week 9 beginning June 22, 2026 at 00:00 UTC.

Current Incarnon Rotation Schedule

Week

Incarnon Genesis choices

1

Braton, Lato, Skana, Paris, Kunai

2

Boar, Gammacor, Angstrum, Gorgon, Anku

3

Bo, Latron, Furis, Furax, Strun

4

Lex, Magistar, Boltor, Bronco, Ceramic Dagger

5

Torid, Dual Toxocyst, Dual Ichor, Miter, Atomos

6

Ack & Brunt, Soma, Vasto, Nami Solo, Burston

7

Zylok, Sibear, Dread, Despair, Hate

8

Dera, Sybaris, Cestra, Sicarus, Okina

9

Vectis, Stug, Ballistica, Destreza, Obex

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

Discord Webhook

Store your webhook in:

GitHub → Settings → Secrets and variables → Actions

The repository secret must be named exactly:

DISCORD_WEBHOOK

Do not put your webhook URL directly in the code.

Discord Role Pings

Role pings are controlled in config.json.

"mentions": {
  "all": "<@&YOUR_ROLE_ID>",
  "coda": "",
  "bird3": "",
  "archon": "",
  "baro": "",
  "darvo": "",
  "teshin": "",
  "incarnon": ""
}

Putting a role under "all" pings that role for every Pazuul update.

Discord role mention format:

<@&ROLE_ID>

Automatic Checks

Pazuul checks several times per hour:

- cron: "7,22,37,52 * * * *"

Scheduled runs never force-post duplicate information.

data/state.json remembers what Pazuul has already posted.

Leave data/state.json alone when updating Pazuul.

Manual Push

Go to:

GitHub → Actions → Warframe Rotation Tracker → Run workflow

Available choices:

all
coda
bird3
archon
baro
darvo
teshin
incarnon

Set:

force = true

to manually repost the selected current tracker even if it was already posted.

The force option is only honored on manual workflow runs.

Updating These Files

When installing this Incarnon upgrade, replace:

tracker.py
config.json
.github/workflows/warframe-tracker.yml
README.md

Do not replace:

data/state.json

Keeping state.json preserves duplicate protection for your existing trackers.

Runtime

The workflow uses:

actions/checkout@v7
actions/setup-python@v7
Python 3.12

Notes

Pazuul's Discord webhook username is set to Pazuul in config.json.

Live vendor/world-state data can occasionally update a little after the actual in-game reset.

Manual force-posting does not force an upstream Warframe API to refresh.

Pazuul is an unofficial community project and is not affiliated with Digital Extremes, Warframe, Discord, GitHub, Genesis, or WFCD.
