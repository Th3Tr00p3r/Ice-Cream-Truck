"""
Ice Cream Truck Game
"""

import os
import sys
import time
from contextlib import suppress
from itertools import cycle
from pathlib import Path
from random import choice, random, uniform
from types import SimpleNamespace
from typing import Dict, Union

import arcade
import game_constants as game
import PIL
from helper import (
    Vector,
    crop_resize_concat_horizontally,
    load_high_scores,
    save_high_scores,
)
from sprites import (
    BlueCat,
    CompetitorCat,
    DigitTextures,
    IceCreamTruck,
    PlayerCat,
    Popsicle,
    RedCat,
    YellowCat,
)

# Assets path
ASSETS_PATH = Path("./assets").resolve()

# TODO: no need for custom TextureAtlas (as far as I understand now)
# NOTE: IT APPEARS THAT THE AURA TEXTURES ARE MOST DANGEROUS IN THIS RESPECT!
# AS THEY CREATE A NEW TEXTURE FOR EVERY PLAYER MOVE!
# what I need to do is as I did with the popsicles (and before that, ignorant of the texture atlas, with the cats)
# I need to ensure each texture is loaded only once.
# the problem now is with the HUD - I shouldn't create a new texture for each (infinite) combination of score digits, score multiplier,
# or life (hearts).
# for the life it should be simple enough to generate all options (only 6 I believe)
# for the score multiplier and the score itself I would need to change the implementation a bit:
# instead of ordering the numbers and creating a new image, I would use the existing images and just order them as I do now, but on screen.

# TODO: Red: superpower is time-stop: many pops are thrown then everything slows down but the player, for a time
# TODO: Yellow: Grows bigger with every popsicle. tramples smaller cats by pouncing. superpower is popsicle magnet for a time

