"""
Helper Module
"""

import pickle
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from typing import Any, List, Tuple

import game_constants as game
import numpy as np
import PIL
import PIL.ImageMorph


class Limits:
    """Doc."""

    def __init__(
        self,
        limits=(np.NINF, np.inf),
        upper=np.inf,
        dict_labels: Tuple[str, str] = None,
        from_string=False,
    ):

        self.dict_labels = dict_labels

        if from_string:
            source_str = limits
            self.lower, self.upper = generate_numbers_from_string(source_str)
        else:
            try:
                self.lower, self.upper = limits
            except ValueError:  # limits is not 2-iterable
                raise TypeError(
                    "Arguments must either be a single value (lower limit) or a 2-iterable"
                )
            except TypeError:  # limits is not iterable
                self.lower, self.upper = limits, upper
                if limits is None:
                    return None
            else:
                if None in limits:
                    return None

    def __call__(self, *args, **kwargs):
        self.__init__(*args, **kwargs)

    def __repr__(self):
        return f"Limits(lower={self.lower}, upper={self.upper})"

    def __str__(self):
        lower_frmt = ".2f"
        with suppress(OverflowError):
            if int(self.lower) == float(self.lower):
                lower_frmt = "d"
                self.lower = int(self.lower)  # ensure for stuff like 1e3 (round floats)

        upper_frmt = ".2f"
        with suppress(OverflowError):
            if int(self.upper) == float(self.upper):
                upper_frmt = "d"
                self.upper = int(self.upper)  # ensure for stuff like 1e3 (round floats)

        return f"({self.lower:{lower_frmt}}, {self.upper:{upper_frmt}})"

    def __iter__(self):
        yield from (self.lower, self.upper)

    def __getitem__(self, idx):
        return tuple(self)[idx]

    def __len__(self):
        return 2

    def __and__(self, other):
        self = self if self is not None else Limits()
        other = other if other is not None else Limits()
        lower = max(self[0], other[0])
        upper = min(self[1], other[1])
        return Limits(lower, upper)

    def __eq__(self, other):
        try:
            return tuple(self) == other
        except TypeError:
            raise TypeError("Can only compare Limits to other instances or tuples")

    def __ne__(self, other):
        return not self.__eq__(other)

    def __gt__(self, other):
        if isinstance(other, (int, float)):
            return other < self.lower
        if isinstance(other, Limits):
            return other.upper < self.lower

    def __lt__(self, other):
        if isinstance(other, (int, float)):
            return other > self.upper
        if isinstance(other, Limits):
            return other.lower > self.upper

    def __contains__(self, other):
        """
        Checks if 'other' is in 'Limits'.
        If:
        other is a tuple/Limits: checks if full range is contained and returns bool
        other is number: checks if number is contained in range and returns bool
        """
        try:
            if len(other) == 2:
                return (self[0] <= other[0]) and (self[1] >= other[1])
        except TypeError:  # other is not 2-iterable
            try:
                return self.lower <= other <= self.upper
            except TypeError:  # other is not a number
                if other is None:
                    return False
                else:
                    raise TypeError(
                        "Can only compare Limits to other instances or 2-iterable objects."
                    )

    def valid_indices(self, arr: np.ndarray, as_bool=True):
        """
        Checks whether each element is contained and returns a boolean array of same shape.
        __contains__ must return a single boolean array, otherwise would be included there.
        """
        if isinstance(arr, np.ndarray):
            if as_bool:
                return (arr >= self.lower) & (arr <= self.upper)
            else:
                return np.nonzero((arr >= self.lower) & (arr <= self.upper))[0]
        else:
            raise TypeError("Argument 'arr' must be a Numpy ndarray!")

    def as_dict(self):
        if self.dict_labels is not None:
            return {key: val for key, val in zip(self.dict_labels, (self.lower, self.upper))}
        else:
            return {key: val for key, val in zip(("lower", "upper"), (self.lower, self.upper))}

    def interval(self):
        return abs(self.upper - self.lower)

    def center(self):
        """Get the center of the range"""

        return sum(self) * 0.5

    def clamp(self, obj):
        """Force limit range on object"""

        if isinstance(obj, (int, float)):
            return max(min(self.upper, obj), self.lower)
        elif hasattr(obj, "lower") and hasattr(obj, "upper"):
            return Limits(self.clamp(obj.lower), self.clamp(obj.upper))
        else:
            raise TypeError("Clamped object must be either a Limits instance or a number!")

    def as_range(self) -> range:
        """Get a Python 'range' (generator)"""

        return range(self.lower, self.upper)


