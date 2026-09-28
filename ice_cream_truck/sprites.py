import math
from collections import namedtuple
from contextlib import suppress
from pathlib import Path
from random import choice, choices, randint, random, uniform
from types import SimpleNamespace

import arcade
import game_constants as game
import numpy as np
import PIL
from arcade.hitbox import RotatableHitBox, SimpleHitBoxAlgorithm, algo_detailed
from helper import Limits, Vector, get_aura_image, tint_greyscale_pixels

# Assets path
try:
    # Nuitka onefile
    __compiled__  # type: ignore
    ASSETS_PATH = Path(__file__).parent / "assets"
except NameError:
    ASSETS_PATH = Path("./assets")

TexturePair = namedtuple("TexturePair", "RIGHT LEFT")


class FastSimpleHitBoxAlgorithm(SimpleHitBoxAlgorithm):
    """Same points as arcade's simple algorithm, computed with numpy instead of per-pixel getpixel"""

    def calculate(self, image, **kwargs):
        if image.mode != "RGBA":
            raise ValueError("Image mode is not RGBA. image.convert('RGBA') is needed.")

        alpha = np.asarray(image.getchannel("A"))
        ys, xs = np.nonzero(alpha)
        if not len(xs):
            return self.create_bounding_box(image)

        left, top, right, bottom = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
        # each corner's offset is the smallest diagonal (|dx| + |dy|) distance to an opaque pixel
        top_left = int(((xs - left) + (ys - top)).min())
        top_right = int(((right - xs) + (ys - top)).min())
        bottom_left = int(((xs - left) + (bottom - ys)).min())
        bottom_right = int(((right - xs) + (bottom - ys)).min())

        h, w = alpha.shape
        points = [(left, bottom + 1 - bottom_left)]
        if bottom_left:
            points.append((left + bottom_left, bottom + 1))
        points.append((right + 1 - bottom_right, bottom + 1))
        if bottom_right:
            points.append((right + 1, bottom + 1 - bottom_right))
        points.append((right + 1, top + top_right))
        if top_right:
            points.append((right + 1 - top_right, top))
        points.append((left + top_left, top))
        if top_left:
            points.append((left, top + top_left))

        return tuple(dict.fromkeys((x - w / 2, (h - y) - h / 2) for x, y in points))


algo_fast_simple = FastSimpleHitBoxAlgorithm()
TEXTURE_CACHE: dict = {}


def load_detailed_texture(filepath):
    """Load (or get cached) texture with a detailed hit box"""

    return arcade.texture.default_texture_cache.load_or_get_texture(
        filepath, hit_box_algorithm=algo_detailed
    )


class SpriteMixin:
    """Useful methods for sprites"""

    color_str: str  # mypy complained...?

    def load_texture(
        self,
        filepath,
        flipped_horizontally=False,
        color: str = None,
        aura_color=None,
        image_scale=1.0,
        **kwargs,
    ):
        """
        Load a texture pair, with the second being a mirror image.
        Optionally, tint the greyscale pixels of the texture.
        """

        texture_name = f"{filepath.parent.stem}_{filepath.stem}"

        # identical textures are requested many times (e.g. each player cat loads all colours)
        cache_key = (
            filepath,
            flipped_horizontally,
            color,
            aura_color,
            image_scale,
            repr(sorted(kwargs.items())),
        )
        with suppress(KeyError):
            return TEXTURE_CACHE[cache_key]

        # open image at filepath
        img = PIL.Image.open(filepath)
        # flip if needed
        if flipped_horizontally:
            img = img.transpose(method=PIL.Image.Transpose.FLIP_LEFT_RIGHT)
            texture_name += "_flipped"

        # tint and add background aura as needed
        if color is not None:
            img = tint_greyscale_pixels(img, color, **kwargs)
            texture_name += f"_{color}"
        if aura_color is not None:
            img = get_aura_image(img, aura_color)
            texture_name += f"_{aura_color}"
        # shrink images drawn far below their full size, so they take less atlas memory
        if image_scale != 1.0:
            size = round(img.width * image_scale), round(img.height * image_scale)
            img = img.resize(size, resample=PIL.Image.Resampling.LANCZOS)
            texture_name += f"_x{image_scale}"

        # return a texture
        TEXTURE_CACHE[cache_key] = arcade.Texture(
            img, hash=texture_name, hit_box_algorithm=algo_fast_simple
        )
        return TEXTURE_CACHE[cache_key]

    def load_texture_pair(self, filepath, **kwargs):
        """
        Load a texture pair, with the second being a mirror image.
        Optionally, tint the greyscale pixels of the texture.
        """

        return TexturePair(
            RIGHT=self.load_texture(filepath, **kwargs),
            LEFT=self.load_texture(filepath, flipped_horizontally=True, **kwargs),
        )

    def restrict_position(self, map_width, should_kill=False, bottom=0):
        """Restrict sprite position so screen width and bottom - either treat as ground/wall or kill"""

        if self.left < 0:
            self.left = 0
            if should_kill:
                self.kill()
                self.is_off_screen = True
        if self.right >= map_width:
            self.right = map_width
            if should_kill:
                self.kill()
                self.is_off_screen = True
        if self.bottom < bottom:
            if should_kill:
                self.kill()
                self.is_off_screen = True
            else:
                self.bottom = bottom


class AnimatedTexture:
    """Doc."""

    # TODO: what are the units of rate?

    def __init__(self, image_list, rate, should_loop=False):
        self.image_iter = iter(image_list)
        self.rate = rate
        self.should_loop = should_loop
        self.n_imgs = len(image_list)
        self.timer = 0.0
        self.img_idx = 0

    def next(self, delta_time: float):
        """Doc."""

        if self.timer * self.rate >= 1:
            self.img_idx += 1
        self.timer += delta_time
        return self.image_iter[self.img_idx]


