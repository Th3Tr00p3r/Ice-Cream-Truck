"""
Helper Module
"""

from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import PIL


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


def tint_greyscale_pixels(
    img: PIL.Image,
    color: str,
    threshold_shade_of_grey: float = 100.0,
    threshold_deviation_from_grey: float = 35.0,
    linear_beta: tuple = (135.0, 1.0),
) -> PIL.Image:

    rgb_color = PIL.ImageColor.getrgb(color)

    img_arr = np.array(img)
    norm_greyscale_img_arr = img_arr[:, :, :3].mean(2) / 255
    greyscale_mask = (img_arr[:, :, :3].std(2) <= threshold_deviation_from_grey) & (
        img_arr[:, :, :3].mean(2) <= threshold_shade_of_grey
    )

    delta, factor = linear_beta
    for dim, color_band in enumerate(rgb_color):
        img_arr[greyscale_mask, dim] = (
            (norm_greyscale_img_arr[greyscale_mask] + delta) * color_band * factor
        )

    img_arr = np.clip(img_arr, 0, 255)

    return PIL.Image.fromarray(img_arr.astype(np.uint8))


def crop_resize_concat_horizontally(im_list, resample=PIL.Image.BOX):
    # Adapted from: https://note.nkmk.me/en/python-pillow-concat-images/

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


def get_score_image(n: int, digit_img_dir_path: Path):
    """
    Accepts an integer 'n' and a path to a directory containing only
    relevent digit images (sorted - e.g. ending in the corresponding digit)
    and returns an image of the number, made of the digit images supplied.
    """

    digit_dict = {
        idx: PIL.Image.open(img_path)
        for idx, img_path in enumerate(digit_img_dir_path.glob("*.png"))
    }
    img_list = [digit_dict[int(digit_char)] for digit_char in str(n)]
    return crop_resize_concat_horizontally(img_list)
