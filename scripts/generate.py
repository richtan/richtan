#!/usr/bin/env python3
"""Fetch GitHub profile data, render text art, and update README.md."""

import hashlib
import os
import re
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone

from github_api import fetch_profile_data, fetch_username
from render_activity import render_activity
from render_graph import render_graph
from render_pinned import render_pinned, visual_len

MARKER_START = "<!-- PROFILE START -->"
MARKER_END = "<!-- PROFILE END -->"
README_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "README.md")


def sanitize(text):
    """Strip null bytes, control chars, and replace tabs with spaces."""
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = text.replace("\t", "    ")
    return text


def validate_output(lines):
    """Basic validation of generated output."""
    text = "\n".join(lines)
    if not text.strip():
        print("WARNING: Generated output is empty")
        return False
    return True


def main():
    token = os.environ.get("GITHUB_TOKEN")

    if not token:
        sys.exit("GITHUB_TOKEN not set")

    username = os.environ.get("GITHUB_USERNAME", "").strip() or fetch_username(token)

    # Fetch data
    data = fetch_profile_data(token, username)
    user = data["user"]
    contributions = user["contributionsCollection"]

    # Filter private repos from pinned items
    pinned_repos = [
        r for r in user["pinnedItems"]["nodes"]
        if not r.get("isPrivate", False)
    ]

    # Fall back to popular repos when nothing is pinned
    if not pinned_repos:
        pinned_repos = user.get("repositories", {}).get("nodes", [])

    # Sanitize dynamic text
    for repo in pinned_repos:
        repo["description"] = sanitize(repo.get("description") or "No description")
        repo["name"] = sanitize(repo.get("name", ""))
        repo["nameWithOwner"] = sanitize(repo.get("nameWithOwner", ""))
        if repo.get("parent") and repo["parent"].get("nameWithOwner"):
            repo["parent"]["nameWithOwner"] = sanitize(repo["parent"]["nameWithOwner"])

    # Render sections
    print("Rendering pinned repos...")
    pinned_lines = render_pinned(pinned_repos, username)

    print("Rendering contribution graph...")
    graph_lines = render_graph(contributions)

    print("Rendering activity timeline...")
    activity_lines = render_activity(contributions)

    # Combine
    output_lines = []
    if pinned_lines:
        output_lines.extend(pinned_lines)
        output_lines.append("")
    output_lines.extend(graph_lines)
    output_lines.extend(activity_lines)

    # Add timestamp
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%d %H:%M UTC")
    output_lines.append("")
    output_lines.append(f"<b>Last updated: {timestamp}</b>")

    # Validate
    if not validate_output(output_lines):
        sys.exit("Output validation failed")

    # Verify line widths
    for i, line in enumerate(output_lines):
        vl = visual_len(line)
        if vl > 80:
            print(f"WARNING: Line {i+1} is {vl} visual chars (max 80): {line[:60]}...")

    # Build the full <pre> block
    content = "\n".join(output_lines)
    rendered = f"<pre>{content}\n</pre>"

    # Hash check (hash of rendered content, excluding hash comment itself)
    new_hash = hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:16]

    # Read existing README
    print(f"Reading {README_PATH}...")
    try:
        with open(README_PATH, "r", encoding="utf-8") as f:
            readme = f.read()
    except FileNotFoundError:
        sys.exit(f"README not found: {README_PATH}")

    # Validate markers exist
    if MARKER_START not in readme:
        sys.exit(f"Marker not found: {MARKER_START}")
    if MARKER_END not in readme:
        sys.exit(f"Marker not found: {MARKER_END}")

    # Check existing hash
    old_hash_match = re.search(r"<!-- hash:(\w+) -->", readme)
    if old_hash_match and old_hash_match.group(1) == new_hash:
        print("No changes detected (hash match). Skipping update.")
        sys.exit(0)

    # Replace content between markers
    pattern = re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END)
    replacement = f"{MARKER_START}\n<!-- hash:{new_hash} -->\n{rendered}\n{MARKER_END}"
    new_readme = re.sub(pattern, replacement, readme, flags=re.DOTALL)

    # Atomic write
    print("Writing updated README...")
    dir_name = os.path.dirname(README_PATH)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=dir_name,
        prefix=".",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        tmp.write(new_readme)
        tmp_path = tmp.name

    os.rename(tmp_path, README_PATH)
    print(f"README updated successfully. Hash: {new_hash}")


if __name__ == "__main__":
    main()