# TODO: add available cat thumbnails to HUD (use big cat images on sprite speadsheet
# TODO: add sounds for: getting killed, competitor grabs popsicle, begging etc.
# TODO: build the cats' house and the ice cream truck using free Kenney parts and PIL
# TODO: add license and credits where needed (as well as my own name!)


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

    SLOW_TIME_FACTOR = 0.3

    def __init__(self) -> None:
        super().__init__()

        # These lists will hold different sets of sprites
        self.popsicles: arcade.SpriteList[Popsicle] = None
        self.ice_cream_truck: IceCreamTruck = None

        # One sprite for the player, no more is needed
        self.player: PlayerCat = None
        self.MAX_PLAYER_LIVES = 5
        self.key_color_dict = {
            arcade.key.B: "deepskyblue",
            arcade.key.R: "crimson",
            arcade.key.Y: "gold",
        }

        # We need a physics engine as well
        self.physics_engine: arcade.PhysicsEnginePlatformer = None

        # Someplace to keep score
        self.score: int
        self.last_drawn_score: int = None
        self.last_drawn_score_multiplier: int = None
        self.score_multiplier: int

        # lives
        self.empty_heart_image = PIL.Image.open(
            ASSETS_PATH / "images" / "HUD" / "hudHeart_empty.png"
        )
        self.full_heart_image = PIL.Image.open(ASSETS_PATH / "images" / "HUD" / "hudHeart_full.png")
        self.last_drawn_lives: int = None

        # Load up our sounds here
        self.coin_sound = arcade.load_sound(str(ASSETS_PATH / "sounds" / "coin.wav"))
        self.victory_sound = arcade.load_sound(str(ASSETS_PATH / "sounds" / "victory.wav"))
        self.kill_sound_list = [
            arcade.load_sound(str(ASSETS_PATH / "sounds" / f"kill{i}.wav")) for i in (1, 2, 3)
        ]
        self.kill_sounds_cycler = cycle(self.kill_sound_list)

        # Which level are we on?
        self.level = 1

        # Track the bottom left corner of the current viewport
        self.view_left = 0
        self.view_bottom = 0

        # Flag for entering view mode - allows super-user to skim around
        self.view_mode = False

    def setup(self) -> None:
        """Sets up the game for the current level"""

        # get current highscores
        self.high_scores_list = load_high_scores()

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

        # get the ground y-coordinate for height calculations (e.g. YellowCat 'drop' ability)
        ground_sprite = self.map_sprite_lists["ground"][0]
        self.ground_height = ground_sprite.center_y + ground_sprite.height / 2

        # Find the edge of the map to control viewport scrolling
        self.map_width = map.width * map.tile_width * game.MAP_SCALING

        # Create the Ice Cream Man and Truck
        self.ice_cream_truck = IceCreamTruck(
            game.TRUCK_START_POS, scale=game.ICE_CREAM_TRUCK_SCALING
        )

        # track pressed movement keys
        self.keys_pressed = {
            arcade.key.LEFT: False,
            arcade.key.RIGHT: False,
            arcade.key.DOWN: False,
            arcade.key.SPACE: False,
            arcade.key.LCTRL: False,
            "LAST": None,
        }

        # Create the player sprite
        self.player_color_cat_dict = {
            cat_class.color_str: cat_class(
                game.PLAYER_START_POS,
                keys_pressed=self.keys_pressed,
                ground_height=self.ground_height,
            )
            for cat_class in (BlueCat, RedCat, YellowCat)
        }
        self.player_cat_cycler = cycle(self.player_color_cat_dict.values())
        # always start with blue cat
        self.player = next(self.player_cat_cycler)  # type: ignore
        # NOTE: mypy complains about type of value in player_cats dict - although they should be a sbuclass of PlayerCat, it treats them as of type SpriteMixin for some reason...

        # cat competitors
        self.n_allowed_cats = 1
        self.new_cat_prob_frame = 0.001

        # Setup the popsicle sprite list
        self.popsicles = arcade.SpriteList()

        # Initiate the competitor cats sprite list
        self.cats = arcade.SpriteList()
        self.n_cats = 0
        self.poofs = arcade.SpriteList()

        # Reset the viewport
        self.view_left = 0
        self.view_bottom = 0

        # Load the physics engine for this map
        self.setup_physics_engine()

        self.player.jump()  # to fix freeze bug on game start

        # reset score
        self.score_textures = DigitTextures()
        self.score = 0
        self.score_multiplier = 1

        # timers
        self.game_timer = 0.0
        self.game_over_timer = 0.0
        self.score_multiplier_timer = 0.0
        self.player_switch_timer = 0.0
        self.slow_time_timer = 0.0

    def on_key_press(self, key, modifiers):
        """Called whenever a key is pressed."""

        # Switch player cat
        if key == arcade.key.Z:
            self.switch_player_cat(is_previous_dead=False)

        # Check for player left/right movement
        if key in (arcade.key.LEFT, arcade.key.RIGHT):
            self.keys_pressed[key] = True
            self.keys_pressed["LAST"] = key
            self.player.update_state()

        # Check for pounce (or drop for YellowCat)
        if key == arcade.key.DOWN:
            self.keys_pressed[key] = True
            self.player.update_state()
            if self.player.state.pounce.can_pounce:
                # exaust all jumps
                for i in range(game.N_JUMPS):
                    self.physics_engine.increment_jump_counter()
                self.player.pounce()

            else:  # YellowCat only
                with suppress(AttributeError):
                    self.player.drop()

        # Check if we can jump (or air-dash for RedCat)
        elif key == arcade.key.SPACE:
            self.keys_pressed[key] = True
            self.player.jump()

        # Check if we can activate superpower
        elif key == arcade.key.LCTRL:
            self.keys_pressed[key] = True
            self.player.update_state()
            if self.player.state.superpower.is_ready:
                self.player.activate_superpower()

        # Did the user want to pause?
        elif key in {arcade.key.ESCAPE, arcade.key.P}:
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

    def on_update(self, delta_time: float) -> None:  # NOQA # C901
        """Updates the position of all screen objects

        Arguments:
            delta_time -- How much time since the last call
        """

        # TESTESTEST - TextureAtlas investigation
        n_textures = len(self.window.ctx.default_atlas._textures)
        print(f"Number of textures in TextureAtlas: {n_textures}")
        # /TESTESTEST

        if self.slow_time_timer > 0:
            self.slow_time_timer -= delta_time
            delta_time *= self.SLOW_TIME_FACTOR

        # check if player is out of lives, and begin death animation
        if not self.player.lives and self.game_over_timer == 0.0:
            self.player.die()
            self.player_color_cat_dict.pop(self.player.color_str)
            self.player_cat_cycler = cycle(self.player_color_cat_dict.values())
            self.poofs.append(self.player.poof())
            # choose random cat remaining in player_cats
            self.switch_player_cat()

        # when death animation ends, game is over
        if self.game_over_timer > 0:
            self.game_over_timer -= delta_time
        elif not self.player.is_alive:
            _, current_scores_list = zip(*self.high_scores_list)
            if self.score > min(current_scores_list):
                self.window.show_view(NewHighScoreView(self))
            else:
                self.window.show_view(GameOverView(self))

        # timers
        self.game_timer += delta_time
        if self.game_timer >= 60:
            self.game_timer = 0.0
            self.new_cat_prob_frame *= 1.25
            if self.n_allowed_cats < 7:
                self.n_allowed_cats += 1

        if self.score_multiplier_timer > 0.0:
            self.score_multiplier_timer -= delta_time
        elif self.score_multiplier > 1:
            self.score_multiplier -= 1
            self.score_multiplier_timer = 5

        if self.player_switch_timer > 0.0:
            self.player_switch_timer -= delta_time

        # Update Popsicles
        with suppress(AttributeError):
            # AttributeError - no popsicles present
            self.popsicles.update_animation(delta_time)
            for popsicle in self.popsicles:
                popsicle.move(delta_time)
                # Check if popsicle flew off-screen or hit ground
                if popsicle.type == "regular":
                    popsicle.restrict_position(self.map_width, should_kill=True)
                    ground_hit = arcade.check_for_collision_with_list(
                        sprite=popsicle, sprite_list=self.map_sprite_lists["ground"]
                    )
                    if ground_hit:
                        popsicle.bounce()
                        # melt popsicle
                        popsicle.melt(delta_time)
                else:  # heart
                    popsicle.restrict_position(self.map_width, should_kill=True)

        # Update player movement based on the physics engine
        self.physics_engine.update()
        self.player.update_state()
        self.player.update_velocity(delta_time)
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
            if new_popsicle.type == "heart":
                self.slow_time_timer = 2.0
            with suppress(IndexError):
                self.popsicles.append(new_popsicle)

        # Create new competitor cat
        if self.n_cats < self.n_allowed_cats and random() < self.new_cat_prob_frame:
            self.cats.append(
                CompetitorCat(
                    init_position=Vector(
                        choice([0, game.SCREEN_PROPS.width]),
                        uniform(0, game.SCREEN_PROPS.height / 2),
                    ),
                    init_speed=Vector(0, uniform(0, 50)),
                    speeds=SimpleNamespace(
                        RUN=uniform(75, 125), SLIDE=5 / 3, JUMP=20 / 3, POUNCE=35 / 3
                    ),  # pixels per frame
                    acceleration_magnitude=100 * 60,
                    color_str=choice(list(game.COLORS - game.PLAYER_COLORS)),
                    game_view=self,
                    scale=game.CHARACTER_SCALING * uniform(1, 1.5),
                )
            )
            self.n_cats += 1

        # Update the player animation
        self.player.update_animation(delta_time)

        # Update the animations for our map objects as well
        self.map_sprite_lists["background"].update_animation(delta_time)

        with suppress(TypeError):
            # Check if we've picked up a popsicle
            popsicles_collected = arcade.check_for_collision_with_list(
                sprite=self.player, sprite_list=self.popsicles
            )

            for popsicle in popsicles_collected:
                if popsicle.type == "heart":
                    if self.player.lives < self.player.MAX_LIVES:
                        self.player.lives += 1
                    else:
                        self.score += popsicle.point_value * self.score_multiplier
                else:  # regular
                    # Add the coin score to our score
                    self.score += (
                        popsicle.point_value * 5
                        if popsicle.color_str == self.player.color_str
                        else popsicle.point_value
                    ) * self.score_multiplier
                    # check for favorites towards superpower
                    if popsicle.color_str == self.player.color_str and not (
                        self.player.state.superpower.is_ready or self.player.state.superpower.is_on
                    ):
                        self.player.n_favorite_pops_collected += 1
                # Play the coin sound
                arcade.play_sound(self.coin_sound, volume=0.2)
                # mark as off-screen (for other cats)
                popsicle.is_off_screen = True
                # Remove the popsicle
                with suppress(ValueError):
                    # arcade - array.remove(x): x not in array
                    popsicle.kill()

        # Check for competitor collisions
        cats_collided_with_player = arcade.check_for_collision_with_list(
            sprite=self.player, sprite_list=self.cats
        )
        self.ice_cream_truck.reset_throw_probabilities()
        for cat in self.cats:
            # popsicle collections
            popsicles_collided_with_cat = arcade.check_for_collision_with_list(
                sprite=cat, sprite_list=self.popsicles
            )
            for popsicle in popsicles_collided_with_cat:
                if popsicle.color_str == cat.color_str:
                    cat.sought_popsicle = None
                    popsicle.remove_from_sprite_lists()

            if cat in cats_collided_with_player or self.player.state.drop.is_dropping:
                if self.player.can_kill_cat(cat):
                    with suppress(ValueError):
                        self.poofs.append(cat.poof())
                        arcade.play_sound(next(self.kill_sounds_cycler))
                    cat.kill()
                    self.n_cats -= 1
                    self.score_multiplier += 1
                    self.score_multiplier_timer = 5.0
                elif not self.player.state.drop.is_dropping:
                    self.player.get_hit(cat)

            if cat.mode == "begging":
                self.ice_cream_truck.color_pop_probs_dict[cat.color_str] *= 2

        # update poofs
        self.poofs.update_animation(delta_time)

        # update truck
        self.ice_cream_truck.update_animation(delta_time)

        # superpower
        if self.player.state.superpower.is_on:
            self.ice_cream_truck.throw_probability_frame *= 3
            self.ice_cream_truck.color_pop_probs_dict[self.player.color_str] *= 1000
        self.player.update_superpower_timer(delta_time)

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
            if self.view_bottom < 0:
                self.view_bottom = 0

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
        self.poofs.draw()
        self.player.draw()

        # Draw the score in the upper left
        if self.score != self.last_drawn_score:
            self.score_sprites = self.get_score_spritelist(self.score)
            self.last_drawn_score = self.score
        self.score_sprites.draw()

        # Draw lives HUD in the upper right
        if self.player.lives != self.last_drawn_lives:
            new_lives_image = self.get_lives_hud(self.MAX_PLAYER_LIVES, self.player.lives)
            unique_str = str(new_lives_image) + str(self.game_timer) + str(time.perf_counter())
            self.lives_texture = arcade.Texture(unique_str, new_lives_image)
            self.last_drawn_lives = self.player.lives

        with suppress(IndexError):
            arcade.draw_texture_rectangle(
                self.view_left + game.SCREEN_PROPS.width - 150,
                self.view_bottom + game.SCREEN_PROPS.height - 50,
                200,
                50,
                self.lives_texture,
            )

        # Draw the score multiplier below the lives HUD
        if self.score_multiplier != self.last_drawn_score_multiplier:
            new_score_multiplier_image = self.get_score_multiplier_image(self.score_multiplier)
            unique_str = (
                str(new_score_multiplier_image) + str(self.game_timer) + str(time.perf_counter())
            )
            self.new_score_multiplier_texture = arcade.Texture(
                unique_str, new_score_multiplier_image
            )
            self.last_drawn_score_multiplier = self.score_multiplier

        arcade.draw_texture_rectangle(
            self.view_left + game.SCREEN_PROPS.width - 105,
            self.view_bottom + game.SCREEN_PROPS.height - 120,
            112.5,
            56.25,
            self.new_score_multiplier_texture,
        )

    def get_score_spritelist(self, score: int):
        """
        Accepts an integer 'score' and returns a SpriteList composed of textures
        of digits of the number supplied, with positions provided to propery display the
        number 'score' upon .draw()
        """

        start_x = self.view_left + 50
        start_y = self.view_bottom + game.SCREEN_PROPS.height - 100
        current_x = start_x

        score_spritelist = arcade.SpriteList()
        for idx, digit_char in enumerate(str(score)):
            digit_texture = self.score_textures.digits[int(digit_char)]
            size_x, size_y = digit_texture.image.size
            digit_sprite = arcade.Sprite(
                texture=digit_texture,
                center_x=current_x + size_x // 3,
                center_y=start_y + size_y // 3,
            )
            score_spritelist.append(digit_sprite)
            current_x += size_x // 3

        return score_spritelist

    def get_score_multiplier_image(self, multiplier: int):
        """Doc."""

        img_list = [self.digit_dict["x"]] + [
            self.digit_dict[int(digit_char)] for digit_char in str(multiplier)
        ]
        return crop_resize_concat_horizontally(img_list)

    def get_lives_hud(self, n_max_lives: int, n_lives_left: int):
        """Doc."""

        n_lives_lost = n_max_lives - n_lives_left
        return crop_resize_concat_horizontally(
            [self.full_heart_image] * n_lives_left + [self.empty_heart_image] * n_lives_lost
        )

    def switch_player_cat(self, is_previous_dead=True):
        """Doc."""

        if self.player_switch_timer <= 0 or is_previous_dead:
            self.player_switch_timer = 0.3
            if len(self.player_color_cat_dict) > 0:
                previous_player = self.player
                next_player = next(self.player_cat_cycler)
                if not previous_player == next_player:
                    self.player = next_player
                    self.player.state = previous_player.state
                    self.player.position = previous_player.position
                    self.player.center_y += (
                        self.player.height
                    )  # to deal with physics engine ground collision
                    self.player.change_x = previous_player.change_x
                    self.player.change_y = previous_player.change_y
                    self.player.angle = previous_player.angle
                    previous_player.position = (0, 0)  # move to safety
                    self.setup_physics_engine(self.physics_engine.jumps_since_ground)
                    if not previous_player.is_alive:
                        self.player.hit_timer = self.player.INVULNERABILITY_DURATION_s
            else:
                # TODO: play game over sound
                self.game_over_timer = 3.0

    def setup_physics_engine(self, jumps_since_ground=0):
        """Doc."""

        self.physics_engine = arcade.PhysicsEnginePlatformer(
            player_sprite=self.player,
            platforms=self.map_sprite_lists["ground"],
            gravity_constant=game.GRAVITY,
        )

        self.player.physics_engine = self.physics_engine

        # multi-jumps
        self.physics_engine.enable_multi_jump(game.N_JUMPS)

        # initiate jumps_since_ground
        self.physics_engine.jumps_since_ground = jumps_since_ground


