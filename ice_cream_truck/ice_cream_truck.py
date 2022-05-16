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

    def apply_friction(self, keys_pressed):

        is_stopping = not keys_pressed[arcade.key.RIGHT] and not keys_pressed[arcade.key.LEFT]
        if is_stopping:
            self.change_x *= game.FRICTION
            if abs(self.change_x) < 1:
                self.change_x = 0


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
    MELT_RATE = 0.999  # units?
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
        self.face_direction = game.FACE_DIRECTION.RIGHT

        # Used for flipping between image sequences
        self.cur_texture = 0

        # Load textures
        self.textures_types = SimpleNamespace(
            standing=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "truckIceCream1.png"),
        )

        # Set the initial texture
        self.texture = self.textures_types.standing.RIGHT

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

    def __init__(
        self,
        init_position: Vector,
        speeds: SimpleNamespace,
        acceleration_magnitude: float,
        map_width,
        **kwargs,
    ):

        super().__init__(init_position, self.MAIN_TEXTURE_PATH / "catStanding.png", **kwargs)

        # keep map width
        self.map_width = map_width

        # Default to face-right
        self.face_direction = game.FACE_DIRECTION.RIGHT

        # Used for flipping between image sequences
        self.cur_texture = 0

        # Load textures
        self.textures_types = SimpleNamespace(
            standing=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catStanding.png"),
            running=[
                self.load_texture_pair(self.MAIN_TEXTURE_PATH / f"catRunning{i}.png")
                for i in (1, 2, 3, 4)
            ],
            pounceing=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catRunning4.png"),
            sliding=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catRunning1.png"),
            jumping=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catJumping.png"),
            stalling=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catStalling.png"),
            falling=self.load_texture_pair(self.MAIN_TEXTURE_PATH / "catFalling.png"),
        )

        # Set the initial texture
        self.texture = self.textures_types.standing.RIGHT

        self.speeds = speeds
        self.acceleration_magnitude = acceleration_magnitude
        self.acceleration = 0.0
        self.spin_speed = 30

        self.is_pouncing = False
        self.is_pouncing_left = False
        self.is_pouncing_right = False
        self.pounce_start = None

        # for setting running animation frequency
        self.time_accumulator = 0.0

    def update_animation(self, delta_time: float, jumps_since_ground: int):

        self.time_accumulator += delta_time

        # stop spinning
        self.change_angle = 0

        # Figure out if we need to flip face left or right
        if self.acceleration < 0:
            self.face_direction = game.FACE_DIRECTION.LEFT
        elif self.acceleration > 0:
            self.face_direction = game.FACE_DIRECTION.RIGHT

        # Jumping/Stalling/Falling animation
        if jumps_since_ground >= 1 or self.change_y < 0 and not self.is_pouncing:
            if 5 < self.change_y:
                self.texture = self.textures_types.jumping[self.face_direction]
            elif -5 < self.change_y < 5:
                self.texture = self.textures_types.stalling[self.face_direction]
            elif self.change_y < -5:
                self.texture = self.textures_types.falling[self.face_direction]

            if jumps_since_ground >= 2:
                if self.change_y > -5:
                    if self.face_direction == game.FACE_DIRECTION.RIGHT:
                        self.change_angle = -self.spin_speed
                    else:
                        self.change_angle = self.spin_speed
                else:
                    self.angle = 0

        # pounce animation
        elif self.is_pouncing:
            self.texture = self.textures_types.pounceing[self.face_direction]

        # Running animation
        elif abs(self.change_x) > self.speeds.RUN * 0.2:
            self.angle = 0
            if self.time_accumulator >= self.RUNNING_ANIMATION_FACTOR / (
                abs(self.change_x) / self.speeds.RUN
            ) / len(self.textures_types.running):
                self.cur_texture += 1
                self.time_accumulator = 0
            if self.cur_texture == len(self.textures_types.running):
                self.cur_texture = 0
            self.texture = self.textures_types.running[self.cur_texture][self.face_direction]

        # Sliding animation
        elif 0 < abs(self.change_x) <= self.speeds.RUN * 0.2:
            self.texture = self.textures_types.sliding[self.face_direction]

        # Idle animation
        else:
            self.angle = 0
            self.texture = self.textures_types.standing[self.face_direction]

    def update_velocity(self, keys_pressed, last_pressed_key, is_on_ground: bool):
        """Doc."""

        is_only_left_pressed = keys_pressed[arcade.key.LEFT] and not keys_pressed[arcade.key.RIGHT]
        is_only_right_pressed = keys_pressed[arcade.key.RIGHT] and not keys_pressed[arcade.key.LEFT]
        are_both_pressed = keys_pressed[arcade.key.RIGHT] and keys_pressed[arcade.key.LEFT]
        is_changing_to_left = are_both_pressed and last_pressed_key == arcade.key.LEFT
        is_changing_to_right = are_both_pressed and last_pressed_key == arcade.key.RIGHT
        is_moving_left = is_only_left_pressed or is_changing_to_left
        is_moving_right = is_only_right_pressed or is_changing_to_right

        is_prepared_to_pounce = (
            keys_pressed[arcade.key.DOWN] and is_on_ground and abs(self.change_x) == self.speeds.RUN
        )
        is_pouncing_left = is_prepared_to_pounce and is_only_left_pressed
        is_pouncing_right = is_prepared_to_pounce and is_only_right_pressed
        is_pouncing = is_pouncing_left or is_pouncing_right

        if is_pouncing and not self.is_pouncing:
            self.is_pouncing = True
            keys_pressed[arcade.key.DOWN] = False
            self.pounce_start = self.center_x
            self.is_pouncing_left = is_pouncing_left
            self.is_pouncing_right = is_pouncing_right
            self.change_y = 10.0

        is_close_to_edges = (
            abs(self.center_x - self.map_width) < self.width / 2 or self.center_x < self.width / 2
        )
        should_keep_pouncing = (
            self.pounce_start is not None
            and abs(self.center_x - self.pounce_start) < self.width * 3.5
            and not is_close_to_edges
        )
        if should_keep_pouncing:
            if self.is_pouncing_left:
                self.change_x = -self.speeds.POUNCE
            elif self.is_pouncing_right:
                self.change_x = self.speeds.POUNCE
        elif self.is_pouncing:
            self.is_pouncing = False
            self.change_x = 0
            self.pounce_start = None

        elif not self.is_pouncing:
            if is_moving_left:
                self.acceleration = -self.acceleration_magnitude
            elif is_moving_right:
                self.acceleration = self.acceleration_magnitude
            else:
                self.acceleration = 0

            self.change_x += self.acceleration
            if self.change_x > self.speeds.RUN:
                self.change_x = self.speeds.RUN
            elif self.change_x < -self.speeds.RUN:
                self.change_x = -self.speeds.RUN

    def update_jump_velocity(self, keys_pressed) -> bool:
        """Doc."""

        has_jumped = False

        if self.is_pouncing:
            keys_pressed[arcade.key.SPACE] = False
        elif keys_pressed[arcade.key.SPACE]:
            self.change_y = self.speeds.JUMP
            keys_pressed[arcade.key.SPACE] = False
            has_jumped = True
        elif self.change_y > 0:
            self.change_y *= 0.5

        return has_jumped


