import math
from collections import namedtuple
from pathlib import Path
from random import choice, randint, random, uniform
from types import SimpleNamespace

import arcade
import game_constants as game
import PIL
from helper import Vector, tint_greyscale_pixels

# Assets path
ASSETS_PATH = Path(__file__).resolve().parent.parent / "assets"


class BasicSprite(arcade.Sprite):

    texture: arcade.Texture

    def __init__(self, init_position: Vector, texture_path: Path, **kwargs):
        init_x, init_y = init_position
        super().__init__(filename=texture_path, center_x=init_x, center_y=init_y, **kwargs)

    def load_texture_pair(self, filename, color_tint: str = None):
        """
        Load a texture pair, with the second being a mirror image.
        Optionally, tint the greyscale pixels of the texture.
        """

        right_texture = arcade.load_texture(filename)
        left_texture = arcade.load_texture(filename, flipped_horizontally=True)

        if color_tint is not None:
            right_texture.image = tint_greyscale_pixels(right_texture.image, color_tint)
            left_texture.image = tint_greyscale_pixels(left_texture.image, color_tint)

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
        if self.right >= map_width:
            self.right = map_width
            if should_kill:
                self.kill()
        if self.bottom < 0:
            self.bottom = 0

    def tint_texture(self, texture: PIL.Image, color: str, **kwargs):
        """Doc."""

        self.texture = tint_greyscale_pixels(self.texture, color, **kwargs)


class Popsicle(BasicSprite):
    """
    An collectible popsicle sprite. Gets thrown away by the 'Ice-Cream Man' and possibly collected by the 'Cat'.
    """

    MAIN_PATH = ASSETS_PATH / "images" / "items"
    pop_color_filename_dict = {
        color: f"popsicle{color.capitalize()}.png" for color in game.POPSICLE_COLORS
    }
    BASE_POINTS = 10
    FROZEN_TIME = 1  # seconds?
    MELT_RATE = 0.99  # units?
    alpha: int

    def __init__(
        self, init_position: Vector, throw_speed_ppf: float, throw_angle_degrees: int, color: str
    ) -> None:

        filename = self.pop_color_filename_dict[color]
        super().__init__(init_position, self.MAIN_PATH / filename, scale=game.POPSICLE_SCALING)

        x_speed = -throw_speed_ppf * math.cos(throw_angle_degrees * math.pi / 180)
        y_speed = throw_speed_ppf * math.sin(throw_angle_degrees * math.pi / 180)
        self.popsicle_color = color
        self.point_value = self.BASE_POINTS

        self.hitbox = self.texture.hit_box_points

        self.change_x = x_speed
        self.change_y = y_speed
        self.change_angle = -math.copysign(1, x_speed) * throw_speed_ppf
        self.melt_timer = 0.0

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
            self.change_y *= -0.5
            self.change_y *= 0.75
        else:
            self.stop()

    def stop(self, should_stop_y=True):
        """Doc."""

        self.change_x = 0
        if should_stop_y:
            self.change_y = 0.0
        self.change_angle = 0
        self.angle = 0

    def melt(self, time_delta: float):
        """Doc."""

        self.melt_timer += time_delta
        if self.melt_timer > self.FROZEN_TIME:
            self.alpha = int(self.MELT_RATE * self.alpha)
            self.point_value = int(self.alpha / 255 * self.BASE_POINTS)
            if self.alpha < 20:
                self.kill()


class IceCreamTruck(BasicSprite):
    """Doc."""

    MAIN_TEXTURE_PATH = ASSETS_PATH / "images" / "enemies"

    def __init__(self, init_position: Vector, throw_probability_frame: float, **kwargs):
        super().__init__(init_position, self.MAIN_TEXTURE_PATH / "truckIceCream1.png", **kwargs)

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
                color=choice(game.POPSICLE_COLORS),
            )


