"""Game-neutral visible-window and bounded-input contracts; legacy types reexport these."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Callable

class HostError(ValueError):
    pass

class InputKind(str, Enum):
    KEYBOARD = "keyboard"
    MOUSE = "mouse"
    CONTROLLER = "controller"


@dataclass(frozen=True)
class WindowObservation:
    process_id: int | None
    process_started_at: str | None
    window_id: str | None
    title: str | None
    bounds: tuple[int, int, int, int] | None
    visible: bool
    windowed: bool
    foreground: bool
    occluded: bool = False

    @property
    def observable(self) -> bool:
        return (self.process_id is not None and bool(self.process_started_at) and bool(self.window_id)
                and self.bounds is not None and self.visible and self.windowed and not self.occluded)

    @property
    def trusted(self) -> bool:
        return (
            self.process_id is not None
            and self.process_started_at is not None
            and bool(self.window_id)
            and self.bounds is not None
            and self.visible
            and self.windowed
            and self.foreground
            and not self.occluded
        )


@dataclass(frozen=True)
class InputCommand:
    kind: InputKind
    control: str
    action: str
    duration_ms: int = 0
    target: tuple[int, int] | None = None
    purpose: str = ""
    reviewed_crop_id: str | None = None


class OrdinaryInputDriver:
    """Uses only configured OS-visible keyboard, mouse, or controller emitters."""

    error_type = HostError

    def __init__(
        self,
        *,
        keyboard: Callable[[InputCommand], None] | None = None,
        mouse: Callable[[InputCommand], None] | None = None,
        controller: Callable[[InputCommand], None] | None = None,
        neutralizer: Callable[[], None] | None = None,
    ) -> None:
        self._emitters = {
            InputKind.KEYBOARD: keyboard,
            InputKind.MOUSE: mouse,
            InputKind.CONTROLLER: controller,
        }
        self._neutralizer = neutralizer

    def available(self, kind: InputKind) -> bool:
        return self._emitters[kind] is not None

    def send(self, command: InputCommand) -> None:
        emitter = self._emitters.get(command.kind)
        if emitter is None:
            raise self.error_type(f"no ordinary {command.kind.value} emitter is configured")
        emitter(command)

    def neutralize(self) -> None:
        if self._neutralizer is not None:
            self._neutralizer()


