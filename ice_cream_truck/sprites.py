import math
from collections import namedtuple
from pathlib import Path
from random import choice, randint, random, uniform
from types import SimpleNamespace

import arcade
import game_constants as game
import numpy as np
import PIL
from helper import Limits, Vector, tint_greyscale_pixels

# Assets path
ASSETS_PATH = Path(__file__).resolve().parent.parent / "assets"


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


class BasicSprite(arcade.Sprite):

    texture: arcade.Texture

    def __init__(self, init_position: Vector, **kwargs):
        init_x, init_y = init_position
        super().__init__(center_x=init_x, center_y=init_y, **kwargs)

        self.is_off_screen = False

    def load_texture(self, filename, color_tint: str = None, **kwargs):
        """
        Load a texture pair, with the second being a mirror image.
        Optionally, tint the greyscale pixels of the texture.
        """

        texture = arcade.load_texture(filename)

        if color_tint is not None:
            tinted_texture = tint_greyscale_pixels(texture.image, color_tint, **kwargs)
            texture = arcade.Texture(str(tinted_texture), tinted_texture)

        return texture

    def load_texture_pair(self, filename, color_tint: str = None, **kwargs):
        """
        Load a texture pair, with the second being a mirror image.
        Optionally, tint the greyscale pixels of the texture.
        """

        right_texture = arcade.load_texture(filename)
        left_texture = arcade.load_texture(filename, flipped_horizontally=True)

        if color_tint is not None:
            tinted_right = tint_greyscale_pixels(right_texture.image, color_tint, **kwargs)
            tinted_left = tint_greyscale_pixels(left_texture.image, color_tint, **kwargs)
            right_texture = arcade.Texture(str(tinted_right), tinted_right)
            left_texture = arcade.Texture(str(tinted_left), tinted_left)

        TexturePair = namedtuple("TexturePair", "RIGHT LEFT")
        return TexturePair(
            RIGHT=right_texture,
            LEFT=left_texture,
        )

    def restrict_position(self, map_width, should_kill=False):
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
        if self.bottom < 0:
            self.bottom = 0

    def tint_texture(self, texture: PIL.Image, color: str, **kwargs):
        """Doc."""

        self.texture = tint_greyscale_pixels(self.texture, color, **kwargs)


