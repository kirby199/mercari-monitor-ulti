"""Mercari Japan new-listing alerter.

Runs once per invocation (GitHub Actions calls it on a schedule):
  1. searches Mercari Japan for SEARCH_KEYWORD, newest first
  2. compares the results against seen.json
  3. emails every address in EMAIL_TO about listings it hasn't seen before
  4. saves the updated list of seen listing IDs

Environment variables:
  SMTP_USER   Gmail address used to SEND the alerts
  SMTP_PASS   Gmail "app password" for that address (NOT the normal password)
  EMAIL_TO    comma-separated recipient addresses
  DRY_RUN     set to 1 to print emails instead of sending them
"""

import asyncio
import html
import json
import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

from mercapi import Mercapi
from mercapi.requests import SearchRequestData

SEARCH_KEYWORD = "レリーフ 1st"
SEEN_FILE = Path(__file__).parent / "seen.json"
MAX_SEEN = 3000        # how many listing IDs to remember
MAX_ITEMS_PER_EMAIL = 40
ITEM_URL = "https://jp.mercari.com/en/item/{id}"
SEARCH_URL = (
    "https://jp.mercari.com/en/search?keyword=%E3%83%AC%E3%83%AA%E3%83%BC%E3%83%95%201st&sort=created_time&order=desc"
)


def load_seen():
    """Return (list_of_ids, first_run)."""
    if not SEEN_FILE.exists():
        return [], True
    try:
        data = json.loads(SEEN_FILE.read_text(encoding="utf-8"))
        return list(data.get("ids", [])), False
    except (json.JSONDecodeError, OSError):
        print("seen.json unreadable; treating as first run", file=sys.stderr)
        return [], True


def save_seen(ids):
    ids = ids[-MAX_SEEN:]
    SEEN_FILE.write_text(json.dumps({"ids": ids}, ensure_ascii=False), encoding="utf-8")


async def fetch_listings():
    m = Mercapi()
    results = await m.search(
        SEARCH_KEYWORD,
        sort_by=SearchRequestData.SortBy.SORT_CREATED_TIME,
        sort_order=SearchRequestData.SortOrder.ORDER_DESC,
    )
    listings = []
    for item in results.items:
        thumbs = getattr(item, "thumbnails", None) or []
        listings.append(
            {
                "id": str(getattr(item, "id_", None) or item.id),
                "name": str(item.name),
                "price": item.price,
                "thumb": thumbs[0] if thumbs else None,
            }
        )
    return listings


def yen(price):
    try:
        return f"¥{int(price):,}"
    except (TypeError, ValueError):
        return str(price)


def build_email(new_items, total_new):
    shown = new_items[:MAX_ITEMS_PER_EMAIL]
    n = total_new
    subject = (
        f"Mercari: new listing - {shown[0]['name'][:60]} ({yen(shown[0]['price'])})"
        if n == 1
        else f"Mercari: {n} new listings for {SEARCH_KEYWORD}"
    )

    text_lines = []
    html_rows = []
    for it in shown:
        url = ITEM_URL.format(id=it["id"])
        text_lines.append(f"{it['name']}\n  Price: {yen(it['price'])}\n  {url}\n")
        img = (
            f'<img src="{html.escape(str(it["thumb"]))}" width="80" '
            f'style="border-radius:4px;display:block">'
            if it["thumb"]
            else ""
        )
        html_rows.append(
            "<tr>"
            f'<td style="padding:8px;vertical-align:top">{img}</td>'
            f'<td style="padding:8px;vertical-align:top">'
            f'<a href="{url}" style="font-weight:bold;color:#1a56db;text-decoration:none">'
            f"{html.escape(it['name'])}</a><br>"
            f'<span style="font-size:16px">{html.escape(yen(it["price"]))}</span>'
            "</td></tr>"
        )

    extra = ""
    if total_new > len(shown):
        extra = f"\n...and {total_new - len(shown)} more. See: {SEARCH_URL}\n"

    text = "\n".join(text_lines) + extra + f"\nFull search: {SEARCH_URL}\n"
    html_body = (
        '<div style="font-family:Arial,sans-serif">'
        f"<p>{n} new listing{'s' if n != 1 else ''} on Mercari Japan for "
        f"<b>{html.escape(SEARCH_KEYWORD)}</b>:</p>"
        '<table cellspacing="0" cellpadding="0">' + "".join(html_rows) + "</table>"
        + (
            f"<p>...and {total_new - len(shown)} more.</p>"
            if total_new > len(shown)
            else ""
        )
        + f'<p><a href="{SEARCH_URL}">Open the full search</a></p></div>'
    )
    return subject, text, html_body


def send_email(subject, text, html_body):
    recipients = [a.strip() for a in os.environ.get("EMAIL_TO", "").split(",") if a.strip()]
    if os.environ.get("DRY_RUN") == "1":
        print(f"[DRY RUN] To: {recipients}\nSubject: {subject}\n\n{text}")
        return
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASS"]
    if not recipients:
        raise RuntimeError("EMAIL_TO is empty")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = ", ".join(recipients)
    msg.set_content(text)
    msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)
    print(f"Email sent to {recipients}")


def main():
    seen, first_run = load_seen()
    listings = asyncio.run(fetch_listings())
    if not listings:
        # An empty page is far more likely to be a blocked/failed request than
        # a genuinely empty search, so don't touch state.
        print("Search returned 0 listings; leaving state unchanged", file=sys.stderr)
        return 1

    seen_set = set(seen)
    new_items = [it for it in listings if it["id"] not in seen_set]
    print(f"Fetched {len(listings)} listings, {len(new_items)} new, first_run={first_run}")

    if first_run:
        # Don't email the whole existing backlog; just confirm the monitor works.
        send_email(
            "Mercari monitor is running",
            f"Monitoring Mercari Japan for {SEARCH_KEYWORD}.\n"
            f"{len(listings)} existing listings recorded; you'll be emailed about "
            f"anything newer.\n\n{SEARCH_URL}\n",
            f"<p>Monitoring Mercari Japan for <b>{html.escape(SEARCH_KEYWORD)}</b>.<br>"
            f"{len(listings)} existing listings recorded; you'll be emailed about "
            f"anything newer.</p><p><a href='{SEARCH_URL}'>Open the search</a></p>",
        )
    elif new_items:
        subject, text, html_body = build_email(new_items, len(new_items))
        send_email(subject, text, html_body)  # raises on failure -> state not saved -> retried

    # Oldest first so the newest IDs sit at the end and survive trimming.
    merged = seen + [it["id"] for it in reversed(listings) if it["id"] not in seen_set]
    save_seen(merged)
    return 0


if __name__ == "__main__":
    sys.exit(main())