class TitleView(arcade.View):
    """Displays a title screen and prompts the user to begin the game.
    Provides a way to show instructions and start the game.
    """

    def __init__(self) -> None:
        super().__init__()

        # flags
        self.is_screen_drawn = False
        self.is_game_ready = False

        # Find the title image in the images folder
        title_image_path = ASSETS_PATH / "images" / "title_image.png"

        # Load our title image
        self.title_image = arcade.load_texture(title_image_path)

        # Set our display timer
        self.display_timer = 2.0

        # Are we showing the instructions?
        self.show_instructions = False

        # define texts
        text_kwargs = dict(
            start_x=0,
            font_name="Kenney Pixel Square",
            multiline=True,
            width=game.SCREEN_PROPS.width,
            align="center",
        )

        self.title_text = arcade.Text(
            "Ice-Cream Truck",
            start_y=game.SCREEN_PROPS.height - 150,
            color=arcade.color.MAGENTA,
            font_size=game.DEFAULT_FONT_SIZE + 15,
            **text_kwargs,
        )

        self.title_shade = arcade.Text(
            " Ice-Cream Truck",
            start_y=game.SCREEN_PROPS.height - 156,
            color=arcade.color.WHITE,
            font_size=game.DEFAULT_FONT_SIZE + 15,
            **text_kwargs,
        )

        # define blinking text
        self.blinking_text = arcade.Text(
            "'Enter' to Start\n'H' for High Scores\n'I' for Instructions\n'Esc' to quit",
            start_y=game.SCREEN_PROPS.height // 2 - 200,
            color=arcade.color.MAGENTA,
            font_size=game.DEFAULT_FONT_SIZE - 15,
            **text_kwargs,
        )

        self.blinking_shade = arcade.Text(
            " 'Enter' to Start\n 'H' for High Scores\n 'I' for Instructions\n 'Esc' to quit",
            start_y=game.SCREEN_PROPS.height // 2 - 206,
            color=arcade.color.WHITE,
            font_size=game.DEFAULT_FONT_SIZE - 15,
            **text_kwargs,
        )

        self.loading_text = arcade.Text(
            "Loading...",
            start_y=game.SCREEN_PROPS.height // 2 - 250,
            color=arcade.color.MAGENTA,
            font_size=game.DEFAULT_FONT_SIZE,
            **text_kwargs,
        )

        self.loading_shade = arcade.Text(
            " Loading...",
            start_y=game.SCREEN_PROPS.height // 2 - 256,
            color=arcade.color.WHITE,
            font_size=game.DEFAULT_FONT_SIZE,
            **text_kwargs,
        )

        self.game_view = PlatformerView()

    def on_update(self, delta_time: float) -> None:
        """Manages the timer to toggle the instructions

        Arguments:
            delta_time -- time passed since last update
        """

        # setup the game before starting (but after title screen is drawn)
        if not self.is_game_ready and self.is_screen_drawn:
            self.game_view.setup()
            self.high_scores_list = load_high_scores()
            self.is_game_ready = True

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

        # draw title text
        self.title_shade.draw()
        self.title_text.draw()

        # show 'laoding' while setting up the game
        if not self.is_game_ready:
            self.loading_shade.draw()
            self.loading_text.draw()

        # Should we show our instructions?
        if self.show_instructions:
            self.blinking_shade.draw()
            self.blinking_text.draw()

        self.is_screen_drawn = True

    def on_key_press(self, key: int, modifiers: int) -> None:
        """Resume the game when the user presses ESC again

        Arguments:
            key -- Which key was pressed
            modifiers -- What modifiers were active
        """

        if not modifiers & arcade.key.MOD_ALT and key == arcade.key.RETURN:
            self.window.show_view(self.game_view)

        elif key == arcade.key.I:
            self.window.show_view(InstructionsView(self))

        elif key == arcade.key.H:
            self.window.show_view(HighScoresView(self))

        elif key == arcade.key.ESCAPE:
            self.window.close()


