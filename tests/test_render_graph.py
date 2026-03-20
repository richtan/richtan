from render_graph import render_graph
from utils import visual_len


def _make_calendar(weeks_count=52, total=100):
    """Create synthetic contribution calendar data."""
    weeks = []
    for w in range(weeks_count):
        days = []
        for d in range(7):
            day_num = w * 7 + d
            month = (day_num // 30) % 12 + 1
            day_of_month = (day_num % 28) + 1
            days.append({
                "contributionCount": 1 if w % 3 == 0 else 0,
                "contributionLevel": "FIRST_QUARTILE" if w % 3 == 0 else "NONE",
                "date": f"2025-{month:02d}-{day_of_month:02d}",
                "weekday": d,
            })
        weeks.append({"contributionDays": days})

    months = [
        {"name": m, "firstDay": f"2025-{i+1:02d}-01", "totalWeeks": 4}
        for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    ]

    return {
        "contributionCalendar": {
            "totalContributions": total,
            "weeks": weeks,
            "months": months,
        }
    }


class TestRenderGraph:
    def test_basic_rendering(self):
        data = _make_calendar()
        lines = render_graph(data)
        assert len(lines) > 0
        # Should contain the total
        joined = "\n".join(lines)
        assert "100 contributions" in joined

    def test_has_borders(self):
        data = _make_calendar()
        lines = render_graph(data)
        # Should have top and bottom borders
        border_lines = [l for l in lines if l.startswith("┌") or l.startswith("└")]
        assert len(border_lines) == 2

    def test_has_legend(self):
        data = _make_calendar()
        lines = render_graph(data)
        joined = "\n".join(lines)
        assert "Less" in joined
        assert "More" in joined

    def test_zero_contributions(self):
        data = _make_calendar(total=0)
        # Make all days NONE
        for week in data["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                day["contributionCount"] = 0
                day["contributionLevel"] = "NONE"
        lines = render_graph(data)
        joined = "\n".join(lines)
        assert "0 contributions" in joined