class DigitTextures(SpriteMixin):
    """Doc."""

    MAIN_TEXTURE_PATH = ASSETS_PATH / "images" / "HUD"

    def __init__(self):
        self.digits = []
        for digit in range(10):
            self.digits.append(
                self.load_texture(
                    self.MAIN_TEXTURE_PATH / f"hud{digit}.png",
                )
            )
        self.x = self.load_texture(
            self.MAIN_TEXTURE_PATH / "hudX.png",
        )


class PopsicleColorTextures(SpriteMixin):
    """Doc."""

    MAIN_TEXTURE_PATH = ASSETS_PATH / "images" / "items"

    def __init__(self, color_str):
        self.color_str = color_str
        self.textures = self._get_textures()

    def _get_textures(self):
        """Return a namespace with colored popsicle textures"""

        # standing texture
        standing_texture = self.load_texture(
            self.MAIN_TEXTURE_PATH / "popsicleWhite.png",
            color=self.color_str,
            linear_beta=(0, 1),
            threshold_deviation_from_grey=10,
            should_tint_black=False,
        )

        # create melting textures
        melt_textures = []
        h = standing_texture.height
        w = standing_texture.width
        for idx, (x_factor, y_factor) in enumerate(
            zip(np.linspace(0.5, 0.875, 10), np.linspace(0, 0.2, 10))
        ):
            arr_img = np.array(standing_texture.image)
            arr_img[: int(h * y_factor), :, 3] = 0
            arr_img[:, : int(w / 2 * x_factor), 3] = 0
            arr_img[:, int(w * (1 - x_factor / 2)) :, 3] = 0
            image = PIL.Image.fromarray(arr_img)
            texture_name = f"{self.color_str}_popsicle_melting_{idx}"
            melt_textures.append(arcade.Texture(image, hash=texture_name))

        return SimpleNamespace(
            standing=standing_texture,
            melting=melt_textures,
        )


class ColorCatTextures(SpriteMixin):
    """Doc."""

    MAIN_TEXTURE_PATH = ASSETS_PATH / "images" / "cat"

    def __init__(self, color_str, **kwargs):
        self.color_str = color_str
        self.textures = self._get_textures(color=color_str, **kwargs)

    def _get_textures(self, aura_color=None, **kwargs):
        """Return a namespace with colored cat textures"""
        # TODO: for each texture create an "aura" version (only for player cat thogh - use flag at instantiation?)

        paths_dict = {
            "standing": self.MAIN_TEXTURE_PATH / "standing1.png",
            "running": [self.MAIN_TEXTURE_PATH / f"running{i}.png" for i in range(1, 6)],
            "pouncing": self.MAIN_TEXTURE_PATH / "running6.png",
            "sliding": self.MAIN_TEXTURE_PATH / "running1.png",
            "jumping": self.MAIN_TEXTURE_PATH / "jumping1.png",
            "stalling": [self.MAIN_TEXTURE_PATH / f"stalling{i}.png" for i in (1, 2)],
            "falling": self.MAIN_TEXTURE_PATH / "falling1.png",
            "scratching": self.MAIN_TEXTURE_PATH / "scratching1.png",
            "dropping": [self.MAIN_TEXTURE_PATH / f"dropping{i}.png" for i in (1, 2)],
            "begging": [self.MAIN_TEXTURE_PATH / f"begging{i}.png" for i in (1, 2, 3, 4, 3, 2)],
            "getting_hit": self.MAIN_TEXTURE_PATH / "getting_hit1.png",
        }

        texture_dict = {}
        for name, paths in paths_dict.items():
            try:
                texture_dict[name] = self.load_texture_pair(paths, **kwargs)
            except AttributeError:
                # paths is a list of paths
                texture_dict[name] = [self.load_texture_pair(path_, **kwargs) for path_ in paths]

        # add aura-d textures, too
        if aura_color:
            for name, paths in paths_dict.items():
                try:
                    texture_dict[f"{name}_aura"] = self.load_texture_pair(
                        paths, aura_color=aura_color, **kwargs
                    )
                except AttributeError:
                    # paths is a list of paths
                    texture_dict[f"{name}_aura"] = [
                        self.load_texture_pair(path_, aura_color=aura_color, **kwargs)
                        for path_ in paths
                    ]

        return SimpleNamespace(**texture_dict)


class BasicSprite(arcade.Sprite, SpriteMixin):
    texture: arcade.Texture

    def __init__(self, init_position: Vector, **kwargs):
        init_x, init_y = init_position
        super().__init__(center_x=init_x, center_y=init_y, **kwargs)

        self.is_off_screen = False

    def set_hit_box_points(self, points):
        """Set the hit box from a list of points"""

        if points is self.hit_box.points:
            return
        self.hit_box = RotatableHitBox(
            points, position=self.position, angle=self.angle, scale=self.scale
        )


