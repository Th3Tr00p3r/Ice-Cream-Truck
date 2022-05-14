"""
Helper Module
"""

from dataclasses import asdict, dataclass, field


@dataclass
class Vector:
    x: int
    y: int

    def __call__(self, *args, **kwargs):
        self.__init__(*args, **kwargs)

    def __iter__(self):
        yield from (self.x, self.y)

    def __getitem__(self, idx):
        return tuple(self)[idx]

    def __setitem__(self, idx):
        return tuple(self)[idx]

    def __len__(self):
        return 2

    def __add__(self, other):
        try:
            x1, y1 = self
            x2, y2 = other
            return Vector(x1 + x2, y1 + y2)
        except TypeError:
            raise TypeError(f"Cannot add '{type(other)}' to 'Vector'")

    def __sub__(self, other):
        try:
            x1, y1 = self
            x2, y2 = other
            return Vector(x1 - x2, y1 - y2)
        except TypeError:
            raise TypeError(f"Cannot subtract '{type(other)}' from 'Vector'")

    def __eq__(self, other):
        try:
            return tuple(self) == tuple(other)
        except TypeError:
            raise TypeError("Can only compare Vectors to other Vectors or tuples")

    def __ne__(self, other):
        return not self.__eq__(other)


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
