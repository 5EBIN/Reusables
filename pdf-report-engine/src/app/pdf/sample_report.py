"""One invented example report ("Sample Inspection Report") built only from the engine's building blocks."""
from __future__ import annotations

from app.pdf import report_kit as K

ITEMS = [
    ["A-1", "Handrail on the north stair is loose at the second post.", "medium", "WARN"],
    ["A-2", "Fire extinguisher tag is dated within the last 12 months.", "info", "PASS"],
    ["A-3", "Emergency exit signage is missing in the east corridor.", "high", "FAIL"],
    ["A-4", "Roof access was locked; the roof was not inspected.", "info", "UNKNOWN"],
]


def build_story() -> list:
    story = []
    story += K.heading("Summary")
    story += K.key_value([("Site", "Example Building, Block B"), ("Inspector", "A. Example"), ("Date", "2025-01-15")])
    story += K.heading("Observations")
    story += K.table([["Item", "Observation", "Severity", "Status"]] + ITEMS, "sample", status_col=3)
    story += [K.P("This report is invented sample data produced to show the layout.")]
    return story


def render() -> bytes:
    inputs = {"items": ITEMS}
    return K.render_bytes(build_story(), title="Sample Inspection Report", project="Example Building", project_id="EX-0001", doc_id="SAMPLE-0001",
                          subject="Sample", author="", run_context=None, inputs=inputs)
