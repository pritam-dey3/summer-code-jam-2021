"""Examples for designing levels."""
import logging
import time
from random import randrange
from threading import Thread
from typing import Union

import blessed
from blessed.keyboard import Keystroke

from core.maze import AIR, Box, Maze
from core.player import Player
from core.render import Render
from core.sound import enter_game_sound, play_level_up_sound, stop_bgm
from game import NEXT_SCENE, PAUSE, PLAY, QUIT, RESET, Scene
from utils import Boundary, Vec  # type: ignore

term = blessed.Terminal()
render = Render()


class TitleScene(Scene):
    """Example of a title scene."""

    def __init__(self) -> None:
        super().__init__()
        txt1 = "welcome to 'Game name' :)"
        txt2 = "hit space to start"
        self.current_frame = term.black_on_peachpuff2 + term.clear
        self.current_frame += term.move_xy(
            x=(self.width - len(txt1)) // 2, y=self.height // 2
        )
        self.current_frame += txt1
        self.current_frame += term.move_xy(
            x=(self.width - len(txt1)) // 2, y=self.height // 2 + 1
        )
        self.current_frame += txt2
        self.first_frame = True

    def next_frame(self, val: Keystroke) -> Union[None, int]:
        """Returns next frame to render"""
        # no need to update the frame anymore
        if self.first_frame:
            self.first_frame = False
            render(self.current_frame)
            # return self.current_frame
        elif str(val) == " " or val.name == "KEY_ENTER":
            enter_game_sound()
            return NEXT_SCENE
        return None
        # return ""

    def reset(self) -> None:
        """Reset has no use for title scene."""
        pass


class Level(Scene):
    """First basic game"""

    def __init__(self, level: str = "1") -> None:
        super().__init__()
        self.maze = Maze.load(level)
        self.level_boundary = Boundary(
            len(self.maze.char_matrix[0]),
            len(self.maze.char_matrix),
            self.maze.top_left_corner,
            term,
        )

        self.end_loc = self.maze.mat2screen(self.maze.end)
        self.first_frame = True
        self.maze_is_visible = False
        self.reward_on_goal = 0

        self.player: Player = Player()
        self.t1 = Thread(target=self.remove_maze, daemon=True)

    def build_level(self) -> None:
        """Load current level specific attributes"""
        self.player.start_loc = self.maze.mat2screen(mat=self.maze.start)
        self.player.collision_count = 0
        self.reward_on_goal = 200

        for box in self.maze.boxes:
            # move to top-left corner of maze + scale and extend width
            # + move to top-left corner of box
            box.loc = self.maze.top_left_corner + box.loc * (2, 1) - (1, 1)
        self.player.inside_box[box.col] = False

    def next_frame(self, val: Keystroke) -> Union[str, int]:
        """Draw next frame."""
        if self.first_frame:
            self.first_frame = False
            self.build_level()
            play_level_up_sound()
            # removes the main maze after 2 sec
            self.t1.start()
            frame = self.get_boundary_frame()
            frame += self.maze.map
            render(frame)
            for box in self.maze.boxes:
                box.render(self.player)

            self.player.start()

        elif val.is_sequence and (257 < val.code < 262):
            # update player
            self.player.update(val, self.maze)
            # check if game ends
            if all(self.player.avi.coords == self.end_loc):
                self.player.score.value += self.reward_on_goal
                return NEXT_SCENE
            if not self.t1.is_alive() or self.player_in_boxes(self.player):
                # render boxes and mazes
                render(self.level_boundary.map)
                for box in self.maze.boxes:
                    box.render(self.player)
                # render player
                render(term.move_xy(*self.end_loc) + "&")
            self.player.render()
        elif val.lower() == "e":
            self.player.player_movement_sound(maze=self.maze)
        elif val.lower() == "q":
            return PAUSE
        elif val.lower() == "r":
            return RESET
        elif val.lower() == "h":
            if not self.maze_is_visible:
                self.maze_is_visible = True
                render(self.maze.map)
                for box in self.maze.boxes:
                    box.render(self.player)
                self.player.render()
            else:
                self.maze_is_visible = False
                self.remove_maze(0)
                return ""

        # things that should update on every frame goes here
        self.player.score.update(player_inside_box=any(self.player.inside_box.values()))
        return ""

    def remove_maze(self, sleep: float = 2) -> None:
        """Erase main maze"""
        time.sleep(sleep)
        render(self.get_boundary_frame())
        self.player.render()
        for box in self.maze.boxes:
            box.render(self.player)

    def get_boundary_frame(self) -> str:
        """Get the frame with only boundary"""
        frame = term.clear
        frame += self.level_boundary.map
        frame += term.move_xy(*self.end_loc) + "&"  # type: ignore
        return frame

    def player_in_boxes(self, player: Player) -> bool:
        """Return True if player in any boxes"""
        k = None
        for box in self.maze.boxes:
            k = box.player_in_box(player)
            if k:
                return True

    def reset(self) -> None:
        """Reset this level"""
        for box in self.maze.boxes:
            box.needs_cleaning = False
        self.player.start()
        self.first_frame = True
        self.instance.t1 = Thread(target=self.remove_maze, daemon=True)


