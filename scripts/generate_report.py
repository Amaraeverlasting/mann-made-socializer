#!/usr/bin/env python3
"""
generate_report.py - Generate weekly social media report for a client.

Usage:
  python3 generate_report.py --client the-exponentials --week 2026-W11
  python3 generate_report.py --client mic-mann
  python3 generate_report.py --client mann-made --week 2026-W10 --email
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).parent.parent
CLIENTS_DIR = BASE / "clients"
REPORTS_DIR = BASE / "reports"


def load_client(client_id: str) -> dict:
    f = CLIENTS_DIR / f"{client_id}.json"
    if not f.exists():
        print(f"ERROR: Client '{client_id}' not found", file=sys.stderr)
        sys.exit(1)
    return json.loads(f.read_text())


def load_queue(client_id: str) -> list:
    qf = CLIENTS_DIR / client_id / "queue.json"
    if qf.exists():
        try:
            return json.loads(qf.read_text())
        except Exception:
            return []
    return []


def parse_week(week_str: str):
    """Parse ISO week string like '2026-W11' and return (start_date, end_date)."""
    try:
        # Python's %G-%V-%u: ISO year, ISO week, weekday
        start = datetime.strptime(f"{week_str}-1", "%G-W%V-%u")
        end = start + timedelta(days=6)
        return start, end
    except Exception as e:
        print(f"ERROR: Cannot parse week '{week_str}': {e}", file=sys.stderr)
        sys.exit(1)


def current_week() -> str:
    now = datetime.now()
    iso = now.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


PLATFORM_ICONS = {
    "x": "X",
    "linkedin": "LinkedIn",
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "youtube": "YouTube",
    "facebook": "Facebook",
}


def generate_report(client_id: str, week_str: str, send_email: bool = False) -> str:
    cfg = load_client(client_id)
    name = cfg.get("name", client_id)
    queue = load_queue(client_id)

    start, end = parse_week(week_str)
    start_str = start.strftime("%B %d")
    end_str = end.strftime("%B %d, %Y")

    # Filter posts for this week
    def in_week(item):
        dt_str = item.get("posted_at") or item.get("scheduled") or ""
        if not dt_str:
            return False
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            return start.date() <= dt.date() <= end.date()
        except Exception:
            return False

    week_posts = [i for i in queue if in_week(i)]
    posted_this_week = [i for i in week_posts if i.get("status") == "posted"]
    pending_this_week = [i for i in week_posts if i.get("status") == "pending"]
    failed_this_week = [i for i in week_posts if i.get("status") == "failed"]

    # Next week items (scheduled but not posted)
    next_week_start = end + timedelta(days=1)
    next_week_end = next_week_start + timedelta(days=6)

    def in_next_week(item):
        dt_str = item.get("scheduled") or ""
        if not dt_str:
            return False
        try:
            dt = datetime.fromisoformat(dt_str)
            return next_week_start.date() <= dt.date() <= next_week_end.date()
        except Exception:
            return False

    next_week_items = [i for i in queue if i.get("status") == "pending" and in_next_week(i)]

    # Count by platform
    by_platform = {}
    for item in posted_this_week:
        for p in (item.get("platforms") or []):
            by_platform[p] = by_platform.get(p, 0) + 1

    platform_summary = ", ".join(
        f"{PLATFORM_ICONS.get(p, p)}: {count}"
        for p, count in by_platform.items()
    ) if by_platform else "None"

    # Total platform slots enabled
    enabled_platforms = [p for p, v in cfg.get("platforms", {}).items() if v.get("enabled")]

    # Build report
    lines = [
        f"# {name} - Weekly Social Report",
        f"Week of {start_str}-{end_str.split(',')[0]}, {end.year}",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- Posts published: {len(posted_this_week)}" + (f" ({platform_summary})" if by_platform else ""),
        f"- Posts pending/scheduled: {len(pending_this_week)}",
        f"- Failed posts: {len(failed_this_week)}",
        f"- Active platforms: {', '.join(PLATFORM_ICONS.get(p, p) for p in enabled_platforms)}",
        "",
    ]

    # Posts this week
    lines.append("## Posts This Week")
    lines.append("")
    if posted_this_week:
        for item in sorted(posted_this_week, key=lambda x: x.get("posted_at") or ""):
            platforms_str = ", ".join(PLATFORM_ICONS.get(p, p) for p in (item.get("platforms") or []))
            posted_at = ""
            if item.get("posted_at"):
                try:
                    dt = datetime.fromisoformat(item["posted_at"])
                    posted_at = dt.strftime("%a %b %d, %H:%M")
                except Exception:
                    posted_at = item["posted_at"]
            caption = (item.get("caption") or "")[:100]
            if len(item.get("caption") or "") > 100:
                caption += "..."
            lines.append(f"- **{platforms_str}** | {posted_at}")
            lines.append(f"  {item.get('filename', '')} - {caption}")
    else:
        lines.append("_No posts published this week._")
    lines.append("")

    # Failed posts
    if failed_this_week:
        lines.append("## Failed Posts")
        lines.append("")
        for item in failed_this_week:
            platforms_str = ", ".join(PLATFORM_ICONS.get(p, p) for p in (item.get("platforms") or []))
            error = item.get("error") or "unknown error"
            lines.append(f"- **{platforms_str}** | {item.get('filename', '')} - Error: {error}")
        lines.append("")

    # Next week queue
    lines.append("## Next Week Queue")
    lines.append("")
    if next_week_items:
        for item in sorted(next_week_items, key=lambda x: x.get("scheduled") or ""):
            platforms_str = ", ".join(PLATFORM_ICONS.get(p, p) for p in (item.get("platforms") or []))
            scheduled = item.get("scheduled", "")
            if scheduled:
                try:
                    dt = datetime.fromisoformat(scheduled)
                    scheduled = dt.strftime("%a %b %d, %H:%M")
                except Exception:
                    pass
            caption = (item.get("caption") or "")[:80]
            if len(item.get("caption") or "") > 80:
                caption += "..."
            lines.append(f"- **{platforms_str}** | {scheduled}")
            lines.append(f"  {item.get('filename', '')} - {caption}")
    else:
        # Show pending items without specific schedule
        pending_unscheduled = [i for i in queue if i.get("status") == "pending" and not in_next_week(i)][:5]
        if pending_unscheduled:
            lines.append(f"_(Showing next {len(pending_unscheduled)} pending items without specific schedule)_")
            for item in pending_unscheduled:
                platforms_str = ", ".join(PLATFORM_ICONS.get(p, p) for p in (item.get("platforms") or []))
                caption = (item.get("caption") or "")[:80]
                lines.append(f"- **{platforms_str}** | {item.get('filename', '')}")
                if caption:
                    lines.append(f"  {caption}")
        else:
            lines.append("_No content scheduled for next week yet._")
    lines.append("")

    # Platform breakdown
    lines.append("## Platform Breakdown")
    lines.append("")
    for platform in enabled_platforms:
        pdata = cfg["platforms"][platform]
        count = by_platform.get(platform, 0)
        handle = pdata.get("handle", "")
        post_times = ", ".join(pdata.get("post_times", []))
        lines.append(f"- **{PLATFORM_ICONS.get(platform, platform)}** {handle}: {count} posts this week | Schedule: {post_times or 'not set'}")
    lines.append("")

    # Footer
    report_email = cfg.get("reporting", {}).get("email", "")
    lines.append("---")
    lines.append(f"_Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | {name}_")
    if report_email:
        lines.append(f"_Report sent to: {report_email}_")

    report_text = "\n".join(lines)

    # Save report to file
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORTS_DIR / f"{client_id}_{week_str}.md"
    report_file.write_text(report_text)
    print(f"Report saved to: {report_file}")

    # Send email if requested
    if send_email and report_email:
        send_report_email(name, report_email, week_str, report_text)

    return report_text


def send_report_email(client_name: str, to_email: str, week_str: str, report_text: str):
    """Send report via email (uses system mail or SMTP if configured)."""
    subject = f"{client_name} - Weekly Social Report {week_str}"
    try:
        import smtplib
        from email.mime.text import MIMEText
        import os

        smtp_host = os.environ.get("SMTP_HOST", "")
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        smtp_user = os.environ.get("SMTP_USER", "")
        smtp_pass = os.environ.get("SMTP_PASS", "")
        from_email = os.environ.get("SMTP_FROM", smtp_user)

        if not smtp_host or not smtp_user:
            print("WARNING: SMTP not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASS, SMTP_FROM env vars.")
            print(f"Would have sent to: {to_email}")
            print(f"Subject: {subject}")
            return

        msg = MIMEText(report_text, "plain")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        print(f"Report emailed to {to_email}")
    except Exception as e:
        print(f"WARNING: Failed to send email: {e}")


def main():
    parser = argparse.ArgumentParser(description="Generate weekly social media report")
    parser.add_argument("--client", required=True, help="Client ID (e.g. mic-mann)")
    parser.add_argument("--week", default="", help="ISO week string e.g. 2026-W11 (default: current week)")
    parser.add_argument("--email", action="store_true", help="Send report to client email")
    parser.add_argument("--print", action="store_true", help="Print report to stdout")
    args = parser.parse_args()

    week = args.week or current_week()
    report = generate_report(args.client, week, send_email=args.email)

    if args.print or not args.email:
        print("\n" + "=" * 60)
        print(report)
        print("=" * 60)


if __name__ == "__main__":
    main()