class Poof(BasicSprite):
    """Doc."""

    MAIN_TEXTURE_PATH = ASSETS_PATH / "images" / "gifs"
    ANIMATION_RATE = 1 / 0.05
    BASE_SCALE = 0.3
    # frames are stored at half size (never drawn above it), keeping the texture atlas small enough for tablets
    IMAGE_SCALE = 0.5

    def __init__(
        self,
        init_position: Vector,
        color_str: str,
        **kwargs,
    ):
        # TODO: perhaps there's no need for initial textures!
        super().__init__(init_position, scale=self.BASE_SCALE / self.IMAGE_SCALE, **kwargs)

        self.loaded_textures = [
            self.load_texture(
                self.MAIN_TEXTURE_PATH / f"poof{i}.png",
                color=color_str,
                image_scale=self.IMAGE_SCALE,
            )
            for i in range(1, 16)
        ]
        #        self.animated_textures = iter(self.loaded_textures)

        self.timer = 0.0
        self.texture_idx = 0

    def reset(self, init_position: Vector, scale: float):
        """Doc."""

        self.center_x = init_position.x
        self.center_y = init_position.y
        self.scale = self.BASE_SCALE / self.IMAGE_SCALE * scale
        self.texture_idx = 0
        self.texture = self.loaded_textures[0]  # else arcade 3 draws its placeholder until frame 1
        self.animated_textures = iter(self.loaded_textures)

    def update_animation(self, delta_time: float):
        """Doc."""

        self.timer += delta_time
        if self.timer * self.ANIMATION_RATE > 1:
            try:
                self.texture = next(self.animated_textures)
            except StopIteration:
                self.kill()
            else:
                self.timer = 0.0


class CompetitorCat(BasicSprite):
    """Doc."""

    RUNNING_ANIMATION_FACTOR = 0.4
    BEGGING_ANIMATION_DURATION_s = 3
    MAX_LIVES = 1
    texture: arcade.texture.Texture
    change_x: float
    change_y: float
    center_y: float
    color_textures_dict = {
        color_str: ColorCatTextures(color_str) for color_str in game.COLORS - game.PLAYER_COLORS
    }
    poof_dict = {
        color_str: Poof(Vector(0, 0), color_str) for color_str in game.COLORS - game.PLAYER_COLORS
    }

    def __init__(
        self,
        init_position: Vector,
        init_speed: Vector,
        speeds: SimpleNamespace,
        acceleration_magnitude: float,
        color_str: str,
        game_view: arcade.View,
        scale=1,
        **kwargs,
    ):
        super().__init__(
            init_position,
            path_or_texture=load_detailed_texture(ASSETS_PATH / "images" / "cat" / "standing1.png"),
            scale=scale,
            **kwargs,
        )

        self.scale = scale

        # hold game view
        self.game_view = game_view

        # initial lives
        self.lives = self.MAX_LIVES

        # get default/initial hitbox
        self.init_hitbox = self.texture.hit_box_points

        # initialize state
        self.move_state = game.STOP
        self.state = SimpleNamespace(
            is_facing_left=int(False),
            jump=SimpleNamespace(
                can_jump=False,
                is_jumping=False,
                is_falling=False,
            ),
            pounce=SimpleNamespace(
                can_pounce=False,
                is_pouncing=False,
                finishing_pounce=False,
                recovery_timer=0,
            ),
            is_near_edge=False,
            is_in_air=True,
        )

        self.mode = "returning"

        # Default to face-right
        self.face_direction = game.FACE_RIGHT

        # Used for flipping between image sequences
        self.texture_idx = 0

        # Load textures
        self.color_str = color_str
        self.loaded_textures = self.color_textures_dict[color_str].textures
        self.hitboxes = SimpleNamespace(
            **{
                name: (
                    txtr[0][0].hit_box_points if isinstance(txtr, list) else txtr[0].hit_box_points
                )
                for name, txtr in vars(self.loaded_textures).items()
            }
        )

        self.speeds = speeds
        self.max_run_speed = self.speeds.RUN
        self.acceleration_magnitude = acceleration_magnitude
        self.acceleration = 0.0

        # initial velocity
        self.change_x, self.change_y = init_speed

        # for setting running animation frequency
        self.timer = 0.0
        self.face_switch_timer = 0.0

        self.sought_popsicle: Popsicle = None

    def change_texture_and_hitbox(self, texture_type: str, idx=None, change_hitbox=False):
        """Doc."""

        if idx is not None:
            self.texture = getattr(self.loaded_textures, texture_type)[idx][
                self.state.is_facing_left
            ]
        else:
            self.texture = getattr(self.loaded_textures, texture_type)[self.state.is_facing_left]
        self.texture_type = texture_type

        if change_hitbox:
            self.set_hit_box_points(getattr(self.hitboxes, texture_type))
        else:  # use default hitbox
            self.set_hit_box_points(self.init_hitbox)

    def update_animation(self, delta_time: float):
        """Doc."""

        self.face_switch_timer += delta_time

        # update state
        if self.acceleration != 0:
            self.move_state = int(math.copysign(1, self.acceleration))
            if self.face_switch_timer > 0.5:
                self.state.is_facing_left = self.move_state < 0
                self.face_switch_timer = 0.0
        else:
            self.move_state = 0

        self.timer += delta_time

        # stop spinning
        self.change_angle = 0

        # Jumping/Stalling/Falling animation
        if self.change_y < 0 and abs(self.change_x) <= self.speeds.RUN:
            if 5 < self.change_y:
                self.change_texture_and_hitbox("jumping", change_hitbox=True)
            elif 0 < self.change_y < 5:
                self.change_texture_and_hitbox("stalling", idx=0, change_hitbox=True)
            elif -5 < self.change_y < 0:
                self.change_texture_and_hitbox("stalling", idx=1, change_hitbox=True)
            elif self.change_y < -5:
                self.change_texture_and_hitbox("falling")

        # pounce animation
        elif self.state.pounce.is_pouncing:
            self.change_texture_and_hitbox("pouncing")

        # Running animation
        elif not self.mode == "begging":
            if self.timer >= self.RUNNING_ANIMATION_FACTOR / (
                (
                    abs(self.change_x)
                    + (
                        self.acceleration_magnitude * delta_time
                        if self.acceleration * self.change_x < 0.0
                        or abs(self.change_x) <= self.speeds.SLIDE
                        else 0
                    )
                )
                / self.speeds.RUN
            ) / len(self.loaded_textures.running):
                self.texture_idx += 1
                self.timer = 0
            if self.texture_idx >= len(self.loaded_textures.running):
                self.texture_idx = 0
            self.change_texture_and_hitbox("running", idx=self.texture_idx, change_hitbox=True)

        # Begging animation
        else:
            if self.timer >= self.BEGGING_ANIMATION_DURATION_s / len(self.loaded_textures.begging):
                self.texture_idx += 1
                self.timer = 0
            if self.texture_idx > len(self.loaded_textures.begging) - 1:
                self.texture_idx = 0
            self.change_texture_and_hitbox("begging", idx=self.texture_idx, change_hitbox=True)

    def seek(self, delta_time: float):
        """Fetch closest self-colored popsicle if one exists, otherwise go to ice cream truck"""

        # change position
        if self.state.is_in_air:
            self.center_y += self.change_y * delta_time
            # change speed (due to 'gravity')
            self.change_y -= game.GRAVITY * 10
        else:
            self.change_y = 0.0
            self.center_y = self._height // 2 + 130

        self.center_x += self.change_x * delta_time

        try:
            closest_popsicle = sorted(
                [
                    popsicle
                    for popsicle in self.game_view.popsicles
                    if popsicle.color_str == self.color_str
                ],
                key=lambda popsicle: abs(popsicle.center_x - self.center_x),
                reverse=True,
            )[0]
        except IndexError:
            # move towards ice_cream_truck
            self.truck_disp = self.game_view.ice_cream_truck.center_x - self.center_x
            self.acceleration = (
                math.copysign(1, self.truck_disp) * self.acceleration_magnitude * delta_time
            )
            self.sought_popsicle = None
            self.mode = "returning"
        else:
            if (
                self.sought_popsicle is None or self.sought_popsicle.is_off_screen
            ):  # seek closest popsicle
                self.sought_popsicle = closest_popsicle
                self.mode = "fetching"
            self.acceleration = (
                math.copysign(1, self.sought_popsicle.center_x - self.center_x)
                * self.acceleration_magnitude
            )

        finally:
            if (
                self.mode in {"returning", "begging"}
                and (abs(self.truck_disp) <= self.game_view.ice_cream_truck._width / 2)
                and self.change_x < self.speeds.SLIDE
            ):
                self.change_x = 0.0
                self.mode = "begging"
            else:
                self.change_x = Limits(-self.max_run_speed, self.max_run_speed).clamp(
                    self.change_x + self.acceleration * delta_time
                )

    def poof(self):
        """Doc."""

        poof = self.poof_dict[self.color_str]
        poof.reset(Vector(self.center_x, self.center_y - self.height / 3), self.scale_x)
        return poof