class InstructionsView(arcade.View):
    """Show instructions to the player"""

    def __init__(self, title_view) -> None:
        """Create instructions screen"""
        super().__init__()

        self.title_view = title_view

        # Load background image
        self.background_image = arcade.load_texture(ASSETS_PATH / "images" / "background_image.png")

        self.text_list = [
            arcade.Text(
                "Instructions / Keys",
                start_x=0,
                start_y=game.SCREEN_PROPS.height - 150,
                color=arcade.color.BLACK,
                font_size=game.DEFAULT_FONT_SIZE + 5,
                font_name="Kenney Pixel Square",
                width=game.SCREEN_PROPS.width,
                align="center",
            ),
            arcade.Text(
                "Move - LEFT/RIGHT\nJump - SPACE\nPounce - DOWN (running at full speed)\nSwitch Cat: Z\nSuper Power - lCtrl\n\nCollect as many popsicles as you can!",
                start_x=100,
                start_y=game.SCREEN_PROPS.height - 300,
                color=arcade.color.BLACK,
                font_size=game.DEFAULT_FONT_SIZE - 10,
                font_name="Kenney Pixel Square",
                width=game.SCREEN_PROPS.width,
                align="left",
                multiline=True,
            ),
        ]

    def on_draw(self) -> None:

        # Draw a rectangle filled with the instructions image
        arcade.draw_texture_rectangle(
            **game.SCREEN_PROPS.as_dict(),
            texture=self.background_image,
        )

        # cover the image in semitransparent white
        arcade.draw_lrtb_rectangle_filled(
            left=0,
            right=game.SCREEN_PROPS.width,
            top=game.SCREEN_PROPS.height,
            bottom=0,
            color=arcade.make_transparent_color(arcade.color.WHITE, transparency=200),
        )

        # draw text
        for text in self.text_list:
            text.draw()

    def on_key_press(self, key: int, modifiers: int) -> None:

        if key in game.ANY_KEY:
            self.window.show_view(self.title_view)


