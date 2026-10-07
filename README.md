# Mercari Japan new-listing alerts

Checks Mercari Japan for **旧アジア** (newest first) every ~10 minutes on GitHub's
servers and emails roy.yn.zhang@gmail.com and ryan-sho@hotmail.co.uk with the
name, price and link of each new listing. Free, and your computer can be off.

## Setup (about 10 minutes)

### 1. Get a Gmail app password (this is the account that SENDS the alerts)
1. Turn on 2-Step Verification: https://myaccount.google.com/security
2. Create an app password: https://myaccount.google.com/apppasswords
3. Copy the 16-character password.

You can use either of your Gmail addresses as the sender. Alerts will come
from it and go to both recipients.

### 2. Create the GitHub repo
1. Sign up/log in at https://github.com and click **New repository**.
2. Name it e.g. `mercari-monitor` and choose **Public** (see note below).
3. Upload everything in this folder, including the hidden `.github` folder
   (easiest: on the repo page choose *Add file → Upload files* and drag the
   whole folder contents in).

### 3. Add the secrets
Repo → **Settings → Secrets and variables → Actions → New repository secret**.
Add three:

| Name        | Value                                                        |
|-------------|--------------------------------------------------------------|
| `SMTP_USER` | the Gmail address that sends the alerts                      |
| `SMTP_PASS` | the 16-character app password (no spaces)                    |
| `EMAIL_TO`  | `roy.yn.zhang@gmail.com,ryan-sho@hotmail.co.uk`              |

### 4. Start it
Repo → **Actions** tab → enable workflows if prompted → **Mercari monitor** →
**Run workflow**. The first run emails a "Mercari monitor is running"
confirmation and records the current listings as already seen. After that you
only get emails for genuinely new ones. Check spam the first time, especially
on the Hotmail address.

## Things to know

- **Cost:** public repos get unlimited free Actions minutes. A private repo
  only gets 2,000 free minutes/month, which a 10-minute schedule would exceed;
  if you go private, change the cron to `*/30 * * * *`.
- **Public repo privacy:** your email addresses and password are in encrypted
  secrets, not visible. The repo will show the search keyword and the list of
  seen listing IDs.
- **Timing:** GitHub's scheduler is best-effort; runs can be delayed by
  5-15 minutes at busy times. Not suitable for sniping, fine for awareness.
- **Inactivity:** GitHub pauses scheduled workflows on repos with no activity
  for 60 days. The monitor commits to the repo whenever new listings appear,
  which normally keeps it alive. If you get a notice, press Run workflow.
- **Failures:** if Mercari blocks GitHub's servers or changes its API, the run
  fails and GitHub emails you. Updating the `mercapi` library often fixes it.
- **Changing the search:** edit `SEARCH_KEYWORD` in `monitor.py`.