class PlayerCat(BasicSprite):
    """Doc."""

    MAIN_TEXTURE_PATH = ASSETS_PATH / "images" / "cat"
    RUNNING_ANIMATION_FACTOR = 0.4
    JUMP_STOP_RATE = 0.95
    MAX_LIVES = 5
    N_REQUIRED_FOR_SUPERPOWER = 25
    POUNCE_DURATION = 13  # units?
    INVULNERABILITY_DURATION_s = 1.5
    POUNCE_RECOV = 50  # TODO: units?..
    physics_engine: arcade.PhysicsEnginePlatformer
    texture: arcade.texture.Texture
    alpha: int
    change_x: float

    poof_dict = {color_str: Poof(Vector(0, 0), color_str) for color_str in game.PLAYER_COLORS}
    jump_sound = arcade.load_sound(str(ASSETS_PATH / "sounds" / "jump.wav"))
    get_hit_sound = arcade.load_sound(str(ASSETS_PATH / "sounds" / "get_hit.wav"))

    def __init__(
        self,
        init_position: Vector,
        keys_pressed,
        speeds: SimpleNamespace,
        acceleration_magnitude: float,
        color_str: str,
        aura_color_str: str,
        lives=3,
        state=None,
        ground_height: float = None,
        can_pounce_kill=False,
        can_swipe=False,
        **kwargs,
    ):
        self.color_textures_dict = {
            color_str: ColorCatTextures(color_str, aura_color=aura_color_str)
            for color_str in game.PLAYER_COLORS
        }

        super().__init__(
            init_position,
            path_or_texture=load_detailed_texture(self.MAIN_TEXTURE_PATH / "running1.png"),
            **kwargs,
        )

        self.ground_height = ground_height

        # initial lives
        self.is_alive = True
        self.lives = lives
        self.hit_timer = 0.0

        # get default/initial hitbox
        self.init_hitbox = self.texture.hit_box_points

        # hold map width
        self.map_width = game.SCREEN_PROPS.width

        # hold pressed keys
        self.keys_pressed = keys_pressed

        # initialize state
        self.move_state = game.STOP
        if state is None:
            self.state = SimpleNamespace(
                is_facing_left=int(False),
                jump=SimpleNamespace(
                    can_jump=False,
                    is_jumping=False,
                    is_falling=False,
                ),
                pounce=SimpleNamespace(
                    can_pounce=False,
                    is_pouncing=False,
                    finishing_pounce=False,
                    recovery_timer=0,
                ),
                air_dash=SimpleNamespace(
                    can_air_dash=False,
                    is_dashing=False,
                ),
                drop=SimpleNamespace(
                    can_drop=False,
                    is_dropping=False,
                ),
                superpower=SimpleNamespace(
                    is_ready=False,
                    is_on=False,
                ),
                is_near_edge=False,
                is_in_air=False,
            )
        else:
            self.state = state

        # Pounce-kill (BlueCat only)
        self.can_pounce_kill = can_pounce_kill

        # Swipe (YellowCat only)
        self.can_swipe = can_swipe

        # Default to face-right
        self.face_direction = game.FACE_RIGHT

        # Used for flipping between image sequences
        self.texture_idx = 0

        # Load textures
        self.color_str = color_str
        self.loaded_textures = self.color_textures_dict[color_str].textures
        self.hitboxes = SimpleNamespace(
            **{
                name: (
                    txtr[0][0].hit_box_points if isinstance(txtr, list) else txtr[0].hit_box_points
                )
                for name, txtr in vars(self.loaded_textures).items()
            }
        )

        self.speeds = speeds
        self.max_run_speed = self.speeds.RUN
        self.acceleration_magnitude = acceleration_magnitude
        self.acceleration = 0.0
        self.spin_speed = 30
        self.base_acceleration_magnitude = acceleration_magnitude

        # track number of self-colored popsicles collected (for superpower)
        self.n_favorite_pops_collected = 0

        # timers
        self.timer = 0.0  # animation
        self.superpower_timer = 0.0
        self.air_dash_timer = 0.0  # RedCat only
        self.pounce_timer = 0.0

        # poof
        self.poof_sprite = self.poof_dict[color_str]

    def update_state(self, **kwargs):
        """Doc."""

        can_jump = self.physics_engine.can_jump()
        n_jumps_since_ground = self.physics_engine.jumps_since_ground

        # Figure out if we need to flip face left or right
        if self.acceleration < 0:
            self.face_direction = game.FACE_LEFT
            self.state.is_facing_left = int(True)
        elif self.acceleration > 0:
            self.face_direction = game.FACE_RIGHT
            self.state.is_facing_left = int(False)

        # Check if near edge
        self.state.is_near_edge = (
            abs(self.center_x - self.map_width) < self.width / 2 or self.center_x < self.width / 2
        )

        # store 'can_jump' from the physics engine
        self.state.jump.can_jump = can_jump
        self.state.jump.is_jumping = bool(n_jumps_since_ground)

        # determine if can pounce (is on ground and running fast enough)
        self.state.pounce.can_pounce = (
            (self.state.pounce.recovery_timer == 0)
            and not self.state.jump.is_jumping
            and (abs(self.change_x) == self.speeds.RUN)
            and not self.state.is_near_edge
        )

        self.state.pounce.is_pouncing = (
            self.state.pounce.is_pouncing
            # and abs(self.change_x) > self.speeds.RUN
            and not self.state.is_in_air
            and self.pounce_timer > 0
        )
        self.state.air_dash.is_dashing = (
            self.state.air_dash.is_dashing
            # and abs(self.change_x) > self.speeds.RUN
            and self.state.is_in_air
            and self.air_dash_timer > 0
        )

        # pouncing
        if self.state.pounce.is_pouncing:
            self.change_x = self.state.pounce.direction * self.speeds.POUNCE
            self.pounce_timer -= 1

        # dashing
        if self.state.air_dash.is_dashing:
            self.change_x = self.state.air_dash.direction * self.speeds.POUNCE
            self.change_y = 0
            self.air_dash_timer -= 1

        # pounce recovery
        if self.state.pounce.recovery_timer > 0:
            self.state.pounce.recovery_timer -= 1

        # check if falling
        self.state.jump.is_falling = self.change_y < 0

        # check if in air
        self.state.is_in_air = self.state.jump.is_jumping

        # check if dropping (YellowCat)
        self.state.drop.is_dropping = self.state.drop.is_dropping and self.state.is_in_air

        self._update_move_direction()

        # check if superpower is ready
        if self.n_favorite_pops_collected == self.N_REQUIRED_FOR_SUPERPOWER:
            self.state.superpower.is_ready = True
            self.n_favorite_pops_collected = 0  # reset

    def _update_move_direction(self):
        """Decide if player is moving left, moving right, or stopping, based on pressed keys"""

        if not self.state.drop.is_dropping:
            is_only_left_pressed = (
                self.keys_pressed[arcade.key.LEFT] and not self.keys_pressed[arcade.key.RIGHT]
            )
            is_only_right_pressed = (
                self.keys_pressed[arcade.key.RIGHT] and not self.keys_pressed[arcade.key.LEFT]
            )
            are_both_pressed = (
                self.keys_pressed[arcade.key.RIGHT] and self.keys_pressed[arcade.key.LEFT]
            )
            are_none_pressed = (
                not self.keys_pressed[arcade.key.RIGHT] and not self.keys_pressed[arcade.key.LEFT]
            )
            is_changing_to_left = are_both_pressed and self.keys_pressed["LAST"] == arcade.key.LEFT
            is_changing_to_right = (
                are_both_pressed and self.keys_pressed["LAST"] == arcade.key.RIGHT
            )
            is_moving_left = is_only_left_pressed or is_changing_to_left
            is_moving_right = is_only_right_pressed or is_changing_to_right
            self.state.was_moving_left = (
                are_none_pressed and self.keys_pressed["LAST"] == arcade.key.LEFT
            )
            self.state.was_moving_right = (
                are_none_pressed and self.keys_pressed["LAST"] == arcade.key.RIGHT
            )

            self.move_state = int(is_moving_right) - int(is_moving_left)

        else:
            self.move_state = 0

    def change_texture_and_hitbox(self, texture_type: str, idx=None, change_hitbox=False):
        """Doc."""

        try:
            self.texture = getattr(self.loaded_textures, texture_type)[idx][
                self.state.is_facing_left
            ]
        except TypeError:
            # idx is None
            self.texture = getattr(self.loaded_textures, texture_type)[self.state.is_facing_left]
        except IndexError:
            # index does not match (related to how auras are handled...
            try:
                self.texture = getattr(self.loaded_textures, texture_type)[0][
                    self.state.is_facing_left
                ]
            except TypeError:
                self.texture = getattr(self.loaded_textures, texture_type)[
                    self.state.is_facing_left
                ]
        self.texture_type = texture_type

        if change_hitbox:
            self.set_hit_box_points(getattr(self.hitboxes, texture_type))
        else:  # use default hitbox
            self.set_hit_box_points(self.init_hitbox)

    def update_animation(self, delta_time: float):  # NOQA # C901
        """Doc."""

        self.timer += delta_time

        # got hit?
        if self.hit_timer > 0 and self.lives:
            self.alpha = 255 * int(not self.alpha)
            self.hit_timer -= delta_time
        else:
            self.alpha = 255

        # stop spinning
        self.change_angle = 0

        # hit animation
        if self.hit_timer >= self.INVULNERABILITY_DURATION_s * 2 / 3:
            self.change_texture_and_hitbox("getting_hit")

        # drop animation (YellowCat)
        elif self.state.drop.is_dropping:
            self.angle = 0
            if self.change_y > -20:
                self.change_texture_and_hitbox("dropping", idx=0)
            else:
                self.change_texture_and_hitbox("dropping", idx=1)

        # Jumping/Stalling/Falling animation
        elif (self.physics_engine.jumps_since_ground >= 1 or self.change_y < 0.0) and abs(
            self.change_x
        ) <= self.speeds.RUN:
            if 5 < self.change_y:
                self.change_texture_and_hitbox("jumping", change_hitbox=True)
            elif 0 < self.change_y < 5:
                self.change_texture_and_hitbox("stalling", idx=0)
            elif -5 < self.change_y < 0:
                self.change_texture_and_hitbox("stalling", idx=1)
            elif self.change_y < -5:
                self.change_texture_and_hitbox("falling")

            if self.physics_engine.jumps_since_ground >= 2:
                if self.change_y > -5:
                    self.change_angle = self.face_direction * self.spin_speed
                else:
                    self.angle = 0

        # pounce animation
        elif self.state.pounce.is_pouncing:
            if self.can_pounce_kill or self.can_swipe:  # BlueCat and YellowCat
                self.angle = self.move_state * 20
                self.change_texture_and_hitbox("scratching", change_hitbox=True)
            else:  # RedCat
                self.change_texture_and_hitbox("pouncing", change_hitbox=True)

        # air-dash animation (RedCat)
        elif self.state.air_dash.is_dashing:
            self.angle = self.move_state * 20
            self.change_texture_and_hitbox("scratching", change_hitbox=True)

        # Running animation
        elif not self.move_state == game.STOP:
            self.angle = 0
            if self.timer >= self.RUNNING_ANIMATION_FACTOR / (
                (
                    abs(self.change_x)
                    + (
                        self.acceleration_magnitude * delta_time
                        if self.acceleration * self.change_x < 0
                        or abs(self.change_x) <= self.speeds.SLIDE
                        else 0
                    )
                )
                / self.speeds.RUN
            ) / len(self.loaded_textures.running):
                self.texture_idx += 1
                self.timer = 0
            if self.texture_idx > len(self.loaded_textures.running) - 1:
                self.texture_idx = 0
            self.change_texture_and_hitbox("running", idx=self.texture_idx, change_hitbox=True)

        # Sliding animation
        elif 0 < abs(self.change_x) <= self.speeds.SLIDE:
            self.change_texture_and_hitbox("sliding", change_hitbox=True)

        # Idle animation
        else:
            self.angle = 0
            self.change_texture_and_hitbox("standing")

        # add aura when superpower is ready
        if self.state.superpower.is_ready:
            if "aura" not in self.texture_type:
                self.change_texture_and_hitbox(self.texture_type + "_aura", idx=self.texture_idx)

    def update_velocity(self, delta_time: float):
        """Doc."""

        if self.state.pounce.recovery_timer > 0:
            self.max_run_speed = self.speeds.RUN / 3
        else:
            self.max_run_speed = self.speeds.RUN

        # set acceleration
        if self.move_state == game.LEFT:
            self.acceleration = -self.acceleration_magnitude
        elif self.move_state == game.RIGHT:
            self.acceleration = self.acceleration_magnitude
        else:
            self.acceleration = 0

        if not (self.state.pounce.is_pouncing or self.state.air_dash.is_dashing):
            speed_range = Limits(-self.max_run_speed, self.max_run_speed)
            if self.change_x in speed_range:
                self.change_x = speed_range.clamp(self.change_x + self.acceleration * delta_time)
            else:  # auto-slow
                self.change_x += (
                    -math.copysign(1, self.change_x) * self.acceleration_magnitude * 2 * delta_time
                )  # TESTESTEST

            # stopping jump by letting go of key
            if (
                self.state.jump.is_jumping
                and not self.state.jump.is_falling
                and not self.keys_pressed[arcade.key.SPACE]
            ):
                self.change_y *= self.JUMP_STOP_RATE

    def jump(self, factor=1, n_jumps=1, is_killing=False):
        """Doc."""

        if self.physics_engine.can_jump() or is_killing:
            # jumping is disabled while pouncing
            if not self.state.pounce.is_pouncing:
                self.change_y += self.speeds.JUMP * factor
                for i in range(n_jumps):
                    self.physics_engine.increment_jump_counter()
                # Play the jump sound
                arcade.play_sound(self.jump_sound, volume=0.1)

        else:  # RedCat only
            with suppress(AttributeError):
                self.air_dash()

    def pounce(self):
        """Doc."""

        self.state.pounce.is_pouncing = True
        self.state.pounce.direction = self.move_state
        self.state.pounce.recovery_timer = self.POUNCE_RECOV
        self.pounce_timer = self.POUNCE_DURATION

    def apply_friction(self):
        if self.move_state != math.copysign(1, self.change_x) and not self.state.is_in_air:
            self.change_x *= game.FRICTION
            if abs(self.change_x) < 1:
                self.change_x = 0

    def can_kill_cat(self, cat) -> bool:
        """Doc."""

        did_kill = False

        # area kill when dropping (YellowCat)
        if self.state.drop.is_dropping:
            above_ground_height = self.bottom - self.ground_height
            if above_ground_height <= cat.height:
                did_kill = abs(self.center_x - cat.center_x) < cat.width * abs(self.change_y / 15)
            else:
                return False

        # pounce-kill (BlueCat)
        elif self.can_pounce_kill and self.state.pounce.is_pouncing:
            self.state.pounce.is_pouncing = False
            self.jump(factor=2, n_jumps=2, is_killing=True)
            self.change_x *= 0.5
            return True

        # pounce-swipe (YellowCat)
        elif self.can_swipe and self.state.pounce.is_pouncing:
            if cat.scale_x * 0.9 < self.scale_x < cat.scale_x * 1.1:
                return True

        elif self.state.air_dash.is_dashing:
            return True

        # jump kill
        else:
            did_kill = self.bottom > cat.top - cat.height / 2 and self.hit_timer <= 0

            if did_kill:
                self.change_y = 0
                self.jump(factor=2, is_killing=True)

        return did_kill

    def get_hit(self, cat):
        """Doc."""

        if not (
            self.state.drop.is_dropping
            or hasattr(self, "air_dash")
            and self.state.pounce.is_pouncing
        ):
            if self.lives >= 1 and self.hit_timer <= 0:
                if self.lives > 1:
                    self.hit_timer = self.INVULNERABILITY_DURATION_s
                    self.change_x = choice([-self.speeds.POUNCE, self.speeds.POUNCE])
                    self.change_y = uniform(0, self.speeds.POUNCE)
                self.lives -= 1
                arcade.play_sound(self.get_hit_sound)

    def poof(self):
        """Doc."""

        poof = self.poof_sprite
        poof.reset(Vector(self.center_x, self.center_y - self.height / 3), self.scale_x)
        return poof

    def die(self):
        """Doc."""

        self.is_alive = False
        self.kill()

    def update_superpower_timer(self, delta_time):
        """Doc."""

        if self.superpower_timer > 0:
            self.superpower_timer -= delta_time
        else:
            self.superpower_timer = 0.0
            self.state.superpower.is_on = False

    def activate_superpower(self):
        """Doc."""

        self.state.superpower.is_on = True
        self.state.superpower.is_ready = False
        self.superpower_timer = 10


