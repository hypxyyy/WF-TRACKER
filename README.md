Pazuul — Warframe Rotation Tracker

Pazuul is a lightweight Warframe rotation tracker that runs with GitHub Actions and posts updates to Discord through a webhook.

It is designed to run alongside Genesis and automatically track several Warframe rotations without requiring you to keep a PC or server online.

Tracked Rotations

🦠 Technocyte Coda / Eleanor

Tracks the active Coda weapon batch.

Alternates between Batch A and Batch B.

Rotates every 96 hours.

Posts only when the rotation changes.

Can also be manually pushed from GitHub Actions.

🐦 Bird 3 Archon Shard

Tracks Bird 3's weekly Archon Shard.

Rotates between:

Azure Archon Shard

Amber Archon Shard

Crimson Archon Shard

Updates on the weekly reset.

Posts only when the shard changes.

⚔️ Weekly Archon Hunt

Pulls the current Archon Hunt from live Warframe data.

Displays:

Current Archon

Archon Shard reward

Mission 1

Mission 2

Mission 3

Mission nodes

Hunt expiration/reset time

Ignores expired Archon Hunt data while waiting for the live source to refresh.

✨ Baro Ki'Teer

Tracks Baro Ki'Teer.

When Baro is active, Pazuul can show:

Relay/location

Full inventory

Credit prices

Ducat prices

Departure time

Automatic notifications are protected from duplicate posts.

Baro can also be manually pushed from GitHub Actions.

⚔️ Teshin — Steel Path Honors

Tracks Teshin's weekly Steel Path offering.

Displays the current rotating reward.

Shows the Steel Essence cost.

Can optionally show evergreen Steel Path offerings.

Posts when the weekly reward changes.

Discord Role Mentions

Role mentions are configured in config.json.

Example:

"mentions": {
  "all": "<@&YOUR_ROLE_ID>",
  "coda": "",
  "bird3": "",
  "archon": "",
  "baro": "",
  "teshin": ""
}

Putting a role mention under "all" will ping that role for every tracker notification.

You can also remove the "all" mention and assign different Discord roles to individual trackers.

Discord role mention format:

<@&ROLE_ID>

Discord Webhook

Create a Discord webhook in the channel where you want Pazuul to post.

In Discord:

Open the channel settings.

Go to Integrations.

Open Webhooks.

Create a new webhook.

Copy the webhook URL.

Do not put the webhook URL directly in the repository.

In GitHub:

Open the repository.

Go to Settings.

Open Secrets and variables → Actions.

Create a repository secret named:

DISCORD_WEBHOOK

Paste the Discord webhook URL as the secret value.

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

Automatic Updates

The GitHub Actions workflow checks for changes several times per hour.

Current schedule:

- cron: "7,22,37,52 * * * *"

This checks at approximately:

:07
:22
:37
:52

of every hour.

GitHub Actions schedules use UTC and may occasionally start a few minutes late.

Pazuul uses data/state.json to remember what it has already posted so the same rotation is not repeatedly sent to Discord.

Do not delete data/state.json unless you intentionally want to reset the tracker's saved state.

Manual Push

You can manually push any current tracker status to Discord.

Go to:

GitHub → Actions → Warframe Rotation Tracker → Run workflow

Available trackers:

all
coda
bird3
archon
baro
teshin

Choose the tracker you want.

To post it even if that rotation has already been sent, enable:

force = true

The force option only applies to manual workflow runs. Scheduled runs do not force duplicate notifications.

Pazuul Discord Name

The webhook username can be configured in config.json:

"discord_username": "Pazuul"

If the tracker does not override the webhook username, you can also rename the webhook itself to Pazuul from Discord's webhook settings.

Configuration

The main settings are stored in:

config.json

Example structure:

{
  "platform": "pc",
  "discord_username": "Pazuul",

  "mentions": {
    "all": "",
    "coda": "",
    "bird3": "",
    "archon": "",
    "baro": "",
    "teshin": ""
  },

  "coda": {
    "enabled": true
  },

  "bird3": {
    "enabled": true
  },

  "archon_hunt": {
    "enabled": true
  },

  "baro": {
    "enabled": true
  },

  "teshin": {
    "enabled": true,
    "show_evergreens": true
  }
}

GitHub Actions

The workflow is stored at:

.github/workflows/warframe-tracker.yml

It handles:

Automatic scheduled checks

Manual runs

Optional manual force-posting

Saving tracker state

Running the Python tracker

The workflow uses:

actions/checkout@v7
actions/setup-python@v7
Python 3.12

Important Notes

Keep DISCORD_WEBHOOK stored as a GitHub secret.

Never post your Discord webhook URL publicly.

Keep data/state.json so duplicate protection continues working.

Live Warframe data can occasionally take time to update immediately after a reset.

If the Archon Hunt API still reports an expired hunt, Pazuul waits for fresh data instead of posting the expired hunt.

Manual force = true reposts the current information but does not make an external Warframe data source refresh sooner.

Disclaimer

Pazuul is an unofficial community project and is not affiliated with Digital Extremes, Warframe, Discord, Genesis, GitHub, or WFCD.
