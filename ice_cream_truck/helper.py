"""
Helper Module
"""

from dataclasses import asdict, astuple, dataclass, field


@dataclass
class Position:
    x: int
    y: int

    def as_tuple(self) -> tuple:
        return astuple(self)


@dataclass
class ScreenProps:
    width: int
    height: int
    center_x: float = field(init=False)
    center_y: float = field(init=False)

    def __post_init__(self):
        self.center_x = self.width / 2
        self.center_y = self.height / 2

    def as_dict(self) -> dict:
        return asdict(self)