class BlueCat(PlayerCat):
    """Doc."""

    color_str = "deepskyblue"

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(
            *args,
            speeds=SimpleNamespace(RUN=10, SLIDE=5, JUMP=20, POUNCE=35),
            acceleration_magnitude=0.75 * 60,
            color_str=self.color_str,
            aura_color_str="skyblue",
            scale=game.CHARACTER_SCALING,
            lives=3,
            can_pounce_kill=True,
            **kwargs,
        )


class RedCat(PlayerCat):
    """Doc."""

    RUNNING_ANIMATION_FACTOR = 0.16
    POUNCE_RECOV = 40  # TODO: units?..
    AIR_DASH_DURATION = 12  # TODO: units?..

    color_str = "crimson"

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(
            *args,
            speeds=SimpleNamespace(RUN=12, SLIDE=6, JUMP=24, POUNCE=42),
            acceleration_magnitude=0.9 * 60,
            color_str=self.color_str,
            aura_color_str="palevioletred",
            scale=game.CHARACTER_SCALING * 0.9,
            lives=2,
            **kwargs,
        )

    def air_dash(self):
        """Doc"""

        if self.state.is_in_air and self.physics_engine.jumps_since_ground < 3:
            self.physics_engine.increment_jump_counter()
            self.state.air_dash.is_dashing = True
            self.air_dash_timer = self.AIR_DASH_DURATION
            self.state.air_dash.direction = self.move_state