class GameWindow(arcade.Window):
    """Doc."""

    def __init__(self):
        super().__init__(
            width=game.SCREEN_PROPS.width,
            height=game.SCREEN_PROPS.height,
            title=game.SCREEN_TITLE,
            fullscreen=True,
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


class PlatformerView(arcade.View):
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
        }

        # Track the bottom left corner of the current viewport
        self.view_left = 0
        self.view_bottom = 0

        # Flag for entering view mode - allows super-user to skim around
        self.view_mode = False

        self.last_pressed_key = None

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
            self.map_width,
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
        self.physics_engine.enable_multi_jump(2)

    def on_key_press(self, key, modifiers):
        """Called whenever a key is pressed."""

        # Check for player left/right movement
        if key in (arcade.key.LEFT, arcade.key.RIGHT):
            self.keys_pressed[key] = True
            self.last_pressed_key = key

        # Check for pounce
        if key == arcade.key.DOWN:
            self.keys_pressed[key] = True

        # Check if we can jump
        elif key == arcade.key.SPACE:
            if self.physics_engine.can_jump():
                self.keys_pressed[key] = True
                has_jumped = self.player.update_jump_velocity(self.keys_pressed)
                if has_jumped:
                    self.physics_engine.increment_jump_counter()
                    self.is_on_ground = False
                    # Play the jump sound
                    arcade.play_sound(self.jump_sound)

        # Did the user want to pause?
        elif key == arcade.key.ESCAPE:
            # Pass the current view to preserve this view's state
            pause = PauseView(self)
            self.window.show_view(pause)

        # Shortcut to end the game
        elif key == arcade.key.Q:
            # Show the game over screen
            gameover = GameOverView(self)
            self.window.show_view(gameover)

    def on_key_release(self, key, modifiers):
        """Called when the user releases a key."""

        if key in self.keys_pressed.keys():
            self.keys_pressed[key] = False
            self.player.update_velocity(self.keys_pressed, self.last_pressed_key, self.is_on_ground)
            self.player.update_jump_velocity(self.keys_pressed)

    def on_update(self, delta_time: float) -> None:
        """Updates the position of all screen objects

        Arguments:
            delta_time -- How much time since the last call
        """

        # Update the animations for our map objects as well
        self.map_sprite_lists["background"].update_animation(delta_time)

        # Are there popsicles? Update them as well
        with suppress(AttributeError):
            # AttributeError - no popsicles present
            self.popsicles.update_animation(delta_time)
            for popsicle in self.popsicles:
                popsicle.move()
                # Check if popsicles flew off-screen
                if not 0 < popsicle.center_x < self.map_width:
                    popsicle.kill()
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
        self.physics_engine.can_jump()
        self.is_on_ground = self.physics_engine.jumps_since_ground == 0
        self.player.update_velocity(self.keys_pressed, self.last_pressed_key, self.is_on_ground)
        #        self.last_pressed_key = None
        self.player.apply_friction(self.keys_pressed)

        # Throw Popsicle
        if (new_popsicle := self.ice_cream_truck.throw_popsicle()) is not None:
            self.popsicles.append(new_popsicle)

        # Update the player animation
        self.player.update_animation(delta_time, self.physics_engine.jumps_since_ground)

        # Restrict user movement so they can't walk off screen
        if self.player.left < 0:
            self.player.left = 0
        if self.player.right >= self.map_width:
            self.player.right = self.map_width
        if self.player.bottom < 0:
            self.player.bottom = 0

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


if __name__ == "__main__":
    GameWindow()
    arcade.run()
