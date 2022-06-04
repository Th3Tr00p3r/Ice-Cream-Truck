"""
Ice Cream Truck Game
"""


from contextlib import suppress
from pathlib import Path
from random import choice, random, uniform
from types import SimpleNamespace

import arcade
import game_constants as game
import PIL
from helper import crop_resize_concat_horizontally
from sprites import CompetitorCat, IceCreamTruck, Player, Popsicle

# Assets path
ASSETS_PATH = Path(__file__).resolve().parent.parent / "assets"


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
        self.popsicles: arcade.SpriteList[Popsicle] = None
        self.ice_cream_truck: IceCreamTruck = None

        # One sprite for the player, no more is needed
        self.player: Player = None

        # Enemies
        self.n_allowed_cats = 1
        self.new_cat_prob_frame = 0.001

        # We need a physics engine as well
        self.physics_engine: arcade.PhysicsEnginePlatformer = None

        # Someplace to keep score
        self.score = 0
        self.last_drawn_score: int = None
        self.digit_dict = {
            idx: PIL.Image.open(img_path)
            for idx, img_path in enumerate((ASSETS_PATH / "images" / "HUD" / "score").glob("*.png"))
        }

        # lives
        self.empty_heart_image = PIL.Image.open(
            ASSETS_PATH / "images" / "HUD" / "hudHeart_empty.png"
        )
        self.full_heart_image = PIL.Image.open(ASSETS_PATH / "images" / "HUD" / "hudHeart_full.png")
        self.last_drawn_lives: int = None

        # Load up our sounds here
        self.coin_sound = arcade.load_sound(str(ASSETS_PATH / "sounds" / "coin.wav"))
        self.jump_sound = arcade.load_sound(str(ASSETS_PATH / "sounds" / "jump.wav"))
        self.victory_sound = arcade.load_sound(str(ASSETS_PATH / "sounds" / "victory.wav"))

        # Which level are we on?
        self.level = 1

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
            game.TRUCK_START_POS, 0.03, scale=game.ICE_CREAM_TRUCK_SCALING
        )

        # Create the player sprite
        self.player = Player(
            game.PLAYER_START_POS,
            game.PLAYER_MOVE_SPEED,
            game.PLAYER_ACCELERATION_MAGNITUDE,
            "lime",
            map_width=self.map_width,
            keys_pressed=self.keys_pressed,
            scale=game.CHARACTER_SCALING,
        )

        # Setup the popsicle sprite list
        self.popsicles = arcade.SpriteList()

        # Initiate the competitor cats sprite list
        self.cats = arcade.SpriteList()
        self.n_cats = 0

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

        # reset score
        self.score = 0

        # timer
        self.game_timer = 0.0

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

        # timer
        self.game_timer += delta_time
        if (
            self.game_timer >= 60
            and self.game_timer % 60 <= delta_time * 2
            and self.n_allowed_cats < 5
        ):
            self.n_allowed_cats += 1

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

        # Update competitor cats
        with suppress(AttributeError):
            # AttributeError - no popsicles present
            self.cats.update_animation(delta_time)
            for cat in self.cats:
                cat.seek(delta_time)
                # Prevent cat from going off-screen
                cat.restrict_position(self.map_width)
                # Check if popsicle hit ground
                ground_hit = arcade.check_for_collision_with_list(
                    sprite=cat, sprite_list=self.map_sprite_lists["ground"]
                )
                if ground_hit:
                    cat.state.is_in_air = False

        # Throw Popsicle
        if (new_popsicle := self.ice_cream_truck.throw_popsicle()) is not None:
            self.popsicles.append(new_popsicle)

        # Create new competitor cat
        if self.n_cats < self.n_allowed_cats and random() < self.new_cat_prob_frame:
            self.cats.append(
                CompetitorCat(
                    init_position=game.PLAYER_START_POS,  # TESTESTEST
                    speeds=SimpleNamespace(
                        RUN=10 / 3, SLIDE=5 / 3, JUMP=20 / 3, POUNCE=35 / 3
                    ),  # pixels per frame
                    acceleration_magnitude=50 / 3,
                    color_str=choice(list(game.COLORS - {self.player.color_str})),
                    game_view=self,
                    scale=game.CHARACTER_SCALING * uniform(1, 1.5),
                )
            )
            self.n_cats += 1

        # Update the player animation
        self.player.update_animation(delta_time, self.physics_engine.jumps_since_ground)

        # Update the animations for our map objects as well
        self.map_sprite_lists["background"].update_animation(delta_time)

        with suppress(TypeError):
            # Check if we've picked up a popsicle
            popsicles_collected = arcade.check_for_collision_with_list(
                sprite=self.player, sprite_list=self.popsicles
            )

            for popsicle in popsicles_collected:
                # Add the coin score to our score
                self.score += popsicle.point_value
                # Play the coin sound
                arcade.play_sound(self.coin_sound)
                # Remove the popsicle
                popsicle.remove_from_sprite_lists()

        # Check for competitor collections
        for cat in self.cats:
            popsicles_hit = arcade.check_for_collision_with_list(
                sprite=cat, sprite_list=self.popsicles
            )
            for popsicle in popsicles_hit:
                if popsicle.color_str == cat.color_str:
                    popsicle.remove_from_sprite_lists()

        # Check for player collisions with other cats
        cats_hit = arcade.check_for_collision_with_list(sprite=self.player, sprite_list=self.cats)
        for cat in cats_hit:
            if self.player.change_y <= -self.player.speeds.JUMP / 2:
                cat.kill()
                self.n_cats -= 1
            else:
                self.player.get_hit()
                if not self.player.lives:
                    self.window.show_view(GameOverView(self))

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

        #        # Scroll up
        #        top_boundary = self.view_bottom + game.SCREEN_PROPS.height - game.TOP_VIEWPORT_MARGIN
        #        if self.player.top > top_boundary:
        #            self.view_bottom += self.player.top - top_boundary

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
        self.cats.draw()
        self.player.draw()

        # Draw the score in the upper left
        if self.score != self.last_drawn_score:
            new_score_image = self.get_score_image(self.score)
            self.score_image = arcade.Texture(str(self.score), new_score_image)
            self.last_drawn_score = self.score

        arcade.draw_texture_rectangle(
            100 + self.view_left,
            self.view_bottom + game.SCREEN_PROPS.height - 50,
            150,
            75,
            self.score_image,
        )

        # Draw lives HUD in the upper right
        if self.player.lives != self.last_drawn_lives:
            new_lives_image = self.get_lives_hud(self.player.MAX_LIVES, self.player.lives)
            self.lives_image = arcade.Texture(str(new_lives_image), new_lives_image)
            self.last_drawn_lives = self.player.lives

        arcade.draw_texture_rectangle(
            self.view_left + game.SCREEN_PROPS.width - 100,
            self.view_bottom + game.SCREEN_PROPS.height - 50,
            150,
            50,
            self.lives_image,
        )

    def get_score_image(self, score: int):
        """
        Accepts an integer 'n' and a path to a directory containing only
        relevent digit images (sorted - e.g. ending in the corresponding digit)
        and returns an image of the number, made of the digit images supplied.
        """

        img_list = [self.digit_dict[int(digit_char)] for digit_char in str(score)]
        return crop_resize_concat_horizontally(img_list)

    def get_lives_hud(self, n_max_lives: int, n_lives_left: int):
        """Doc."""

        n_lives_lost = n_max_lives - n_lives_left
        return crop_resize_concat_horizontally(
            [self.full_heart_image] * n_lives_left + [self.empty_heart_image] * n_lives_lost
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