class YellowCat(PlayerCat):
    """Doc."""

    RUNNING_ANIMATION_FACTOR = 0.24
    POUNCE_RECOV = 60  # TODO: units?..

    color_str = "gold"

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(
            *args,
            speeds=SimpleNamespace(RUN=8, SLIDE=4, JUMP=16, POUNCE=28),
            acceleration_magnitude=0.6 * 60,
            color_str=self.color_str,
            aura_color_str="yellow",
            scale=game.CHARACTER_SCALING * 1.1,
            lives=4,
            can_swipe=True,
            **kwargs,
        )

        self.state.drop.can_drop = True

    def drop(self):
        """Doc."""

        above_ground_height = self.bottom - self.ground_height
        if self.state.is_in_air and above_ground_height > self.height * 2.5:
            self.state.drop.is_dropping = True
            self.change_x = 0.0
            self.change_y = 0.0


class Popsicle(BasicSprite):
    """Doc."""

    def __init__(
        self,
        init_position: Vector,
        throw_speed_ppf: float,
        throw_angle_degrees: int,
        *args,
        type="regular",
        **kwargs,
    ) -> None:
        super().__init__(init_position, **kwargs)

        self.type = type

        x_speed = -throw_speed_ppf * math.cos(throw_angle_degrees * math.pi / 180)
        y_speed = throw_speed_ppf * math.sin(throw_angle_degrees * math.pi / 180)

        self.change_x = x_speed
        self.change_y = y_speed
        self.change_angle = math.copysign(1, x_speed) * throw_speed_ppf

        self.color_str: str = None
        self.is_on_ground = False

    def move(self, delta_time):
        """Doc."""

        # update velocity
        if not self.is_on_ground:
            self.change_y -= game.GRAVITY * 250 * delta_time

        # change position
        self.center_x += self.change_x * delta_time
        self.center_y += self.change_y * delta_time

        # spin
        self.angle += self.change_angle * delta_time

    def bounce(self):
        """Doc."""

        if self.change_y < -0.001:
            self.change_angle *= uniform(-1.5, 1.5)
            self.change_y *= -uniform(0.3, 0.5)
        else:
            self.is_on_ground = True
            self.stop()

    def stop(self, should_stop_y=True):
        """Doc."""

        self.change_x = 0
        if should_stop_y:
            self.change_y = 0.0
        self.change_angle = 0
        self.angle = 0


