#!/usr/bin/env python3
"""Watchdog for the Xavier AI Club site and sign-up form.

Usage:  python3 healthcheck.py [--report report.md]
Exit 0 when everything is up, 1 when anything is down (the report says what).

A page only counts as up if it returns 200 AND still contains the text that proves
it is the right page. A 200 with a blank or wrong page is a failure too.
Runs from GitHub Actions every hour (see .github/workflows/watchdog.yml in the
Pages repo) and by hand from any session.
"""
import argparse
import sys
import time
import urllib.error
import urllib.request

SITE = "https://doshi123456789.github.io/xavier-ai-club/"
FORM = "https://docs.google.com/forms/d/e/1FAIpQLSfqbNDx-KuUZGUqxHl-kp91mAG4DBzC7D0R6YPLR2PbuuD87A/viewform"

CHECKS = [
    {"name": "Home", "url": SITE, "must_contain": ["Xavier AI Club", "volunteer/"]},
    {"name": "Join page (poster QR)", "url": SITE + "join/",
     "must_contain": ["Join the AI Club", "1FAIpQLSfqbNDx"]},
    {"name": "Volunteer map (poster QR)", "url": SITE + "volunteer/",
     "must_contain": ["Where to Volunteer in NYC"]},
    {"name": "AI scoreboard", "url": SITE + "models/",
     "must_contain": ["AI models, compared", "Claude Fable 5.1", "Higgsfield"]},
    {"name": "Sign-up form", "url": FORM,
     "must_contain": ["Join the Xavier AI Club", "community service hours"],
     "must_not_contain": ["no longer accepting responses"]},
]
SIMULATED_OUTAGE = {"name": "Simulated outage (test only)", "url": SITE + "watchdog-test-page-that-does-not-exist/",
                    "must_contain": ["never"]}
ATTEMPTS = 3
RETRY_SECONDS = 20
TIMEOUT_SECONDS = 30


def judge(check, status, body):
    """Return None when the check passes, else a one-line reason."""
    if status is None:
        return f"could not connect ({body})"
    if status != 200:
        return f"HTTP {status}"
    missing = [text for text in check["must_contain"] if text not in body]
    if missing:
        return "page loads but is missing: " + ", ".join(repr(m) for m in missing)
    bad = [text for text in check.get("must_not_contain", []) if text in body]
    if bad:
        return "page says: " + ", ".join(repr(b) for b in bad)
    return None


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "xavier-ai-club-watchdog/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        return err.code, ""
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        return None, str(err)


def run_check(check):
    """Retry before calling something down, so one network blip isn't an outage."""
    reason = None
    for attempt in range(ATTEMPTS):
        reason = judge(check, *fetch(check["url"]))
        if reason is None:
            return None
        if attempt < ATTEMPTS - 1:
            time.sleep(RETRY_SECONDS)
    return reason


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", help="write a markdown report to this file")
    parser.add_argument("--simulate-failure", action="store_true",
                        help="add a check that is guaranteed to fail (tests the alert path)")
    args = parser.parse_args()

    checks = CHECKS + ([SIMULATED_OUTAGE] if args.simulate_failure else [])
    failures = []
    for check in checks:
        reason = run_check(check)
        print(f"{'OK  ' if reason is None else 'DOWN'} {check['name']}: {check['url']}"
              + ("" if reason is None else f" -> {reason}"))
        if reason:
            failures.append((check, reason))

    if args.report:
        lines = [f"- **{c['name']}** {c['url']}: {r}" for c, r in failures] or ["All checks passed."]
        with open(args.report, "w") as out:
            out.write("\n".join(lines) + "\n")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
