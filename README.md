# Warframe Discord Rotation Tracker

A small GitHub Actions + Discord webhook tracker that works alongside Genesis.

It posts only when a rotation changes:

- **Eleanor / Technocyte Coda weapons** — Batch A/B every 4 days at 00:00 UTC.
- **Bird 3 weekly Archon Shard** — Azure / Amber / Crimson every Monday at 00:00 UTC.
- **Weekly Archon Hunt** — fetched live from WarframeStat.us, including boss, shard color, and all 3 missions.

No paid server is required. GitHub Actions checks once per hour and `data/state.json` prevents duplicate notifications.

## 1. Create the Discord webhook

In Discord:

1. Open the channel you want the alerts in.
2. **Edit Channel → Integrations → Webhooks → New Webhook**.
3. Name it something like `Warframe Rotation Tracker`.
4. Copy the webhook URL.

**Keep the webhook URL private.** Anyone with it can post to that channel.

## 2. Upload this project to GitHub

Create a **private** GitHub repository, for example:

`warframe-rotation-tracker`

Upload everything in this folder, including the hidden `.github` folder.

## 3. Add the webhook as a GitHub secret

In the repository:

**Settings → Secrets and variables → Actions → New repository secret**

Name:

`DISCORD_WEBHOOK`

Value:

Paste your Discord webhook URL.

## 4. Test it

Go to:

**Actions → Warframe Rotation Tracker → Run workflow**

Choose:

- `only: all`
- `force: true`

Then press **Run workflow**.

That forces one test message for Coda, Bird 3, and the Archon Hunt.

Afterward, leave `force` off. The scheduled job checks hourly and only posts when it sees a new rotation.

## What the alerts look like

### Coda

The Coda embed shows the active batch and every available weapon, plus Discord's live countdown to the next rotation.

The tracker follows this cycle:

**Batch A**
- Coda Hema
- Coda Sporothrix
- Coda Catabolyst
- Coda Pox
- Dual Coda Torxica
- Coda Mire
- Coda Motovore

**Batch B**
- Coda Bassocyst
- Coda Bubonico
- Coda Synapse
- Coda Tysis
- Coda Caustacyst
- Coda Hirudo
- Coda Pathocyst

Important: the bot tracks which **weapons** are in Eleanor's current batch. The individual **Valence element and percentage rolls are generated in-game** and are not exposed by the WarframeStat.us Archon/world-state endpoint used by this project, so the embed tells players to check Eleanor for those rolls.

### Bird 3

The Bird 3 embed shows the current normal Archon Shard for **30,000 Cavia Standing** and the next Monday reset.

### Archon Hunt

The Archon Hunt is **live**, not calculated from a fixed schedule. The tracker requests:

`https://api.warframestat.us/pc/archonHunt`

It posts:

- Current Archon boss
- Corresponding shard color
- Mission 1 + node
- Mission 2 + node
- Mission 3 + node
- Expiry/reset time

Boss-to-shard mapping:

- Archon Amar → Crimson Archon Shard
- Archon Nira → Amber Archon Shard
- Archon Boreal → Azure Archon Shard

## Optional Discord role ping

If you want a role ping such as `@Warframe Alerts`, get the role ID and edit `config.json`.

Example:

```json
"mentions": {
  "all": "<@&123456789012345678>",
  "coda": "",
  "bird3": "",
  "archon": ""
}
```

Using `all` pings the role for all three trackers. Or leave `all` blank and put a role mention under only the tracker you want.

To get a Discord role ID, enable Developer Mode in Discord, right-click the role, and choose **Copy Role ID**.

## Run locally without posting

Python 3.11+ is enough; there are no third-party dependencies.

```bash
python tracker.py --dry-run --force
```

Run only one tracker:

```bash
python tracker.py --dry-run --force --only archon
python tracker.py --dry-run --force --only coda
python tracker.py --dry-run --force --only bird3
```

To actually post locally, set the environment variable first:

macOS/Linux:

```bash
export DISCORD_WEBHOOK='YOUR_WEBHOOK_URL'
python tracker.py --force
```

PowerShell:

```powershell
$env:DISCORD_WEBHOOK='YOUR_WEBHOOK_URL'
python tracker.py --force
```

## How duplicate prevention works

After a successful post, the tracker writes the rotation key to:

`data/state.json`

The GitHub workflow commits that file back to the repository. On the next hourly check, the same rotation is skipped.

If Discord rejects a webhook post or the live Archon API fails, the state is not advanced for that notification, so the tracker can retry on the next run.

## If Digital Extremes forces a Coda rotation

DE has manually forced Eleanor's store to rotate before. If they ever do that again and it permanently changes the 4-day phase, update:

```json
"reference_utc": "YYYY-MM-DDT00:00:00Z"
```

under `coda` in `config.json`, and make the first item in `order` match the batch active on that reference date.

## Rotation references used by this project

The current reference points/order were taken from the open-source Warframe Task Checklist cycle data:

- Coda reference: `2025-03-18`, alternating the two weapon groups every 4 days.
- Bird 3 reference: `2026-01-12`, order Azure → Amber → Crimson weekly.

The weekly Archon Hunt does not rely on that table; it comes directly from WarframeStat.us/WFCD every time the action runs.

## Files

```text
warframe-rotation-tracker/
├── .github/
│   └── workflows/
│       └── warframe-tracker.yml
├── data/
│   └── state.json
├── config.json
├── tracker.py
├── .gitignore
└── README.md
```

## Notes

- GitHub scheduled workflows can occasionally start a few minutes late. The job checks hourly, so it will catch the new rotation on the next run if necessary.
- Keep the repo private if you prefer, but the webhook itself is stored only as a GitHub secret and is never written into the code.
- This is an unofficial community tool and is not affiliated with Digital Extremes, Discord, Genesis, or WFCD.