class RegularPopsicle(Popsicle):
    """
    An collectible popsicle sprite. Gets thrown away by the 'Ice-Cream Man' and possibly collected by the 'Cat'.
    """

    MAIN_PATH = ASSETS_PATH / "images" / "items"
    white_pop_path = MAIN_PATH / "popsicleWhite.png"
    BASE_POINTS = 10
    FROZEN_TIME = 1  # seconds?
    MELT_RATE = 5  # units?

    color_textures_dict = {color_str: PopsicleColorTextures(color_str) for color_str in game.COLORS}

    def __init__(
        self,
        color_str: str,
        *args,
    ) -> None:
        super().__init__(*args, scale=game.POPSICLE_SCALING)

        # Load textures
        self.color_str = color_str
        self.loaded_textures = self.color_textures_dict[color_str].textures
        self.hitboxes = SimpleNamespace(
            **{
                name: (txtr[0].hit_box_points if isinstance(txtr, list) else txtr.hit_box_points)
                for name, txtr in vars(self.loaded_textures).items()
            }
        )

        self.texture = self.loaded_textures.standing
        self.melt_textures_iter = iter(self.loaded_textures.melting)

        self.color_str = color_str
        self.point_value = self.BASE_POINTS

        self.frozen_timer = 0.0
        self.melting_timer = 0.0

    def melt(self, delta_time: float):
        """Doc."""

        if self.frozen_timer > self.FROZEN_TIME:
            self.melting_timer += delta_time
            if self.melting_timer * self.MELT_RATE > 1:
                try:
                    with suppress(IndexError):  # arcade - pop from an empty deque
                        self.texture = next(self.melt_textures_iter)
                    self.point_value -= int(self.BASE_POINTS * 0.1)
                except StopIteration:
                    self.kill()
                else:
                    self.melting_timer = 0.0
        else:
            self.frozen_timer += delta_time


