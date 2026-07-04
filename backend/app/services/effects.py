"""Visual effects: auto punch-in zoom on speech/action peaks."""
from __future__ import annotations


def punch_in_filter(peaks: list[float], fps: float = 30, intensity: float = 0.15,
                    span_sec: float = 2.0) -> str:
    """Subtle zoompan pulses around peak timestamps. Off by default for calm clips."""
    if not peaks:
        return "null"
    max_zoom = 1.0 + max(0.05, min(0.3, intensity))
    conds = "+".join(f"between(time,{max(0.0, t - 0.2):.2f},{t + span_sec:.2f})" for t in peaks[:8])
    return (f"zoompan=z='if({conds},min(zoom+0.0008,{max_zoom:.2f}),max(zoom-0.002,1.0))'"
            f":d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':fps={int(fps)}")
