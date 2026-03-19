"""Renders the GitHub contribution graph as text art."""

LEVEL_CHARS = {
    "NONE": "·",
    "FIRST_QUARTILE": "░",
    "SECOND_QUARTILE": "▒",
    "THIRD_QUARTILE": "▓",
    "FOURTH_QUARTILE": "█",
}

DAY_LABELS = {
    1: "Mon  ",
    3: "Wed  ",
    5: "Fri  ",
}


def render_graph(contributions_collection):
    """Render a contribution graph as text art.

    Args:
        contributions_collection: The contributionsCollection dict from the
            GitHub GraphQL API.

    Returns:
        A list of text lines (strings).
    """
    calendar = contributions_collection["contributionCalendar"]
    total = calendar["totalContributions"]
    weeks = calendar["weeks"]
    months = calendar["months"]

    lines = []

    # Blank line before header.
    lines.append("")

    # Header.
    lines.append(f"  {total} contributions in the last year")
    lines.append("")

    # Build a mapping from date string to week index so we can place month
    # labels at the correct column.
    date_to_week = {}
    for week_idx, week in enumerate(weeks):
        for day in week["contributionDays"]:
            date_to_week[day["date"]] = week_idx

    # Month label row.
    month_row = [" "] * (5 + len(weeks))
    prev_col = -999
    for month in months:
        first_day = month["firstDay"]
        if first_day not in date_to_week:
            continue
        col = 5 + date_to_week[first_day]
        if col - prev_col < 3:
            continue
        label = month["name"][:3]
        for i, ch in enumerate(label):
            pos = col + i
            if pos < len(month_row):
                month_row[pos] = ch
        prev_col = col

    lines.append("".join(month_row).rstrip())

    # Build the grid: 7 rows (Sun=0 .. Sat=6), one column per week.
    grid = [[""] * len(weeks) for _ in range(7)]
    for week_idx, week in enumerate(weeks):
        filled = set()
        for day in week["contributionDays"]:
            weekday = day["weekday"]
            grid[weekday][week_idx] = LEVEL_CHARS.get(
                day["contributionLevel"], "·"
            )
            filled.add(weekday)
        # Fill any missing days in partial weeks with empty string (no char).
        for d in range(7):
            if d not in filled:
                grid[d][week_idx] = " "

    # Render each row.
    for weekday in range(7):
        prefix = DAY_LABELS.get(weekday, "     ")
        row_str = prefix + "".join(grid[weekday])
        lines.append(row_str.rstrip())

    lines.append("")

    # Legend.
    lines.append("       Less · ░ ▒ ▓ █ More")

    # Blank line after legend.
    lines.append("")

    return lines