class Poof(BasicSprite):
    """Doc."""

    MAIN_TEXTURE_PATH = ASSETS_PATH / "images" / "gifs"
    ANIMATION_RATE = 1 / 0.05
    BASE_SCALE = 0.3

    def __init__(
        self,
        init_position: Vector,
        color_str: str,
        **kwargs,
    ):

        # TODO: perhaps there's no need for initial textures!
        super().__init__(init_position, hit_box_algorithm=None, scale=self.BASE_SCALE, **kwargs)

        self.loaded_textures = [
            self.load_texture(self.MAIN_TEXTURE_PATH / f"poof{i}.png", color_str)
            for i in range(1, 16)
        ]
        #        self.animated_textures = iter(self.loaded_textures)

        self.timer = 0.0
        self.texture_idx = 0

    def reset(self, init_position: Vector, scale: float):
        """Doc."""

        self.center_x = init_position.x
        self.center_y = init_position.y
        self.scale = self.BASE_SCALE * scale
        self.texture_idx = 0
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

    MAIN_TEXTURE_PATH = ASSETS_PATH / "images" / "cat"
    RUNNING_ANIMATION_FACTOR = 0.4  # TODO: twice that of player (should be determined by speed)
    MAX_LIVES = 1
    texture: arcade.texture.Texture
    change_x: float
    change_y: float
    center_y: float
    poof_dict = {color_str: Poof(Vector(0, 0), color_str) for color_str in game.COLORS}

    def __init__(
        self,
        init_position: Vector,
        speeds: SimpleNamespace,
        acceleration_magnitude: float,
        color_str: str,
        game_view: arcade.View,
        scale=1,
        **kwargs,
    ):

        super().__init__(
            init_position,
            filename=self.MAIN_TEXTURE_PATH / "catStanding.png",
            hit_box_algorithm="Detailed",
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
        self.loaded_textures = SimpleNamespace(
            standing=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catStanding.png", color_str),
            running=[
                self.load_texture_pair(self.MAIN_TEXTURE_PATH / f"catRunning{i}.png", color_str)
                for i in (1, 2, 3, 4)
            ],
            pouncing=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catRunning4.png", color_str),
            sliding=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catRunning1.png", color_str),
            jumping=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catJumping.png", color_str),
            stalling=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catStalling.png", color_str),
            falling=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catFalling.png", color_str),
        )
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
        self.delta_v = 0.0

        # for setting running animation frequency
        self.timer = 0.0
        self.face_switch_timer = 0.0

        self.sought_popsicle: Popsicle = None

    def change_texture_and_hitbox(self, texture_name: str, idx=None, change_hitbox=False):
        """Doc."""

        if idx is not None:
            self.texture = getattr(self.loaded_textures, texture_name)[idx][
                self.state.is_facing_left
            ]
        else:
            self.texture = getattr(self.loaded_textures, texture_name)[self.state.is_facing_left]

        if change_hitbox:
            self.hit_box = getattr(self.hitboxes, texture_name)
        else:  # use default hitbox
            self.hit_box = self.init_hitbox

    def update_animation(self, delta_time: float):
        """Doc."""

        self.face_switch_timer += delta_time

        # update state
        if self.delta_v != 0:
            self.move_state = int(math.copysign(1, self.delta_v))
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
            elif -5 < self.change_y < 5:
                self.change_texture_and_hitbox("stalling", change_hitbox=True)
            elif self.change_y < -5:
                self.change_texture_and_hitbox("falling")

        # pounce animation
        elif self.state.pounce.is_pouncing:
            self.change_texture_and_hitbox("pouncing")

        # Running animation
        elif not self.mode == "waiting":
            if self.timer >= self.RUNNING_ANIMATION_FACTOR / (
                (
                    abs(self.change_x)
                    + (
                        self.acceleration_magnitude * delta_time * 10
                        if self.delta_v * self.change_x < 0.0
                        or abs(self.change_x) <= self.speeds.SLIDE
                        else 0
                    )
                )
                / self.speeds.RUN
            ) / len(self.loaded_textures.running):
                self.texture_idx += 1
                self.timer = 0
            if self.texture_idx == len(self.loaded_textures.running):
                self.texture_idx = 0
            self.change_texture_and_hitbox("running", idx=self.texture_idx, change_hitbox=True)

        # Idle animation
        else:
            self.change_texture_and_hitbox("standing")

    def seek(self, delta_time: float):
        """Fetch closest self-colored popsicle if one exists, otherwise go to ice cream truck"""

        # change position
        if self.state.is_in_air:
            self.center_y += self.change_y
            # change speed (due to 'gravity')
            self.change_y -= game.GRAVITY * 0.1
        else:
            self.change_y = 0.0
            self.center_y = self._height // 2 + 130

        self.center_x += self.change_x

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
            self.delta_v = (
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
            self.delta_v = (
                math.copysign(1, self.sought_popsicle.center_x - self.center_x)
                * self.acceleration_magnitude
            )

        finally:
            if (
                self.mode in {"returning", "waiting"}
                and (abs(self.truck_disp) <= self.game_view.ice_cream_truck._width / 2)
                and self.change_x < self.speeds.SLIDE
            ):
                self.change_x = 0.0
                self.mode = "waiting"
            else:
                self.change_x = Limits(-self.max_run_speed, self.max_run_speed).clamp(
                    self.change_x + self.delta_v
                )

    def poof(self):
        """Doc."""

        poof = self.poof_dict[self.color_str]
        poof.reset(Vector(self.center_x, self.center_y - self.height / 3), self.scale)
        return poof


class Player(BasicSprite):
    """Doc."""

    MAIN_TEXTURE_PATH = ASSETS_PATH / "images" / "cat"
    RUNNING_ANIMATION_FACTOR = 0.2
    JUMP_STOP_RATE = 0.9
    MAX_LIVES = 3
    INV_TIME = 1.5  # seconds?
    texture: arcade.texture.Texture
    alpha: int

    def __init__(
        self,
        init_position: Vector,
        speeds: SimpleNamespace,
        acceleration_magnitude: float,
        color_str: str,
        map_width,
        keys_pressed,
        **kwargs,
    ):

        super().__init__(
            init_position,
            filename=self.MAIN_TEXTURE_PATH / "catStanding.png",
            hit_box_algorithm="Detailed",
            **kwargs,
        )

        # initial lives
        self.is_alive = True
        self.lives = self.MAX_LIVES
        self.hit_timer = 0.0

        # get default/initial hitbox
        self.init_hitbox = self.texture.hit_box_points

        # hold map width
        self.map_width = map_width

        # hold pressed keys
        self.keys_pressed = keys_pressed

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
            is_in_air=False,
        )

        # Default to face-right
        self.face_direction = game.FACE_RIGHT

        # Used for flipping between image sequences
        self.texture_idx = 0

        # Load textures
        self.color_str = color_str
        self.loaded_textures = SimpleNamespace(
            standing=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catStanding.png", color_str),
            running=[
                self.load_texture_pair(self.MAIN_TEXTURE_PATH / f"catRunning{i}.png", color_str)
                for i in (1, 2, 3, 4)
            ],
            pouncing=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catRunning4.png", color_str),
            sliding=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catRunning1.png", color_str),
            jumping=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catJumping.png", color_str),
            stalling=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catStalling.png", color_str),
            falling=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catFalling.png", color_str),
        )
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

        # for setting running animation frequency
        self.timer = 0.0

        # poof
        self.poof_sprite = Poof(Vector(0, 0), self.color_str)

    def update_state(self, can_jump, n_jumps_since_ground, **kwargs):
        """Doc."""

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
        self.state.pounce.is_pouncing = abs(self.change_x) == self.speeds.POUNCE and not can_jump
        self.state.pounce.finishing_pounce = abs(self.change_x) == self.speeds.POUNCE and can_jump

        # pounce recovery
        if self.state.pounce.finishing_pounce:
            self.state.pounce.recovery_timer = 50
        elif self.state.pounce.recovery_timer > 0:
            self.state.pounce.recovery_timer -= 1

        # check if falling
        self.state.jump.is_falling = self.change_y < 0

        # check if in air
        self.state.is_in_air = self.state.jump.is_jumping or self.state.pounce.is_pouncing

        self._update_move_direction()

    def _update_move_direction(self):
        """Decide if player is moving left, moving right, or stopping, based on pressed keys"""

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
        is_changing_to_right = are_both_pressed and self.keys_pressed["LAST"] == arcade.key.RIGHT
        is_moving_left = is_only_left_pressed or is_changing_to_left
        is_moving_right = is_only_right_pressed or is_changing_to_right
        self.state.was_moving_left = (
            are_none_pressed and self.keys_pressed["LAST"] == arcade.key.LEFT
        )
        self.state.was_moving_right = (
            are_none_pressed and self.keys_pressed["LAST"] == arcade.key.RIGHT
        )

        self.move_state = int(is_moving_right) - int(is_moving_left)

    def change_texture_and_hitbox(self, texture_name: str, idx=None, change_hitbox=False):
        """Doc."""

        if idx is not None:
            self.texture = getattr(self.loaded_textures, texture_name)[idx][
                self.state.is_facing_left
            ]
        else:
            self.texture = getattr(self.loaded_textures, texture_name)[self.state.is_facing_left]

        if change_hitbox:
            self.hit_box = getattr(self.hitboxes, texture_name)
        else:  # use default hitbox
            self.hit_box = self.init_hitbox

    def update_animation(self, delta_time: float, jumps_since_ground: int):
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

        # Jumping/Stalling/Falling animation
        if (jumps_since_ground >= 1 or self.change_y < 0.0) and abs(
            self.change_x
        ) <= self.speeds.RUN:
            if 5 < self.change_y:
                self.change_texture_and_hitbox("jumping", change_hitbox=True)
            elif -5 < self.change_y < 5:
                self.change_texture_and_hitbox("stalling", change_hitbox=True)
            elif self.change_y < -5:
                self.change_texture_and_hitbox("falling")

            if jumps_since_ground >= 2:
                if self.change_y > -5:
                    self.change_angle = -self.face_direction * self.spin_speed
                else:
                    self.angle = 0

        # pounce animation
        elif self.state.pounce.is_pouncing:
            self.change_texture_and_hitbox("pouncing")

        # Running animation
        elif not self.move_state == game.STOP:
            self.angle = 0
            if self.timer >= self.RUNNING_ANIMATION_FACTOR / (
                (
                    abs(self.change_x)
                    + (
                        self.acceleration_magnitude * 20
                        if self.acceleration * self.change_x < 0
                        or abs(self.change_x) <= self.speeds.SLIDE
                        else 0
                    )
                )
                / self.speeds.RUN
            ) / len(self.loaded_textures.running):
                self.texture_idx += 1
                self.timer = 0
            if self.texture_idx == len(self.loaded_textures.running):
                self.texture_idx = 0
            self.change_texture_and_hitbox("running", idx=self.texture_idx, change_hitbox=True)

        # Sliding animation
        elif 0 < abs(self.change_x) <= self.speeds.SLIDE:
            self.change_texture_and_hitbox("sliding", change_hitbox=True)

        # Idle animation
        else:
            self.angle = 0
            self.change_texture_and_hitbox("standing")

    def update_velocity(self):  # , delta_time: float):
        """Doc."""
        # TODO: attempt to seperate directions from magnitudes? (1D vector) - could make code clearer

        if self.state.pounce.finishing_pounce:
            self.change_x *= self.speeds.SLIDE / self.speeds.POUNCE

        if self.state.pounce.recovery_timer > 0:
            self.max_run_speed = self.speeds.RUN / 1.5
            self.acceleration_magnitude = game.PLAYER_ACCELERATION_MAGNITUDE / 3
        else:
            self.max_run_speed = self.speeds.RUN
            self.acceleration_magnitude = game.PLAYER_ACCELERATION_MAGNITUDE

        if not self.state.pounce.is_pouncing:
            if self.move_state == game.LEFT:
                self.acceleration = -self.acceleration_magnitude
            elif self.move_state == game.RIGHT:
                self.acceleration = self.acceleration_magnitude
            else:
                self.acceleration = 0

            self.change_x = self.change_x = Limits(-self.max_run_speed, self.max_run_speed).clamp(
                self.change_x + self.acceleration
            )

            # stopping jump by letting go of key
            if (
                self.state.jump.is_jumping
                and not self.state.jump.is_falling
                and not self.keys_pressed[arcade.key.SPACE]
            ):
                self.change_y *= self.JUMP_STOP_RATE

    def jump(self, factor=1):
        """Doc."""

        # jumping is disabled while pouncing
        if self.state.pounce.is_pouncing:
            self.keys_pressed[arcade.key.SPACE] = False
        else:
            self.change_y += self.speeds.JUMP * factor

    def pounce(self):
        """Doc."""

        self.state.pounce.is_pouncing = True
        if self.move_state == game.LEFT:
            self.change_x = -self.speeds.POUNCE
        elif self.move_state == game.RIGHT:
            self.change_x = self.speeds.POUNCE
        self.change_y = 6

    def apply_friction(self):

        if self.move_state == game.STOP and not self.state.is_in_air:
            self.change_x *= game.FRICTION
            if abs(self.change_x) < 1:
                self.change_x = 0

    def can_kill_cat(self, cat) -> bool:
        """Doc."""

        return (
            self.change_y < 0
            and abs(self.center_x - cat.center_x) < cat.width / 3
            and self.hit_timer <= self.INV_TIME * 0.9
        )

    def get_hit(self, cat):
        """Doc."""

        if (
            self.change_y >= 0
            and abs(self.center_x - cat.center_x) < cat.width / 2
            and abs(self.center_y - cat.center_y) < cat.height / 2
        ):
            if self.lives >= 1 and self.hit_timer <= 0:
                if self.lives > 1:
                    self.hit_timer = self.INV_TIME  # seconds?
                    self.change_x = choice([-50, 50])
                self.lives -= 1

    def poof(self):
        """Doc."""

        poof = self.poof_sprite
        poof.reset(Vector(self.center_x, self.center_y - self.height / 3), self.scale)
        return poof

    def die(self):
        """Doc."""

        self.is_alive = False
        self.kill()


class Popsicle(BasicSprite):
    """
    An collectible popsicle sprite. Gets thrown away by the 'Ice-Cream Man' and possibly collected by the 'Cat'.
    """

    MAIN_PATH = ASSETS_PATH / "images" / "items"
    white_pop_path = MAIN_PATH / "popsicleWhite.png"
    BASE_POINTS = 10
    FROZEN_TIME = 1  # seconds?
    MELT_RATE = 5  # units?
    alpha: int

    def __init__(
        self,
        init_position: Vector,
        throw_speed_ppf: float,
        throw_angle_degrees: int,
        color_str: str,
    ) -> None:

        super().__init__(init_position, scale=game.POPSICLE_SCALING)

        self.texture = self.load_texture(
            self.white_pop_path,
            color_str,
            linear_beta=(0, 1),
            threshold_deviation_from_grey=10,
            should_tint_black=False,
        )

        melt_textures = []
        h = self.texture.height
        w = self.texture.width
        for x_factor, y_factor in zip(np.linspace(0.5, 0.875, 10), np.linspace(0, 0.2, 10)):
            arr_img = np.array(self.texture.image)
            arr_img[: int(h * y_factor), :, 3] = 0
            arr_img[:, : int(w / 2 * x_factor), 3] = 0
            arr_img[:, int(w * (1 - x_factor / 2)) :, 3] = 0
            image = PIL.Image.fromarray(arr_img)
            melt_textures.append(arcade.Texture(str(image), image))
        self.melt_textures_iter = iter(melt_textures)

        x_speed = -throw_speed_ppf * math.cos(throw_angle_degrees * math.pi / 180)
        y_speed = throw_speed_ppf * math.sin(throw_angle_degrees * math.pi / 180)
        self.color_str = color_str
        self.point_value = self.BASE_POINTS

        self.hitbox = self.texture.hit_box_points

        self.change_x = x_speed
        self.change_y = y_speed
        self.change_angle = -math.copysign(1, x_speed) * throw_speed_ppf
        self.frozen_timer = 0.0
        self.melting_timer = 0.0

    def move(self):
        """Doc."""

        # change position
        self.center_x += self.change_x
        self.center_y += self.change_y

        # change speed (due to 'gravity')
        self.change_y -= game.GRAVITY * 0.1

        # spin
        self.angle += self.change_angle

    def bounce(self):
        """Doc."""

        if self.change_y < -0.01:
            self.change_angle *= uniform(-1.5, 1.5)
            self.change_y *= -uniform(0.25, 0.75)
        else:
            self.stop()

    def stop(self, should_stop_y=True):
        """Doc."""

        self.change_x = 0
        if should_stop_y:
            self.change_y = 0.0
        self.change_angle = 0
        self.angle = 0

    def melt(self, delta_time: float):
        """Doc."""

        if self.frozen_timer > self.FROZEN_TIME:

            self.melting_timer += delta_time
            if self.melting_timer * self.MELT_RATE > 1:
                try:
                    self.texture = next(self.melt_textures_iter)
                    self.point_value -= int(self.BASE_POINTS * 0.1)
                except StopIteration:
                    self.kill()
                else:
                    self.melting_timer = 0.0
        else:
            self.frozen_timer += delta_time


class IceCreamTruck(BasicSprite):
    """Doc."""

    MAIN_TEXTURE_PATH = ASSETS_PATH / "images" / "enemies"

    def __init__(self, init_position: Vector, throw_probability_frame: float, **kwargs):
        super().__init__(
            init_position, filename=self.MAIN_TEXTURE_PATH / "truckIceCream1.png", **kwargs
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

        self.throw_probability_frame = throw_probability_frame

    def throw_popsicle(self):
        """Throw a random (color, angle) popsicle."""

        if random() < self.throw_probability_frame:
            return Popsicle(
                Vector(self.center_x, self.center_y),
                throw_speed_ppf=game.PLAYER_MOVE_SPEED.RUN * uniform(0.25, 1),
                throw_angle_degrees=randint(45, 135),
                color_str=choice(list(game.COLORS)),
            )