class InfiniteLevel(Scene):
    """Infinite level of maze"""

    instance = None
    random = None

    def __init__(self, random_pos: bool) -> None:
        global random
        super().__init__()
        if type(self).instance is None:
            self.maze = Maze.generate(term.width // 5, term.height // 3, random_pos=random_pos)
            random = random_pos
            # self.maze = Maze.generate(10, 3, random_pos=random_pos)
            self.generate_boxes()
            self.level_boundary = Boundary(
                len(self.maze.char_matrix[0]),
                len(self.maze.char_matrix),
                self.maze.top_left_corner,
                term,
            )
            self.player = Player()

            self.end_loc = self.maze.mat2screen(self.maze.end)
            self.first_frame = True
            self.maze_is_visible = False
            for box in self.maze.boxes:
                # move to top-left corner of maze + scale and extend width
                # + move to top-left corner of box
                box.loc = self.maze.top_left_corner + box.loc * (2, 1) - (1, 1)
            self.t1 = Thread(target=self.remove_maze, daemon=True)
            type(self).instance = self
        else:
            logging.error(RuntimeError("Only one instance of 'Infinitelevel' can exist at a time"))

    def build_level(self) -> None:
        """Load current level specific attributes"""
        self.player.start_loc = self.maze.mat2screen(mat=self.maze.start)
        self.player.collision_count = 0
        self.reward_on_goal = 200

        for box in self.maze.boxes:
            # move to top-left corner of maze + scale and extend width
            # + move to top-left corner of box
            box.loc = self.maze.top_left_corner + box.loc * (2, 1) - (1, 1)
        self.player.inside_box[box.col] = False

    def next_frame(self, val: Keystroke) -> Union[str, int]:
        """Draw next frame."""
        if self.instance.first_frame:
            self.instance.first_frame = False
            self.build_level()
            play_level_up_sound()
            # removes the main maze after 2 sec
            self.instance.t1.start()
            frame = self.get_boundary_frame()
            frame += self.instance.maze.map
            render(frame)
            for box in self.instance.maze.boxes:
                box.render(self.instance.player)

            self.instance.player.start()

        elif val.is_sequence and (257 < val.code < 262):
            # update player
            self.instance.player.update(val, self.instance.maze)
            # check if game ends
            if all(self.instance.player.avi.coords == self.instance.end_loc):
                self.instance.reset_cls()
                self.instance.next_frame(Keystroke())
                render(self.instance.maze.map)
            if not self.instance.t1.is_alive() or self.player_in_boxes(self.instance.player):
                # render boxes and mazes
                render(self.instance.level_boundary.map)
                for box in self.instance.maze.boxes:
                    box.render(self.instance.player)
                # render player
                render(term.move_xy(*self.instance.end_loc) + "&")
            self.instance.player.render()
        elif val.lower() == "e":
            self.player.player_movement_sound(maze=self.maze)
        elif val.lower() == "q":
            return PAUSE
        elif val.lower() == "r":
            return RESET
        elif val.lower() == "h":
            if not self.instance.maze_is_visible:
                self.instance.maze_is_visible = True
                render(self.instance.maze.map)
                for box in self.instance.maze.boxes:
                    box.render(self.instance.player)
                self.instance.player.render()
            else:
                self.instance.maze_is_visible = False
                self.instance.remove_maze(0)
                return ""

        # things that should update on every frame goes here
        self.player.score.update(player_inside_box=any(self.player.inside_box.values()))
        return ""

    def remove_maze(self, sleep: float = 2) -> None:
        """Erase main maze"""
        time.sleep(sleep)
        render(self.get_boundary_frame())
        self.instance.player.render()
        for box in self.instance.maze.boxes:
            box.render(self.instance.player)

    def get_boundary_frame(self) -> str:
        """Get the frame with only boundary"""
        frame = term.clear
        frame += self.instance.level_boundary.map
        frame += term.move_xy(*self.instance.end_loc) + "&"  # type: ignore
        return frame

    def player_in_boxes(self, player: Player) -> bool:
        """Return True if player in any boxes"""
        k = None
        for box in self.instance.maze.boxes:
            k = box.player_in_box(player)
            if k:
                return True

    def generate_boxes(self) -> None:
        """Generate boxes"""
        num_box_x = self.maze.width // 10
        num_box_y = self.maze.height // 4
        if num_box_y == 0:
            num_box_y = 1
        if num_box_x == 0:
            num_box_x = 1
        radius = max(self.maze.width // num_box_x, self.maze.height // num_box_y) + 5
        number_of_box = num_box_x * num_box_y
        box_list = []
        logging.debug("radius {}".format(radius))
        logging.debug("width:" + str(self.maze.width))
        logging.debug("height:" + str(self.maze.height))
        logging.debug("number of box:" + str(number_of_box))
        logging.debug("\n" + str(self.maze))
        for y in range(0, num_box_y):
            for x in range(0, num_box_x):
                box_pos = None
                while box_pos is None or box_pos.x < 2 or box_pos.y < 2 or box_pos.x > len(
                        self.maze.matrix[1]) - 2 or box_pos.y > len(self.maze.matrix) - 2 or \
                        self.maze.matrix[box_pos.y][box_pos.x] != AIR or all(box_pos == self.maze.start) or all(
                        box_pos == self.maze.end):
                    box_pos = Vec(
                        self.maze.width * 2 // num_box_x // 2 + (self.maze.width * 2 // num_box_x) * x + randrange(-2,
                                                                                                                   2),
                        (self.maze.height // num_box_y // 2) + (self.maze.height * 2 // num_box_y) * y + randrange(-2,
                                                                                                                   2))
                logging.debug("Box pos: {}".format(str(box_pos)))
                box = Box(box_pos)
                box.generate_map(self.maze, radius)
                box.generate_image()
                box_list.append(box)
        self.maze.boxes = box_list

    def reset(self) -> None:
        """Reset this level"""
        for box in self.instance.maze.boxes:
            box.needs_cleaning = False
        self.instance.player.start()
        self.instance.first_frame = True
        self.instance.t1 = Thread(target=self.remove_maze, daemon=True)

    @classmethod
    def reset_cls(cls):
        """Reset class"""
        global random
        cls.instance = None
        cls.instance = InfiniteLevel(random)


class EndScene(Scene):
    """Example of ending scene."""

    def __init__(self):
        super().__init__()
        txt = "You won :o"
        self.current_frame = term.move_xy(
            x=(self.width - len(txt)) // 2, y=self.height // 2
        )
        self.current_frame += txt
        self.first_frame = True

    def next_frame(self, val: Keystroke) -> Union[None, int]:
        """Return next frame to render"""
        # no need to update each frame
        if self.first_frame:
            stop_bgm()
            self.first_frame = False
            render(self.current_frame)
            # return self.render(self.current_frame)
        elif str(val) == " " or val.name == "KEY_ENTER":
            return NEXT_SCENE
        return None

    def reset(self) -> None:
        """No use."""
        pass


class Pause(Scene):
    """Pause Screen for the game"""

    def __init__(self):
        super().__init__()
        self.first_frame = True
        self.reset()

    def next_frame(self, val: Keystroke) -> Union[None, int]:
        """Return next frame to render"""
        # no need to update each frame
        if self.first_frame:
            self.first_frame = False
            render(self.current_frame)
        elif val.lower() == "q":
            return QUIT
        elif val.lower() == "p":
            # remove everything from screen
            self.current_frame = term.move_xy(
                x=(self.width - len(self.txt)) // 2, y=self.height // 2
            )
            self.current_frame += " " * len(self.txt)
            self.current_frame += term.move_xy(
                x=(self.width - len(self.txt2)) // 2, y=self.height // 2 + 1
            )
            self.current_frame += " " * len(self.txt2)
            self.current_frame += term.move_xy(
                x=(self.width - len(self.txt3)) // 2, y=self.height
            )
            self.current_frame += " " * len(self.txt3)
            render(self.current_frame)
            return PLAY
        # elif val.lower() == "h":
        #     # help
        # elif val.lower() == "c":
        #     # credits

        return None

    def reset(self) -> None:
        """Reset current scene"""
        self.txt = "This is the pause screen and we need to design it"
        self.txt2 = "Hit p to play"
        self.txt3 = "Hit q again to exit"
        self.current_frame = term.move_xy(
            x=(self.width - len(self.txt)) // 2, y=self.height // 2
        )
        self.current_frame += self.txt
        self.current_frame += term.move_xy(
            x=(self.width - len(self.txt2)) // 2, y=self.height // 2 + 1
        )
        self.current_frame += self.txt2
        self.current_frame += term.move_xy(
            x=(self.width - len(self.txt3)) // 2, y=self.height
        )
        self.current_frame += self.txt3
        self.first_frame = True
