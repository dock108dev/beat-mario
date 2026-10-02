"""Logical desktop coordinates, normalized captures and unavailable camera seam."""
from dataclasses import dataclass
import math

from smb3_agent.host_contracts import HostError


@dataclass(frozen=True)
class WindowCoordinates:
    bounds: tuple[int, int, int, int]
    pixel_size: tuple[int, int]

    def validate(self):
        if (len(self.bounds) != 4 or any(type(v) is not int for v in self.bounds)
                or min(self.bounds[2:]) <= 0
                or self.pixel_size not in (self.bounds[2:], tuple(v*2 for v in self.bounds[2:]))):
            raise HostError("Unsupported capture scaling or geometry")

    def native_point(self, x, y):
        self.validate()
        if any(type(v) not in {float, int} or not math.isfinite(v) or not 0 <= v < 1 for v in (x, y)):
            raise HostError("Normalized target outside selected window")
        bx, by, width, height = self.bounds
        return (bx+min(width-1, round(x*width)), by+min(height-1, round(y*height)))


@dataclass(frozen=True)
class RelativePointerCalibration:
    profile_id: str
    window_id: str
    settings_id: str
    observed: bool = False


def relative_pointer_pulse(dx, dy, duration_ms, calibration):
    # Finite interface only. No provider may advertise this capability yet.
    if (any(type(v) not in {int, float} or not math.isfinite(v) or abs(v) > 100 for v in (dx, dy))
            or type(duration_ms) is not int or not 1 <= duration_ms <= 250
            or not isinstance(calibration, RelativePointerCalibration)):
        raise HostError("Invalid bounded relative-pointer request")
    raise HostError("Relative camera input and calibration are not qualified or available")
