"""Deterministic regex parser for sam-3.1 output wire format.

Wire format (in response.output_text), one or more detections:
    <0f>0<|box;x1=181;y1=365;x2=556;y2=486;w=1516;h=1600|><|mask;x=0;y=0;data=...|>

Rules (see AGENTS.md SS3.1):
- Never use an LLM to parse this. Regex only, pure and unit-testable.
- Coordinates are in the image space declared by w/h.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

_DETECTION_RE = re.compile(
    r"<\|box;x1=(?P<x1>\d+);y1=(?P<y1>\d+);x2=(?P<x2>\d+);y2=(?P<y2>\d+);"
    r"w=(?P<w>\d+);h=(?P<h>\d+)\|>"
    r"(?:<\|mask;x=(?P<mx>\d+);y=(?P<my>\d+);data=(?P<mask>[^|]*)\|>)?"
)


@dataclass
class SamDetection:
    x1: int
    y1: int
    x2: int
    y2: int
    w: int
    h: int
    mask_x: int | None = None
    mask_y: int | None = None
    mask_data: str | None = None  # RLE payload, decoded on Day 2

    @property
    def box_area(self) -> int:
        return max(0, self.x2 - self.x1) * max(0, self.y2 - self.y1)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SamParseResult:
    detections: list[SamDetection] = field(default_factory=list)
    raw: str = ""

    @property
    def image_size(self) -> tuple[int, int] | None:
        if not self.detections:
            return None
        d = self.detections[0]
        return (d.w, d.h)

    def to_dict(self) -> dict:
        return {
            "image_size": self.image_size,
            "count": len(self.detections),
            "detections": [d.to_dict() for d in self.detections],
        }


def parse_sam_output(output_text: str) -> SamParseResult:
    """Parse all box/mask detections from sam-3.1 output_text. Empty-safe."""
    detections: list[SamDetection] = []
    for m in _DETECTION_RE.finditer(output_text or ""):
        g = m.groupdict()
        detections.append(
            SamDetection(
                x1=int(g["x1"]), y1=int(g["y1"]),
                x2=int(g["x2"]), y2=int(g["y2"]),
                w=int(g["w"]), h=int(g["h"]),
                mask_x=int(g["mx"]) if g.get("mx") is not None else None,
                mask_y=int(g["my"]) if g.get("my") is not None else None,
                mask_data=g.get("mask") or None,
            )
        )
    return SamParseResult(detections=detections, raw=output_text or "")


def box_iou(a: SamDetection, b: SamDetection) -> float:
    """Intersection-over-Union of two boxes. Pure geometry - verifier foundation (Day 4)."""
    ix1, iy1 = max(a.x1, b.x1), max(a.y1, b.y1)
    ix2, iy2 = min(a.x2, b.x2), min(a.y2, b.y2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    union = a.box_area + b.box_area - inter
    return (inter / union) if union > 0 else 0.0