class HighScoresView(arcade.View):
    def __init__(self, title_view) -> None:
        """Create high-scores screen"""
        super().__init__()

        self.title_view = title_view
        self.high_scores_list = load_high_scores()

        # Load our title image
        self.background_image = arcade.load_texture(ASSETS_PATH / "images" / "background_image.png")

        # Store a semi-transparent color to use as an overlay
        self.fill_color = arcade.make_transparent_color(arcade.color.WHITE, transparency=150)

        # define texts
        name_score_str_list = [
            f"{name} - {score}"
            for idx, (name, score) in enumerate(self.title_view.high_scores_list)
        ]
        text_kwargs = dict(
            start_x=0,
            font_name="Kenney Pixel Square",
            multiline=True,
            width=game.SCREEN_PROPS.width,
            align="center",
        )
        self.text_list = [
            arcade.Text(
                "Ice-Cream Truck",
                start_y=game.SCREEN_PROPS.height - 150,
                color=arcade.color.MAGENTA,
                font_size=game.DEFAULT_FONT_SIZE + 15,
                **text_kwargs,
            ),
            arcade.Text(
                " Ice-Cream Truck",
                start_y=game.SCREEN_PROPS.height - 156,
                color=arcade.color.WHITE,
                font_size=game.DEFAULT_FONT_SIZE + 15,
                **text_kwargs,
            ),
            arcade.Text(
                "High Scores:\n" + "\n".join(name_score_str_list),
                start_y=game.SCREEN_PROPS.height - 300,
                color=arcade.color.BLACK,
                font_size=game.DEFAULT_FONT_SIZE,
                **text_kwargs,
            ),
            arcade.Text(
                " High Scores:\n" + "\n".join([f" {str_}" for str_ in name_score_str_list]),
                start_y=game.SCREEN_PROPS.height - 306,
                color=arcade.color.MAGENTA,
                font_size=game.DEFAULT_FONT_SIZE,
                **text_kwargs,
            ),
            arcade.Text(
                "Press any key",
                start_y=game.SCREEN_PROPS.height - 700,
                color=arcade.color.MAGENTA,
                font_size=game.DEFAULT_FONT_SIZE - 15,
                **text_kwargs,
            ),
            arcade.Text(
                " Press any key",
                start_y=game.SCREEN_PROPS.height - 706,
                color=arcade.color.WHITE,
                font_size=game.DEFAULT_FONT_SIZE - 15,
                **text_kwargs,
            ),
        ]

    def on_draw(self) -> None:
        """Draw the underlying screen, blurred, then the game over text"""

        # Draw a rectangle filled with the instructions image
        arcade.draw_texture_rectangle(
            **game.SCREEN_PROPS.as_dict(),
            texture=self.background_image,
        )

        # Now create a filled rect that covers the current viewport
        # We get the viewport size from the game view
        arcade.draw_lrtb_rectangle_filled(
            left=0,
            right=game.SCREEN_PROPS.width,
            top=game.SCREEN_PROPS.height,
            bottom=0,
            color=self.fill_color,
        )

        # Now show the game over text
        for text in self.text_list:
            text.draw()

    def on_key_press(self, key: int, modifiers: int) -> None:
        """Restart the current level when the user presses Enter

        Arguments:
            key -- Which key was pressed
            modifiers -- What modifiers were active
        """

        if key in game.ANY_KEY:
            self.window.show_view(self.title_view)


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

        # define pause text
        text_kwargs = dict(
            start_x=0,
            font_name="Kenney Pixel Square",
            multiline=True,
            width=game.SCREEN_PROPS.width,
            align="center",
        )

        self.pause_text = arcade.Text(
            "PAUSED\nPRESS 'P' OR 'Esc' TO CONTINUE",
            start_y=game.SCREEN_PROPS.height // 2,
            color=arcade.color.MAGENTA,
            font_size=game.DEFAULT_FONT_SIZE,
            **text_kwargs,
        )

        self.pause_shade = arcade.Text(
            " PAUSED\n PRESS 'P' OR 'Esc' TO CONTINUE",
            start_y=game.SCREEN_PROPS.height // 2 - 6,
            color=arcade.color.WHITE,
            font_size=game.DEFAULT_FONT_SIZE,
            **text_kwargs,
        )

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

        self.pause_shade.draw()
        self.pause_text.draw()

    def on_key_press(self, key: int, modifiers: int) -> None:
        """Resume the game when the user presses ESC again

        Arguments:
            key -- Which key was pressed
            modifiers -- What modifiers were active
        """
        if key in {arcade.key.ESCAPE, arcade.key.P}:
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

        # define texts
        name_score_str_list = [
            f"{name} - {score}" for idx, (name, score) in enumerate(self.game_view.high_scores_list)
        ]
        text_kwargs = dict(
            start_x=0,
            font_name="Kenney Pixel Square",
            multiline=True,
            width=game.SCREEN_PROPS.width,
            align="center",
        )
        self.text_list = [
            arcade.Text(
                "Game Over!",
                start_y=game.SCREEN_PROPS.height - 150,
                color=arcade.color.MAGENTA,
                font_size=game.DEFAULT_FONT_SIZE + 15,
                **text_kwargs,
            ),
            arcade.Text(
                " Game Over!",
                start_y=game.SCREEN_PROPS.height - 156,
                color=arcade.color.WHITE,
                font_size=game.DEFAULT_FONT_SIZE + 15,
                **text_kwargs,
            ),
            arcade.Text(
                "High Scores:\n" + "\n".join(name_score_str_list),
                start_y=game.SCREEN_PROPS.height - 300,
                color=arcade.color.BLACK,
                font_size=game.DEFAULT_FONT_SIZE,
                **text_kwargs,
            ),
            arcade.Text(
                " High Scores:\n" + "\n".join([f" {str_}" for str_ in name_score_str_list]),
                start_y=game.SCREEN_PROPS.height - 306,
                color=arcade.color.MAGENTA,
                font_size=game.DEFAULT_FONT_SIZE,
                **text_kwargs,
            ),
            arcade.Text(
                "'Enter' to restart\n'Esc' to exit",
                start_y=game.SCREEN_PROPS.height - 700,
                color=arcade.color.MAGENTA,
                font_size=game.DEFAULT_FONT_SIZE - 15,
                **text_kwargs,
            ),
            arcade.Text(
                " 'Enter' to restart\n 'Esc' to exit",
                start_y=game.SCREEN_PROPS.height - 706,
                color=arcade.color.WHITE,
                font_size=game.DEFAULT_FONT_SIZE - 15,
                **text_kwargs,
            ),
        ]

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
        for text in self.text_list:
            text.draw()

    def on_key_press(self, key: int, modifiers: int) -> None:
        """Restart the current level when the user presses Enter

        Arguments:
            key -- Which key was pressed
            modifiers -- What modifiers were active
        """

        if key == arcade.key.RETURN:
            # Reset the current level
            self.game_view.setup()
            self.window.show_view(self.game_view)

        elif key == arcade.key.ESCAPE:
            self.window.close()