class HeartPopsicle(Popsicle):
    """Doc."""

    TEXTURE_PATH = ASSETS_PATH / "images" / "items" / "popsicleHeart.png"

    def __init__(
        self,
        *args,
    ) -> None:
        super().__init__(*args, type="heart", scale=game.POPSICLE_SCALING)

        self.texture = self.load_texture(
            self.TEXTURE_PATH,
        )

        self.point_value = 100


class IceCreamTruck(BasicSprite):
    """Doc."""

    MAIN_TEXTURE_PATH = ASSETS_PATH / "images" / "enemies"
    ANIMATION_RATE = 10
    SHAKE_PAUSE = 1
    THROW_PROBABILITY = 0.03
    THROW_SPEED = 600
    angle: float

    def __init__(self, init_position: Vector, **kwargs):
        super().__init__(
            init_position, path_or_texture=self.MAIN_TEXTURE_PATH / "truckIceCream1.png", **kwargs
        )

        # Default to face-right
        self.face_direction = game.FACE_RIGHT

        # Used for flipping between image sequences
        self.texture_idx = 0

        # Load textures
        self.loaded_textures = SimpleNamespace(
            standing=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "truckIceCream1.png"),
        )

        # Set the initial texture
        self.texture = self.loaded_textures.standing.RIGHT

        self.throw_probability_frame = self.THROW_PROBABILITY

        # timers
        self.animation_timer = 0.0
        self.shaking_timer = 0.0

        # initiate throw probabilities
        self.reset_throw_probabilities()

    def reset_throw_probabilities(self):
        """Doc."""

        self.throw_probability_frame = self.THROW_PROBABILITY
        self.color_pop_probs_dict = {
            pop_color: self.throw_probability_frame for pop_color in list(game.COLORS)
        }
        self.heart_pop_prob = self.throw_probability_frame * 0.005

    def throw_popsicle(self):
        """Throw a random (color, angle) popsicle."""

        if random() < self.heart_pop_prob:
            self.shaking_timer = self.SHAKE_PAUSE  # stop shaking
            return HeartPopsicle(
                Vector(self.center_x, self.center_y),
                self.THROW_SPEED * uniform(0.75, 1.15),
                randint(75, 105),
            )

        elif random() < self.throw_probability_frame:
            color_str = choices(
                list(self.color_pop_probs_dict.keys()),
                weights=list(self.color_pop_probs_dict.values()),
            )[0]
            self.shaking_timer = self.SHAKE_PAUSE  # stop shaking
            return RegularPopsicle(
                color_str,
                Vector(self.center_x, self.center_y),
                self.THROW_SPEED * uniform(0.25, 1),
                randint(45, 135),
            )

    def update_animation(self, delta_time: float):
        """Doc."""

        self.shaking_timer -= delta_time
        if self.shaking_timer <= 0:
            self.animation_timer += delta_time
            if self.animation_timer * self.ANIMATION_RATE > 1:
                self.angle = -math.copysign(1, self.angle) * uniform(0.5, 3)
                self.animation_timer = 0.0
        else:
            self.angle = 0.0