class Player(BasicSprite):
    """Doc."""

    MAIN_TEXTURE_PATH = ASSETS_PATH / "images" / "player"
    RUNNING_ANIMATION_FACTOR = 0.2
    JUMP_STOP_RATE = 0.9
    MOVE_STATE_DICT = {0: "STOP", 1: "RIGHT", -1: "LEFT"}
    texture: arcade.texture.Texture

    def __init__(
        self,
        init_position: Vector,
        speeds: SimpleNamespace,
        acceleration_magnitude: float,
        color: str,
        map_width,
        keys_pressed,
        **kwargs,
    ):

        super().__init__(init_position, self.MAIN_TEXTURE_PATH / "catStanding.png", **kwargs)

        # get default/initial hitbox
        self.init_hitbox = self.texture.hit_box_points

        # hold map width
        self.map_width = map_width

        # hold pressed keys
        self.keys_pressed = keys_pressed

        # initialize state
        self.move_state = "STOP"
        self.state = SimpleNamespace(
            is_facing_left=False,
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
        self.loaded_textures = SimpleNamespace(
            standing=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catStanding.png", color),
            running=[
                self.load_texture_pair(self.MAIN_TEXTURE_PATH / f"catRunning{i}.png", color)
                for i in (1, 2, 3, 4)
            ],
            pouncing=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catRunning4.png", color),
            sliding=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catRunning1.png", color),
            jumping=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catJumping.png", color),
            stalling=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catStalling.png", color),
            falling=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catFalling.png", color),
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
        self.time_accumulator = 0.0

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

        self.move_state = self.MOVE_STATE_DICT[int(is_moving_right) - int(is_moving_left)]

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

        self.time_accumulator += delta_time

        # stop spinning
        self.change_angle = 0

        # Jumping/Stalling/Falling animation
        if (jumps_since_ground >= 1 or self.change_y < 0) and abs(self.change_x) <= self.speeds.RUN:
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
        elif abs(self.change_x) > self.speeds.SLIDE:
            self.angle = 0
            if self.time_accumulator >= self.RUNNING_ANIMATION_FACTOR / (
                abs(self.change_x) / self.speeds.RUN
            ) / len(self.loaded_textures.running):
                self.texture_idx += 1
                self.time_accumulator = 0
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

    def update_velocity(self):
        """Doc."""
        # TODO: attempt to seperate directions from magnitudes? (1D vector) - could make code clearer
        # TODO: fix pouncing with new 'state' paradigm

        if self.state.pounce.finishing_pounce:
            #            self.change_x = self.speeds.SLIDE
            if self.move_state == "LEFT" or self.state.was_moving_left:
                self.change_x = -self.speeds.SLIDE
            if self.move_state == "RIGHT" or self.state.was_moving_right:
                self.change_x = self.speeds.SLIDE

        if self.state.pounce.recovery_timer > 0:
            self.acceleration_magnitude = game.PLAYER_ACCELERATION_MAGNITUDE / 5
        else:
            self.acceleration_magnitude = game.PLAYER_ACCELERATION_MAGNITUDE

        if not self.state.pounce.is_pouncing:
            if self.move_state == "LEFT":
                self.acceleration = -self.acceleration_magnitude
            elif self.move_state == "RIGHT":
                self.acceleration = self.acceleration_magnitude
            else:
                self.acceleration = 0

            self.change_x += self.acceleration

            if abs(self.change_x) > self.max_run_speed:
                if self.move_state == "RIGHT":
                    self.change_x = self.max_run_speed
                elif self.move_state == "LEFT":
                    self.change_x = -self.max_run_speed

            # stopping jump by letting go of key
            if (
                self.state.jump.is_jumping
                and not self.state.jump.is_falling
                and not self.keys_pressed[arcade.key.SPACE]
            ):
                self.change_y *= self.JUMP_STOP_RATE

    def jump(self):
        """Doc."""

        # jumping is disabled while pouncing
        if self.state.pounce.is_pouncing:
            self.keys_pressed[arcade.key.SPACE] = False
        else:
            self.change_y += self.speeds.JUMP

    def pounce(self):
        """Doc."""

        self.state.pounce.is_pouncing = True
        if self.move_state == "LEFT":
            self.change_x = -self.speeds.POUNCE
        elif self.move_state == "RIGHT":
            self.change_x = self.speeds.POUNCE
        self.change_y = 6

    def apply_friction(self):

        if self.move_state == "STOP" and not self.state.is_in_air:
            self.change_x *= game.FRICTION
            if abs(self.change_x) < 1:
                self.change_x = 0
