"""
Ice Cream Truck Game
"""

import math
from collections import namedtuple
from contextlib import suppress
from pathlib import Path
from random import choice, randint, random, uniform
from types import SimpleNamespace

import arcade
import game_constants as game
from helper import Vector

# Assets path
ASSETS_PATH = Path(__file__).resolve().parent.parent / "assets"


class BasicSprite(arcade.Sprite):
    def __init__(self, init_position: Vector, texture_path: Path, **kwargs):
        init_x, init_y = init_position
        super().__init__(filename=texture_path, center_x=init_x, center_y=init_y, **kwargs)

    def load_texture_pair(self, filename):
        """
        Load a texture pair, with the second being a mirror image.
        """

        TexturePair = namedtuple("TexturePair", "RIGHT LEFT")
        return TexturePair(
            RIGHT=arcade.load_texture(filename),
            LEFT=arcade.load_texture(filename, flipped_horizontally=True),
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
            standing=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catStanding.png"),
            running=[
                self.load_texture_pair(self.MAIN_TEXTURE_PATH / f"catRunning{i}.png")
                for i in (1, 2, 3, 4)
            ],
            pouncing=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catRunning4.png"),
            sliding=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catRunning1.png"),
            jumping=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catJumping.png"),
            stalling=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catStalling.png"),
            falling=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catFalling.png"),
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


class GameWindow(arcade.Window):
    """Doc."""

    def __init__(self):
        super().__init__(
            width=game.SCREEN_PROPS.width,
            height=game.SCREEN_PROPS.height,
            title=game.SCREEN_TITLE,
            fullscreen=False,
        )
        self.center_window()
        self.show_view(TitleView())

    def on_key_press(self, key, modifiers):
        """Called whenever a key is pressed."""

        if modifiers & arcade.key.MOD_ALT and key == arcade.key.ENTER:
            # User hits s. Flip between full and not full screen.
            self.set_fullscreen(not self.fullscreen)

            # Instead of a one-to-one mapping, stretch/squash window to match the
            # constants. This does NOT respect aspect ratio. You'd need to
            # do a bit of math for that.
            self.set_viewport(0, game.SCREEN_PROPS.width, 0, game.SCREEN_PROPS.height)


class PlatformerView(arcade.View):
    """Doc."""

    def __init__(self) -> None:
        super().__init__()

        # These lists will hold different sets of sprites
        self.popsicles: arcade.SpriteList = None
        self.ice_cream_truck: BasicSprite = None

        # One sprite for the player, no more is needed
        self.player: BasicSprite = None

        # We need a physics engine as well
        self.physics_engine: arcade.PhysicsEnginePlatformer = None

        # Someplace to keep score
        self.score = 0

        # Which level are we on?
        self.level = 1

        # Load up our sounds here
        self.coin_sound = arcade.load_sound(str(ASSETS_PATH / "sounds" / "coin.wav"))
        self.jump_sound = arcade.load_sound(str(ASSETS_PATH / "sounds" / "jump.wav"))
        self.victory_sound = arcade.load_sound(str(ASSETS_PATH / "sounds" / "victory.wav"))

        # track pressed movement keys
        self.keys_pressed = {
            arcade.key.LEFT: False,
            arcade.key.RIGHT: False,
            arcade.key.DOWN: False,
            arcade.key.SPACE: False,
            "LAST": None,
        }

        # Track the bottom left corner of the current viewport
        self.view_left = 0
        self.view_bottom = 0

        # Flag for entering view mode - allows super-user to skim around
        self.view_mode = False

    def setup(self) -> None:
        """Sets up the game for the current level"""

        # Get the current map based on the level
        map_name = f"Ice_cream_truck_level_{self.level:02}.json"
        map_path = ASSETS_PATH / map_name

        # Load the current map
        map = arcade.tilemap.TileMap(map_path, scaling=game.MAP_SCALING)

        # What are the names of the layers?
        layer_names = ["ground", "background", "background objects"]
        self.map_sprite_lists = {
            layer_name: map.sprite_lists[layer_name] for layer_name in layer_names
        }

        # Set the background color
        background_color = arcade.color.FRESH_AIR
        if map.background_color:
            background_color = map.background_color
        arcade.set_background_color(background_color)

        # Find the edge of the map to control viewport scrolling
        self.map_width = (map.width - 1) * map.tile_width * game.MAP_SCALING

        # Create the Ice Cream Man and Truck
        self.ice_cream_truck = IceCreamTruck(
            game.TRUCK_START_POS, 0.01, scale=game.ICE_CREAM_TRUCK_SCALING
        )

        # Create the player sprite, if they're not already setup
        self.player = Player(
            game.PLAYER_START_POS,
            game.PLAYER_MOVE_SPEED,
            game.PLAYER_ACCELERATION_MAGNITUDE,
            map_width=self.map_width,
            keys_pressed=self.keys_pressed,
            scale=game.CHARACTER_SCALING,
        )

        # Setup the popsicle sprite list
        self.popsicles = arcade.SpriteList()

        # Reset the viewport
        self.view_left = 0
        self.view_bottom = 0

        # Load the physics engine for this map
        self.physics_engine = arcade.PhysicsEnginePlatformer(
            player_sprite=self.player,
            platforms=self.map_sprite_lists["ground"],
            gravity_constant=game.GRAVITY,
        )

        # multi-jumps
        self.physics_engine.enable_multi_jump(game.N_JUMPS)

    def on_key_press(self, key, modifiers):
        """Called whenever a key is pressed."""

        # Check for player left/right movement
        if key in (arcade.key.LEFT, arcade.key.RIGHT):
            self.keys_pressed[key] = True
            self.keys_pressed["LAST"] = key
            self.player.update_state(
                self.physics_engine.can_jump(), self.physics_engine.jumps_since_ground
            )

        # Check for pounce
        if key == arcade.key.DOWN:
            self.keys_pressed[key] = True
            self.player.update_state(
                self.physics_engine.can_jump(), self.physics_engine.jumps_since_ground
            )
            if self.player.state.pounce.can_pounce:
                # exaust all jumps
                for i in range(game.N_JUMPS):
                    self.physics_engine.increment_jump_counter()
                self.player.pounce()

        # Check if we can jump
        elif key == arcade.key.SPACE:
            self.keys_pressed[key] = True
            self.player.update_state(
                self.physics_engine.can_jump(), self.physics_engine.jumps_since_ground
            )
            if self.player.state.jump.can_jump:
                self.player.jump()
                self.physics_engine.increment_jump_counter()
                # Play the jump sound
                arcade.play_sound(self.jump_sound)

        # Did the user want to pause?
        elif key == arcade.key.ESCAPE:
            # Pass the current view to preserve this view's state
            self.window.show_view(PauseView(self))

        # Shortcut to end the game
        elif key == arcade.key.Q:
            # Show the game over screen
            self.window.show_view(GameOverView(self))

    def on_key_release(self, key, modifiers):
        """Called when the user releases a key."""

        if key in self.keys_pressed.keys():
            self.keys_pressed[key] = False
            self.player.update_velocity()

    def on_update(self, delta_time: float) -> None:
        """Updates the position of all screen objects

        Arguments:
            delta_time -- How much time since the last call
        """

        # Update Popsicles
        with suppress(AttributeError):
            # AttributeError - no popsicles present
            self.popsicles.update_animation(delta_time)
            for popsicle in self.popsicles:
                popsicle.move()
                # Check if popsicles flew off-screen
                popsicle.restrict_position(self.map_width, should_kill=True)
                # Check if popsicle hit ground
                ground_hit = arcade.check_for_collision_with_list(
                    sprite=popsicle, sprite_list=self.map_sprite_lists["ground"]
                )
                if ground_hit:
                    popsicle.bounce()
                    # melt popsicle
                    popsicle.melt(delta_time)

        # Update player movement based on the physics engine
        self.physics_engine.update()
        self.player.update_state(
            self.physics_engine.can_jump(), self.physics_engine.jumps_since_ground
        )
        self.player.update_velocity()
        self.player.apply_friction()
        self.player.restrict_position(self.map_width)

        # Throw Popsicle
        if (new_popsicle := self.ice_cream_truck.throw_popsicle()) is not None:
            self.popsicles.append(new_popsicle)

        # Update the player animation
        self.player.update_animation(delta_time, self.physics_engine.jumps_since_ground)

        # Update the animations for our map objects as well
        self.map_sprite_lists["background"].update_animation(delta_time)

        with suppress(TypeError):
            # Check if we've picked up a popsicle
            popsicles_hit = arcade.check_for_collision_with_list(
                sprite=self.player, sprite_list=self.popsicles
            )

            for popsicle in popsicles_hit:
                # Add the coin score to our score
                self.score += popsicle.point_value
                # Play the coin sound
                arcade.play_sound(self.coin_sound)
                # Remove the popsicle
                popsicle.remove_from_sprite_lists()

        #        # Has Roz collided with an enemy?
        #        enemies_hit = arcade.check_for_collision_with_list(
        #            sprite=self.player, sprite_list=self.enemies
        #        )
        #
        #        if enemies_hit:
        #            game_over = GameOverView(self)
        #            self.window.show_view(game_over)

        # Set the viewport, scrolling if necessary
        self.scroll_viewport()

    def scroll_viewport(self) -> None:
        """Scrolls the viewport when the player gets close to the edges"""
        # Scroll left
        # Find the current left boundary
        left_boundary = self.view_left + game.LEFT_VIEWPORT_MARGIN

        # Are we to the left of this boundary? Then we should scroll left
        if self.player.left < left_boundary:
            self.view_left -= left_boundary - self.player.left
            # But don't scroll past the left edge of the map
            if self.view_left < 0:
                self.view_left = 0

        # Scroll right
        # Find the current right boundary
        right_boundary = self.view_left + game.SCREEN_PROPS.width - game.RIGHT_VIEWPORT_MARGIN

        # Are we right of this boundary? Then we should scroll right
        if self.player.right > right_boundary:
            self.view_left += self.player.right - right_boundary
            # Don't scroll past the right edge of the map
            if self.view_left > self.map_width - game.SCREEN_PROPS.width:
                self.view_left = self.map_width - game.SCREEN_PROPS.width

        # Scroll up
        top_boundary = self.view_bottom + game.SCREEN_PROPS.height - game.TOP_VIEWPORT_MARGIN
        if self.player.top > top_boundary:
            self.view_bottom += self.player.top - top_boundary

        # Scroll down
        bottom_boundary = self.view_bottom + game.BOTTOM_VIEWPORT_MARGIN
        if self.player.bottom < bottom_boundary:
            self.view_bottom -= bottom_boundary - self.player.bottom

        # Only scroll to integers. Otherwise we end up with pixels that
        # don't line up on the screen
        self.view_bottom = int(self.view_bottom)
        self.view_left = int(self.view_left)

        # Do the scrolling
        arcade.set_viewport(
            left=self.view_left,
            right=game.SCREEN_PROPS.width + self.view_left,
            bottom=self.view_bottom,
            top=game.SCREEN_PROPS.height + self.view_bottom,
        )

    def on_draw(self) -> None:
        arcade.start_render()

        # Draw all the sprites
        self.map_sprite_lists["background"].draw()
        self.map_sprite_lists["background objects"].draw()
        self.map_sprite_lists["ground"].draw()
        #        self.enemies.draw()

        self.ice_cream_truck.draw()
        self.popsicles.draw()
        self.player.draw()

        # Draw the score in the lower left
        score_text = f"Score: {self.score}"

        # First a black background for a shadow effect
        arcade.draw_text(
            score_text,
            start_x=10 + self.view_left,
            start_y=10 + self.view_bottom,
            color=arcade.csscolor.BLACK,
            font_size=40,
        )
        # Now in white slightly shifted
        arcade.draw_text(
            score_text,
            start_x=15 + self.view_left,
            start_y=15 + self.view_bottom,
            color=arcade.csscolor.WHITE,
            font_size=40,
        )


class TitleView(arcade.View):
    """Displays a title screen and prompts the user to begin the game.
    Provides a way to show instructions and start the game.
    """

    def __init__(self) -> None:
        super().__init__()

        # Find the title image in the images folder
        title_image_path = ASSETS_PATH / "images" / "title_image.png"

        # Load our title image
        self.title_image = arcade.load_texture(title_image_path)

        # Set our display timer
        self.display_timer = 3.0

        # Are we showing the instructions?
        self.show_instructions = False

    def on_update(self, delta_time: float) -> None:
        """Manages the timer to toggle the instructions

        Arguments:
            delta_time -- time passed since last update
        """

        # First, count down the time
        self.display_timer -= delta_time

        # If the timer has run out, we toggle the instructions
        if self.display_timer < 0:

            # Toggle whether to show the instructions
            self.show_instructions = not self.show_instructions

            # And reset the timer so the instructions flash slowly
            self.display_timer = 1.0

    def on_draw(self) -> None:
        # Start the rendering loop
        arcade.start_render()

        # Draw a rectangle filled with our title image
        arcade.draw_texture_rectangle(
            **game.SCREEN_PROPS.as_dict(),
            texture=self.title_image,
        )

        # Should we show our instructions?
        if self.show_instructions:
            arcade.draw_text(
                "Enter to Start | I for Instructions",
                start_x=100,
                start_y=220,
                color=arcade.color.INDIGO,
                font_size=40,
            )

    def on_key_press(self, key: int, modifiers: int) -> None:
        """Resume the game when the user presses ESC again

        Arguments:
            key -- Which key was pressed
            modifiers -- What modifiers were active
        """
        if not modifiers & arcade.key.MOD_ALT and key == arcade.key.RETURN:
            game_view = PlatformerView()
            game_view.setup()
            self.window.show_view(game_view)
        elif key == arcade.key.I:
            instructions_view = InstructionsView()
            self.window.show_view(instructions_view)


class InstructionsView(arcade.View):
    """Show instructions to the player"""

    def __init__(self) -> None:
        """Create instructions screen"""
        super().__init__()

        # Find the instructions image in the image folder
        instructions_image_path = ASSETS_PATH / "images" / "instructions_image.png"

        # Load our title image
        self.instructions_image = arcade.load_texture(instructions_image_path)

    def on_draw(self) -> None:
        # Start the rendering loop
        arcade.start_render()

        # Draw a rectangle filled with the instructions image
        arcade.draw_texture_rectangle(
            **game.SCREEN_PROPS.as_dict(),
            texture=self.instructions_image,
        )

    def on_key_press(self, key: int, modifiers: int) -> None:
        """Start the game when the user presses Enter

        Arguments:
            key -- Which key was pressed
            modifiers -- What modifiers were active
        """
        if key == arcade.key.RETURN:
            game_view = PlatformerView()
            game_view.setup()
            self.window.show_view(game_view)

        elif key == arcade.key.ESCAPE:
            title_view = TitleView()
            self.window.show_view(title_view)


class PauseView(arcade.View):
    """Shown when the game is paused"""

    def __init__(self, game_view: arcade.View) -> None:
        """Create the pause screen"""
        # Initialize the parent
        super().__init__()

        # Store a reference to the underlying view
        self.game_view = game_view

        # Store a semi-transparent color to use as an overlay
        self.fill_color = arcade.make_transparent_color(arcade.color.WHITE, transparency=150)

    def on_draw(self) -> None:
        """Draw the underlying screen, blurred, then the Paused text"""

        # First, draw the underlying view
        # This also calls start_render(), so no need to do it again
        self.game_view.on_draw()

        # Now create a filled rect that covers the current viewport
        # We get the viewport size from the game view
        arcade.draw_lrtb_rectangle_filled(
            left=self.game_view.view_left,
            right=self.game_view.view_left + game.SCREEN_PROPS.width,
            top=self.game_view.view_bottom + game.SCREEN_PROPS.height,
            bottom=self.game_view.view_bottom,
            color=self.fill_color,
        )

        # Now show the Pause text
        arcade.draw_text(
            "PAUSED - ESC TO CONTINUE",
            start_x=self.game_view.view_left + 180,
            start_y=self.game_view.view_bottom + 300,
            color=arcade.color.INDIGO,
            font_size=40,
        )

    def on_key_press(self, key: int, modifiers: int) -> None:
        """Resume the game when the user presses ESC again

        Arguments:
            key -- Which key was pressed
            modifiers -- What modifiers were active
        """
        if key == arcade.key.ESCAPE:
            self.window.show_view(self.game_view)


class VictoryView(arcade.View):
    """Shown when a level is completed"""

    def __init__(self, game_view: arcade.View, victory_sound: arcade.Sound) -> None:
        super().__init__()

        # Store a reference to the underlying view
        self.game_view = game_view

        # Play the victory sound
        arcade.play_sound(victory_sound)

        # Store a semi-transparent color to use as an overlay
        self.fill_color = arcade.make_transparent_color(arcade.color.WHITE, transparency=150)

    def on_draw(self) -> None:
        """Draw the underlying screen, blurred, then the victory text"""

        # First, draw the underlying view
        # This also calls start_render(), so no need to do it again
        self.game_view.on_draw()

        # Now create a filled rect that covers the current viewport
        # We get the viewport size from the game view
        arcade.draw_lrtb_rectangle_filled(
            left=self.game_view.view_left,
            right=self.game_view.view_left + game.SCREEN_PROPS.width,
            top=self.game_view.view_bottom + game.SCREEN_PROPS.height,
            bottom=self.game_view.view_bottom,
            color=self.fill_color,
        )

        # Now show the victory text
        arcade.draw_text(
            "SUCCESS! Press Enter for next level...",
            start_x=self.game_view.view_left + 90,
            start_y=self.game_view.view_bottom + 300,
            color=arcade.color.INDIGO,
            font_size=40,
        )

    def on_key_press(self, key: int, modifiers: int) -> None:
        """Start the next level when the user presses Enter

        Arguments:
            key -- Which key was pressed
            modifiers -- What modifiers were active
        """
        if key == arcade.key.ENTER:
            self.game_view.level += 1
            self.game_view.setup()
            self.window.show_view(self.game_view)


class GameOverView(arcade.View):
    """Shown when the player loses the game"""

    def __init__(self, game_view: arcade.View) -> None:
        """Create the game over screen"""
        # Initialize the parent
        super().__init__()

        # Store a reference to the underlying view
        self.game_view = game_view

        # Store a semi-transparent color to use as an overlay
        self.fill_color = arcade.make_transparent_color(arcade.color.WHITE, transparency=150)

    def on_draw(self) -> None:
        """Draw the underlying screen, blurred, then the game over text"""

        # First, draw the underlying view
        # This also calls start_render(), so no need to do it again
        self.game_view.on_draw()

        # Now create a filled rect that covers the current viewport
        # We get the viewport size from the game view
        arcade.draw_lrtb_rectangle_filled(
            left=self.game_view.view_left,
            right=self.game_view.view_left + game.SCREEN_PROPS.width,
            top=self.game_view.view_bottom + game.SCREEN_PROPS.height,
            bottom=self.game_view.view_bottom,
            color=self.fill_color,
        )

        # Now show the game over text
        arcade.draw_text(
            "Game Over!",
            start_x=self.game_view.view_left + 360,
            start_y=self.game_view.view_bottom + 330,
            color=arcade.color.INDIGO,
            font_size=40,
        )
        arcade.draw_text(
            "Enter to restart, ESC to exit",
            start_x=self.game_view.view_left + 190,
            start_y=self.game_view.view_bottom + 280,
            color=arcade.color.INDIGO,
            font_size=40,
        )

    def on_key_press(self, key: int, modifiers: int) -> None:
        """Restart the current level when the user presses Enter

        Arguments:
            key -- Which key was pressed
            modifiers -- What modifiers were active
        """
        if key == arcade.key.ENTER:
            # Reset the current level
            self.game_view.setup()
            self.window.show_view(self.game_view)

        elif key == arcade.key.ESCAPE:
            self.window.close()


if __name__ == "__main__":
    GameWindow()
    arcade.run()