class NewHighScoreView(arcade.View):
    """Shown when the player sets a new highscore"""

    def __init__(self, game_view: arcade.View) -> None:
        """Create the game over screen"""
        # Initialize the parent
        super().__init__()

        # Store a reference to the underlying view
        self.game_view = game_view

        # Store a semi-transparent color to use as an overlay
        self.fill_color = arcade.make_transparent_color(arcade.color.WHITE, transparency=150)

        # keep the current score list and the new score
        self.new_score = game_view.score
        self.new_name = ""

        # define texts
        self.text_kwargs = dict(
            start_x=0,
            font_name="Kenney Pixel Square",
            multiline=True,
            width=game.SCREEN_PROPS.width,
            align="center",
        )
        self.text_list = [
            arcade.Text(
                "New High Score Set!",
                start_y=game.SCREEN_PROPS.height - 150,
                color=arcade.color.MAGENTA,
                font_size=game.DEFAULT_FONT_SIZE + 15,
                **self.text_kwargs,
            ),
            arcade.Text(
                " New High Score Set!",
                start_y=game.SCREEN_PROPS.height - 156,
                color=arcade.color.WHITE,
                font_size=game.DEFAULT_FONT_SIZE + 15,
                **self.text_kwargs,
            ),
            arcade.Text(
                "Please Type in your name (up to 5 characters):",
                start_y=game.SCREEN_PROPS.height - 250,
                color=arcade.color.MAGENTA,
                font_size=game.DEFAULT_FONT_SIZE - 10,
                **self.text_kwargs,
            ),
            arcade.Text(
                " Please Type in your name (up to 5 characters):",
                start_y=game.SCREEN_PROPS.height - 256,
                color=arcade.color.WHITE,
                font_size=game.DEFAULT_FONT_SIZE - 10,
                **self.text_kwargs,
            ),
            0,
            0,
        ]

        self.update_name()

    def on_key_press(self, key: int, modifiers: int) -> None:
        """Restart the current level when the user presses Enter

        Arguments:
            key -- Which key was pressed
            modifiers -- What modifiers were active
        """

        if key == arcade.key.RETURN:
            self.update_high_scores()
            self.window.show_view(GameOverView(self.game_view))

        elif key == arcade.key.ESCAPE:
            self.new_name = ""
            self.update_high_scores()
            self.window.show_view(GameOverView(self.game_view))

        elif key in range(97, 122 + 1):  # key is in A-Z
            if len(self.new_name) < 5:
                self.new_name += game.KEY_STR_DICT[key]
                self.update_name()

        elif key == arcade.key.BACKSPACE:
            self.new_name = self.new_name[:-1]
            self.update_name()

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
        for text in self.text_list:
            text.draw()

    def update_name(self):
        """Doc."""

        name_text = arcade.Text(
            self.new_name,
            start_y=game.SCREEN_PROPS.height - 400,
            color=arcade.color.BLACK,
            font_size=game.DEFAULT_FONT_SIZE,
            **self.text_kwargs,
        )
        name_shade = arcade.Text(
            f" {self.new_name}",
            start_y=game.SCREEN_PROPS.height - 406,
            color=arcade.color.MAGENTA,
            font_size=game.DEFAULT_FONT_SIZE,
            **self.text_kwargs,
        )

        self.text_list = self.text_list[:-2] + [name_text, name_shade]

    def update_high_scores(self):
        """Doc."""

        current_names, current_scores = zip(*self.game_view.high_scores_list)

        scores = list(current_scores) + [self.new_score]
        names = list(current_names) + [self.new_name]

        new_high_score_list = [
            (name, score) for score, name in sorted(zip(scores, names), reverse=True)[:3]
        ]

        # save to file and update current game highscore (avoid re-loading file)
        save_high_scores(new_high_score_list)
        self.game_view.high_scores_list = new_high_score_list


if __name__ == "__main__":

    # for PyInstaller
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        os.chdir(sys._MEIPASS)  # type: ignore

    GameWindow()
    arcade.run()