def can_float(value: Any) -> bool:
    """Checks if 'value' can be turned into a float"""

    try:
        float(value)
        return True
    except (ValueError, TypeError):
        if value == "-":  # consider hyphens part of float (minus sign)
            return True
        return False


def number(x):
    """Attempts to convert 'x' into an integer, a float if that fails."""

    try:
        return int(x)
    except (ValueError, OverflowError):
        return float(x)


def generate_numbers_from_string(source_str):
    """A generator function for getting numbers out of strings."""

    i = 0
    while i < len(source_str):
        j = i + 1
        while (j < len(source_str) + 1) and can_float(source_str[i:j]):
            j += 1
        with suppress(TypeError, ValueError):
            yield number(source_str[i : j - 1])
        i = j


@dataclass
class Vector:
    x: float
    y: float

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


def tint_greyscale_pixels(
    img: PIL.Image,
    color: str,
    should_tint_black: bool = True,
    threshold_shade_of_grey: float = 100.0,
    threshold_deviation_from_grey: float = 35.0,
    linear_beta: tuple = (0.8, 1.05),
) -> PIL.Image:

    rgb_color = PIL.ImageColor.getrgb(color)

    img_arr = np.array(img)
    norm_greyscale_img_arr = img_arr[:, :, :3].mean(2) / 255
    if should_tint_black:
        greyscale_mask = (img_arr[:, :, :3].std(2) <= threshold_deviation_from_grey) & (
            img_arr[:, :, :3].mean(2) <= threshold_shade_of_grey
        )
    else:
        greyscale_mask = (img_arr[:, :, :3].std(2) <= threshold_deviation_from_grey) & (
            img_arr[:, :, :3].mean(2) > threshold_shade_of_grey
        )

    delta, factor = linear_beta
    for dim, color_band in enumerate(rgb_color):
        img_arr[greyscale_mask, dim] = np.clip(
            (norm_greyscale_img_arr[greyscale_mask] + delta) * color_band * factor, 0, 255
        )

    img_arr = np.clip(img_arr, 0, 255)

    return PIL.Image.fromarray(img_arr.astype(np.uint8))


def crop_resize_concat_horizontally(im_list, resample=PIL.Image.BOX):
    """ "Adapted from: https://note.nkmk.me/en/python-pillow-concat-images/"""

    cropped_img_list = [img.crop(img.getbbox()) for img in im_list]
    min_height = min(im.height for im in cropped_img_list)
    im_list_resize = [
        im.resize((int(im.width * min_height / im.height), min_height), resample=resample)
        for im in cropped_img_list
    ]
    total_width = sum(im.width for im in im_list_resize)
    dst = PIL.Image.new("RGBA", (total_width, min_height))
    pos_x = 0
    for im in im_list_resize:
        dst.paste(im, (pos_x, 0))
        pos_x += im.width
    return dst


def get_aura_image(img, color_str, thickness=3):
    """Takes an input PIL image and adds an 'aura' effect to it in chosen color"""

    alpha_chan = img.getchannel("A")

    dilate_op = PIL.ImageMorph.MorphOp(op_name="dilation8")
    for _ in range(thickness):
        _, alpha_chan = dilate_op.apply(alpha_chan)

    white_aura_img = alpha_chan.convert("RGBA")
    white_aura_img.putalpha(alpha_chan)

    blue_aura_img = tint_greyscale_pixels(
        white_aura_img,
        color_str,
        should_tint_black=False,
        threshold_deviation_from_grey=10,
        linear_beta=(0, 1),
    )

    return PIL.Image.alpha_composite(blue_aura_img, img)


def load_high_scores() -> List[Tuple[str, int]]:
    """Doc."""

    try:
        with open(game.HIGH_SCORES_FILENAME, "rb") as f:
            return pickle.load(f)
    except FileNotFoundError:
        return [("???", 0)] * 3


def save_high_scores(high_scores_list) -> None:
    """Doc."""

    with open(game.HIGH_SCORES_FILENAME, "wb") as f:
        pickle.dump(high_scores_list, f, protocol=-1)
