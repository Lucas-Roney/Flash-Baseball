"""
FLASH BASEBALL  -  batting + baserunning game (pygame, fullscreen)

Run it:      pip install pygame
             python flash_baseball.py

START SCREEN
  Type a team name, click a home color, pick EASY / MEDIUM / HARD, pick a game length (1/3/5/9 innings),
  then click PLAY BALL (or press ENTER).
  Keyboard shortcuts: LEFT/RIGHT = color, UP/DOWN = difficulty, TAB = innings.
  Want a different title font?  Drop any .ttf file next to this script and name it  title_font.ttf

DIFFICULTY  (you can change it any time from the pause menu)
  EASY ..... slower pitches, bigger timing windows, and you CAN hit the splitter if you swing in the green
  MEDIUM ... the original game
  HARD ..... faster pitches, smaller timing windows, plus the CHANGEUP and the SLIDER (always a ball)

HOW A PLAY WORKS
  1. BATTING VIEW (behind the batter): time your swing with the meter, and read the
     SEAMS window in the corner to see which pitch is coming (rolling up = fastball,
     rolling down = curveball, barely spinning = splitter, slower rolling up = changeup, tilted = slider).
  2. PITCH LOCATION: pitches come INSIDE, MIDDLE or OUTSIDE. The ball drifts left/right and the green part of the
     meter shifts: inside pitches need an EARLIER swing, outside pitches a LATER swing.
  3. After contact the game cuts to the OVERHEAD FIELD VIEW. Fielders chase the ball (backups and cutoff men
     help out). The batter runs to first on his own; after that YOU click RUN at every base.
  4. Home runs stay in the batting view with a fireworks celebration. A PERFECT PERFECT swing
     gets a short side-view "slugger" cutscene: bat meets ball, explosion, camera follows it out.
  5. The pitcher has a brain: he picks pitches based on the count (more chase pitches with two strikes,
     fastballs when he is behind, and he mixes it up so he is not predictable).
  6. FLY BALLS: the fielder runs to where he thinks it will land. If it comes down inside his catch circle it is an out,
     otherwise it drops in for a hit. Worse contact = bigger circle (see CATCH_RADIUS). A fly out is clearly CAUGHT (white flash + "CAUGHT!" text). A ball that falls in for a hit bounces
     (dust puff) and rolls on, and the fielder has to chase it down.

STEALING
  With runners on, press S BEFORE the pitch to send them. Odds depend on the pitch:
  fastball is the worst for the runner, curveball / slider / changeup are about 50-50, splitter is a bit better.
  If you put the ball in play the steal is called off. A foul ball sends the runners back.

RARE ANIMATIONS (each has its own chance in the settings - see DIVE_CHANCE etc.)
  Diving stop ........ a fielder dives for a ground ball
  Leaping catch ...... a fielder jumps to snag a fly ball
  Broken bat ......... weak contact snaps the bat
  Fan catch .......... a (tiny) fan in the stands catches a home run
  Scoreboard hit ..... a home run over the scoreboard rocks it and makes it flicker
  Slugger cutscene ... a PERFECT PERFECT swing
  Pause (P) > Animations lets you watch every one of them on demand.

CONTROLS
  Batting:   SPACE or click ........ swing
  Steal:     S before the pitch .... runners go on the pitch (press again to cancel)
  Running:   click RUN button ...... send the runner to the next base (or press R)
             click SLIDE button .... shown when the runner is close to the bag (or press S)
             click the runner ...... turn him around mid-run (short cooldown so you can't flip-flop)
             R while running ....... run THROUGH the next bag without stopping
  Any time:  F11 fullscreen / windowed,  ESC quit
  Pause:     P pauses / resumes (menu: Resume, Difficulty, Animations, Restart Game, Quit to Title)
  Cutscene:  SPACE or click skips the PERFECT PERFECT home run cutscene
  After a ball in play: click the NEXT PITCH button (or press SPACE) to move on
  Game over: line score + stats; click or SPACE returns to the start screen

FILE LAYOUT
  1. SETTINGS ......... every number you might want to tweak
  2. DATA CLASSES ..... Pitch, Hit, Ball, Fielder, Runner, FieldPlay
  3. DRAWING HELPERS .. backgrounds, people, buttons, title lettering (these never change the game)
  4. GAME CLASS ....... the rules (pitching, swinging, fielding AI, baserunning, scoring)
  5. MENU CLASS ....... the start screen
  6. MAIN LOOP

All times are in SECONDS. "bases" as a position means: 0=home, 1=first, 2=second, 3=third, 4=home again.
"""
import json
import math
import os
import random
import sys
from dataclasses import dataclass, field

import pygame

# =============================================================================
# 1. SETTINGS  -  change these to change how the game feels
# =============================================================================

FULLSCREEN = True               # start fullscreen (F11 toggles)
WINDOW_SCALE = 0.9              # window size (windowed mode) relative to the 1280x720 canvas
FPS = 60
LOGICAL_W, LOGICAL_H = 1280, 720    # the game is drawn on this canvas and scaled to fit your screen
BAT_W, BAT_H = 770, 390             # size of the batting-view picture (scaled up to fill the screen)
FADE_TIME = 0.3                     # fade-in when the view switches

# --- Start screen ------------------------------------------------------------
TITLE_TEXT = "FLASH BASEBALL"
TITLE_FONT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "title_font.ttf")   # optional custom font
TITLE_FONT_NAMES = "impact,haettenschweiler,arialblack,franklingothicheavy,anton,bebasneue"   # tried in order if no file
DEFAULT_TEAM_NAME = "SLUGGERS"
MAX_NAME_LENGTH = 12
DEFAULT_DIFFICULTY = "Medium"
INNING_OPTIONS = [1, 3, 5, 9]    # game lengths offered on the start screen
DEFAULT_INNINGS = 3
LOGO_PX = 48                     # logos are 48x48 pixel pictures
LOGO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "home_logo.png")   # your drawn logo is saved here
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "flash_baseball_settings.json")   # team name, color, difficulty, innings
PEN_COLORS = [(255, 255, 255), (20, 20, 24), (230, 50, 50), (242, 201, 76), (60, 200, 90), (70, 140, 255)]
TEAM_COLORS = [                  # (label, colour) - used for the batter's helmet and your runners' caps
    ("Navy", (44, 58, 128)), ("Red", (214, 48, 48)), ("Orange", (242, 134, 32)), ("Gold", (235, 190, 40)),
    ("Green", (34, 150, 76)), ("Teal", (24, 170, 180)), ("Purple", (136, 70, 180)), ("Black", (40, 40, 46)),
]

# --- Players -----------------------------------------------------------------
# Every batter gets a random skin tone (tan to dark). He keeps it from the batter's box all the way around the bases.
# The fielders each get one for the whole game.
SKIN_TONES = [(226, 184, 134), (210, 164, 114), (190, 142, 98), (164, 116, 78), (136, 94, 62), (106, 72, 48), (82, 55, 38)]
SKIN_DEFAULT = (224, 190, 150)
# Batter's swing (batting view): the bat takes SWING_TIME seconds to reach the ball, then follows through
LOAD_TIME = 0.30                 # the batter loads (hands go back and up) during the last part of the wind-up
SETTLE_TIME = 0.35               # how long the batter takes to ease from his held finish back to the stance for the next pitch
SWING_TIME = 0.15
FOLLOW_TIME = 0.20
BAT_DRAW_LENGTH = 100            # bat length in pixels in the batting view

# --- Gait: sway + dust under the feet --------------------------------------------
SWAY_AMOUNT = 1.6                # how far (pixels) a running player's head sways side to side
BOB_AMOUNT = 1.4                 # how far he bobs up and down with each step
STRIDE_PER_PIXEL = 0.12          # radians of the step cycle per pixel travelled (bigger = quicker steps)
DUST_RATE = 12                   # dust particles per second from a running player's feet (sliding makes more)
SLIDE_DUST_RATE = 40
MAX_DUST = 350                   # safety cap on the number of particles

# --- Difficulty --------------------------------------------------------------
# speed:   pitch speed multiplier (1.0 = original; bigger = faster pitches, shorter time to react)
# window:  multiplier on ALL the timing windows below (bigger = bigger hit zone)
# splitter_in_green: True = the splitter can be hit if your swing lands inside the green (PERFECT) window
# pitches: which pitches the pitcher can throw
# zone_offset: seconds of timing shift for an inside (earlier) / outside (later) pitch
# blurb:   two lines shown under the difficulty buttons
DIFFICULTIES = {
    "Easy":   dict(speed=0.88, window=1.30, splitter_in_green=True, zone_offset=0.035,
                   pitches=("Fastball", "Curveball", "Splitter"),
                   blurb=("Slower pitches and a bigger hit zone.", "You can even hit the splitter if you swing in the green!")),
    "Medium": dict(speed=1.00, window=1.00, splitter_in_green=False, zone_offset=0.045,
                   pitches=("Fastball", "Curveball", "Splitter"),
                   blurb=("The classic Flash Baseball experience.", "Lay off the splitter.")),
    "Hard":   dict(speed=1.08, window=0.80, splitter_in_green=False, zone_offset=0.055,
                   pitches=("Fastball", "Curveball", "Splitter", "Changeup", "Slider"),
                   blurb=("Faster pitches, a smaller hit zone, plus", "changeups and sliders. No mercy.")),
}

# --- Game length -------------------------------------------------------------
OUTS_PER_INNING = 3
BALLS_FOR_WALK = 4
STRIKES_FOR_OUT = 3
# The CPU's final score is a random number from 0 to CPU_MAX_TOTAL. Once YOU pass CPU_MAX_TOTAL runs,
# it is a random number from 0 to CPU_RATIO_ABOVE_MAX (80%) of your score instead.
# It is rolled once per game (as a 0-100% roll) and the CPU's runs are spread across the innings toward that total.
CPU_MAX_TOTAL = 15
CPU_RATIO_ABOVE_MAX = 0.80

# --- Pitches -----------------------------------------------------------------
# chance:   base relative likelihood (the pitching brain adjusts it by the count)
# seconds:  (fastest, slowest) time to reach the plate. SMALLER = FASTER.   (Medium difficulty values)
# mph:      speed shown for the (fastest, slowest) pitch
# hittable: False = you can never make contact (lay off it)   (Easy lets you hit the splitter in the green)
PITCHES = {
    "Fastball":  dict(chance=40, seconds=(0.42, 0.54), mph=(100, 90), hittable=True),
    "Curveball": dict(chance=40, seconds=(0.72, 0.92), mph=(80, 71),  hittable=True),
    "Splitter":  dict(chance=20, seconds=(0.55, 0.63), mph=(89, 84),  hittable=False),
    "Changeup":  dict(chance=18, seconds=(0.66, 0.80), mph=(88, 80),  hittable=True),    # Hard only: hot out of the hand, then it dies
    "Slider":    dict(chance=16, seconds=(0.52, 0.60), mph=(88, 82),  hittable=False),   # Hard only: always a ball, like the splitter
}
PAUSE_BEFORE_PITCH = 0.9
WIND_UP_TIME = 0.9               # the pitcher's windup: settle, leg kick, stride, then the arm whips through
PITCH_FOLLOW_TIME = 0.25         # seconds the pitcher's arm takes to carry through after the release
RELEASE_BLEND = 0.18             # first part of the pitch's flight (0-1) during which the ball travels from his hand onto its path
DUGOUT_WALK_SPEED = 85           # pixels per second: how fast a batter who made an out walks back to the dugout
DUGOUTS = {"left": (150, 672), "right": (1130, 672)}   # where he heads (the nearer one); he disappears inside when he arrives
LOC_NAMES = ["inside", "middle", "outside"]      # zone -1 / 0 / +1
ZONE_WEIGHTS = (25, 50, 25)                      # normal chance of inside / middle / outside
CHANGEUP_HOT_START = 1.9                         # bigger = the changeup looks faster out of the hand (and slower at the end)

# --- Stealing ----------------------------------------------------------------
# chance the runners get the bag when you press S before this pitch
STEAL_CHANCE = {"Fastball": 0.30, "Curveball": 0.50, "Slider": 0.50, "Changeup": 0.50, "Splitter": 0.60}

# --- Foul balls --------------------------------------------------------------
FOUL_CAUGHT_CHANCE = 0.10        # a foul pop that gets caught = an out
FOUL_TIP_CHANCE = 0.12           # with two strikes, a foul can be a foul tip into the catcher's mitt = strikeout

# --- Reading the seams (magnified ball in the top-right corner of the batting view) ---
SHOW_SEAM_WINDOW = True          # False hides the window entirely
SHOW_SEAM_LEGEND = True          # False hides the little answer key under the window
SEAM_PREVIEW_TIME = 0.15         # the window opens this long BEFORE release so you get a head start
# (spin speed in radians/second, tilt of the spin axis). Negative = seams roll UP (backspin), positive = DOWN.
SEAM_SPIN = {"Fastball": (-16.0, 0.0), "Curveball": (7.5, 0.3), "Splitter": (0.9, 0.6),
             "Changeup": (-8.0, 0.0), "Slider": (8.5, 1.9)}
SEAM_LEGEND_TEXT = {"Fastball": "seams UP = fastball", "Curveball": "seams DOWN = curve", "Splitter": "no spin = splitter",
                    "Changeup": "slower UP = change", "Slider": "tilted = slider"}

# --- Timing windows (seconds away from the perfect swing; smaller = harder) ---
# These are the MEDIUM values; the difficulty's "window" number scales all of them.
PERFECT_PERFECT_WINDOW = 0.009   # guaranteed home run (about one frame wide at 60 FPS - very tight!)
PERFECT_WINDOW = 0.03
GOOD_WINDOW = 0.08
CONTACT_WINDOW = 0.16            # inside this you make contact
FOUL_WINDOW = 0.24               # between CONTACT and this = foul, beyond = swing and miss
METER_EXTRA_TIME = 0.25

# --- What contact turns into -------------------------------------------------
# For each contact quality: (cumulative chance, result)
HIT_TABLES = {
    "perfect_perfect": [(1.00, "HR")],
    "perfect":         [(0.28, "HR"), (0.50, "2B"), (0.58, "3B"), (0.82, "1B"), (1.00, "FLY_OUT")],
    "good":            [(0.30, "1B"), (0.38, "2B"), (0.65, "GROUND_OUT"), (1.00, "FLY_OUT")],
    "weak":            [(0.20, "1B"), (0.58, "GROUND_OUT"), (1.00, "FLY_OUT")],
}
# earned:   bases that runners ALREADY on base advance by themselves on this hit
#           (the batter never runs automatically - you click Run)
# flight:   seconds the ball is in the air
# distance: (min, max) pixels from home plate where the ball lands on the field view
# arc:      how high the ball flies (0 = bouncing grounder)
HIT_INFO = {
    "1B":         dict(earned=1, flight=1.7, distance=(240, 300), arc=85),
    "2B":         dict(earned=2, flight=2.2, distance=(320, 370), arc=125),
    "3B":         dict(earned=3, flight=3.0, distance=(390, 440), arc=160),
    "HR":         dict(earned=4, flight=1.6, distance=(0, 0),     arc=0),
    "FLY_OUT":    dict(earned=0, flight=2.4, distance=(270, 380), arc=170),
    "GROUND_OUT": dict(earned=0, flight=0.9, distance=(120, 210),  arc=0),
}

# --- Fielding ----------------------------------------------------------------
FIELDER_SPEED = 100              # pixels per second (smaller = slower fielders = easier extra bases)
FIELDER_REACTION = 0.7          # seconds a fielder takes to read a fly ball before he starts moving
FIELDER_MISJUDGE = 35            # a fielder runs to where he THINKS a fly ball will land: off by up to this many pixels
# CATCH CIRCLE: when a fly ball lands, it is caught if it comes down inside this many pixels of the fielder.
# Worse contact = bigger circle = more likely to be an out. Anything outside the circle falls in for a hit.
CATCH_RADIUS = {"perfect": 20, "good": 34, "weak": 50}
FIELDER_PICKUP_TIME = 0.5        # seconds a fielder takes to gather a loose ball before throwing
RELAY_TIME = 0.25                # seconds to catch a throw and throw it on (a quick relay)
THROW_SPEED = 450                # pixels per second
BAG_RADIUS = 45                  # a fielder this close to a bag, holding the ball, "is at the base"
DEAD_BALL_DELAY = 0.6            # pitcher has the ball and nobody is running -> play ends after this
CUTOFF_MIN_THROW = 330           # outfield throws longer than this go through a cutoff man (SS or 2B)
BACKUP_DISTANCE = 55             # a backup fielder stands this far behind where the ball lands

# --- Catch / landing effects (so a fly out looks different from a hit that falls in) ---
HIT_ROLL_SPEED = 150             # how fast a ball that falls in keeps rolling after it lands (pixels/second)
GROUNDER_ROLL_SPEED = 70         # same, for ground balls
ROLL_DRAG = 1.8                  # bigger = the ball stops rolling sooner
CATCH_FX_TIME = 1.2              # seconds the white "CAUGHT!" effect lasts

# --- Baserunning -------------------------------------------------------------
RUNNER_SPEED = 1.1               # bases per second
BATTER_START_DELAY = 0.75        # the batter finishes his swing, drops the bat and gets going (bigger = easier to throw him out at first)
RUNNER_START_DELAY = 0.2         # reaction time after contact before runners ALREADY on base take off
SLIDE_RANGE = 0.45               # when closer than this (in bases) to the bag, the button says SLIDE
SLIDE_SPEED_MULT = 1.8           # a slide covers the last stretch this much faster...
SLIDE_RECOVERY = 0.5             # ...but you need this long to get up before you can run again
TURN_COOLDOWN = 0.35             # after sending (or turning) the runner, he can't be turned again for this long
FIELD_PLAY_TIMEOUT = 25          # safety: force the play to end after this many seconds

# --- Messages ----------------------------------------------------------------
MESSAGE_TIME = 1.6
HOME_RUN_MESSAGE_TIME = 2.0
NEXT_PITCH_DELAY = 0.6           # seconds before the NEXT PITCH button appears (only after a ball in play)
NEXT_BUTTON = (1160, 590)        # where the round NEXT PITCH button sits on the canvas
NEXT_BUTTON_RADIUS = 72

# --- Screen shake on solid contact -------------------------------------------
SHAKE_TIME = 0.3                 # seconds
SHAKE_PERFECT = 8                # pixels of shake for a PERFECT hit
SHAKE_PERFECT_PERFECT = 13       # pixels of shake for a PERFECT PERFECT hit (when there is no cutscene)

# --- PERFECT PERFECT home run cutscene (side view, Mario Super Sluggers style) --
SLUGGER_CUTSCENE = True          # False = a PERFECT PERFECT homer just uses the normal home run animation
SLUGGER_HIT_TIME = 0.8           # seconds of slow-motion wind-up before the bat meets the ball
SLUGGER_TIME = 2.8               # total cutscene length (the rest of the time the camera follows the ball)
SLUGGER_HITSTOP = 0.12           # the picture freezes this long on the connecting swing (explosion + flash play over it)

# --- Rare animations ---------------------------------------------------------
# Each chance is rolled when that kind of play happens (0 = never, 1 = every time).
DIVE_CHANCE = 0.30               # on a ground ball, the fielder dives for it
LEAP_CHANCE = 0.30               # on a fly out, the fielder leaps for the catch
BROKEN_BAT_CHANCE = 0.12         # on weak contact, the bat snaps
FAN_CATCH_CHANCE = 0.25          # on a home run into the seats (not over the scoreboard), a fan catches it
BOARD_X_MIN, BOARD_X_MAX = 292, 478   # a home run that ends up between these x positions hits the scoreboard
BOARD_HIT_CHANCE = 0.20          # a home run headed over the scoreboard only actually hits it this often
BOARD_ANIM_TIME = 3.0           # seconds the scoreboard rocks / flickers
DIVE_TIME = 0.5                  # seconds of the dive itself
DIVE_RECOVERY = 0.5              # seconds he lies there / gets up before he can throw
LEAP_TIME = 1.0                  # length of the jump (the catch happens at the top, halfway through)
LEAP_HEIGHT = 36                 # how high (pixels) the fielder rises
FIELDER_SCALE = 1.3              # size of the fielders on the field view
LEAP_GLOVE_Z = LEAP_HEIGHT + 47 * FIELDER_SCALE - 4   # glove height above the ground at the top of the jump
BROKEN_BAT_TIME = 1.4            # how long the flying bat pieces are drawn
FAN_SCALE = 0.3                 # how big the fan is (1.0 = the old giant fan)

# (name, one-line description, seconds long) - this is the list shown in the pause menu's Animations gallery
ANIMATIONS = [
    ("Slugger Cutscene", "PERFECT PERFECT swing = guaranteed home run", SLUGGER_TIME),
    ("Diving Stop", f"Ground balls: {round(DIVE_CHANCE * 100)}% chance", 2.9),
    ("Leaping Catch", f"Fly outs: {round(LEAP_CHANCE * 100)}% chance", 3.0),
    ("Broken Bat", f"Weak contact: {round(BROKEN_BAT_CHANCE * 100)}% chance", 2.4),
    ("Fan Catch", f"Home runs into the seats: {round(FAN_CATCH_CHANCE * 100)}% chance", 3.0),
    ("Scoreboard Hit", f"Home runs over the scoreboard: {round(BOARD_HIT_CHANCE * 100)}% chance", 4.4),
]

# --- Field geometry (canvas pixels) ------------------------------------------
HOME, B1, B2, B3 = (610, 610), (880, 470), (650, 345), (360, 470)
BASES = [HOME, B1, B2, B3, HOME]            # index = base number (4 = home again)
MOUND = (630, 478)
BASE_NAMES = ["first", "second", "third", "home"]
FIELDER_POSTS = {                           # where each fielder stands at the start of a play
    "P": MOUND, "C": (610, 640), "1B": (905, 452), "2B": (700, 352), "SS": (520, 365),
    "3B": (330, 452), "LF": (215, 272), "CF": (640, 252), "RF": (1065, 277),
}
BASE_FIELDERS = {1: "1B", 2: "2B", 3: "3B", 4: "C"}   # who receives a throw to each base

# --- Batting-view positions --------------------------------------------------
BAT_RELEASE_POINT = (387, 212)
BAT_FIELDERS = [(60, 175, 1.3), (240, 150, 1.0), (525, 150, 1.0), (705, 165, 1.3),
                (120, 138, 0.8), (392, 126, 0.8), (615, 138, 0.8)]   # (x, y, size) - just for looks

# --- Colours -----------------------------------------------------------------
WHITE, BLACK = (255, 255, 255), (0, 0, 0)
SLIDE_GREEN = (46, 190, 80)           # colour of the Slide button (Run is teal)
GOLD, RED, GREEN, TEAL = (242, 201, 76), (255, 90, 74), (93, 255, 122), (24, 190, 190)

# =============================================================================
# 2. DATA CLASSES  -  bundles of related values
# =============================================================================

@dataclass
class Pitch:
    name: str
    duration: float            # seconds from release to the plate
    mph: int
    hittable: bool
    time: float = 0.0
    swung: bool = False
    swing_time: float = 0.0
    label: str = ""            # "PERFECT", "EARLY", ... shown on the meter
    result: str = ""           # "", "miss" or "foul"
    zone: int = 0              # -1 inside, 0 middle, +1 outside
    offset: float = 0.0        # the perfect swing is at duration + offset (inside = earlier, outside = later)


@dataclass
class Hit:
    kind: str                  # "1B" "2B" "3B" "HR" "FLY_OUT" "GROUND_OUT"
    quality: str
    start_x: float             # where the ball was when you hit it (batting view)
    start_y: float
    sideways: float            # negative = pulled to left field, positive = right field
    flight: float
    arc: float
    land_x: float = 0.0        # where it lands on the FIELD view
    land_y: float = 0.0
    time: float = 0.0
    broken_bat: bool = False   # rare animation: the bat snapped on this swing
    distance: int = 0          # home run distance in feet (changes how high / far the ball flies)
    caught: bool = False       # fly balls: did it land inside the catch circle?
    read_x: float = 0.0        # where the fielder THINKS the ball will land (he runs here)
    read_y: float = 0.0
    catch_x: float = 0.0       # if caught: where the fielder is standing when it arrives
    catch_y: float = 0.0


@dataclass
class Ball:
    x: float
    y: float
    z: float = 0.0             # height above the ground (drawn as an upward offset)
    mode: str = "flying"       # "flying" (off the bat) | "loose" (on the ground) | "held" | "thrown"
    holder: int = -1           # index of the fielder holding it
    hold_time: float = 0.0     # how long the holder has had it
    quick: bool = False        # True if he just caught a throw (relay) instead of picking up a loose ball
    t: float = 0.0             # animation clock for flying / thrown
    dur: float = 1.0           # duration of the current throw
    sx: float = 0.0            # throw start / end points
    sy: float = 0.0
    tx: float = 0.0
    ty: float = 0.0
    receiver: int = -1
    vx: float = 0.0            # rolling velocity after landing
    vy: float = 0.0
    bt: float = 0.0            # seconds since it landed (drives the bounce)


@dataclass
class Fielder:
    name: str
    post: tuple                # where he wants to stand
    x: float
    y: float


@dataclass
class Runner:
    """The batter after contact - the runner YOU control."""
    earned: int                # guaranteed bases
    moving: bool = True
    wait: float = 0.0          # reaction delay before the first step
    pos: float = 0.0           # 0=home, 1=first, 2=second, 3=third, 4=scored
    target: int = 1            # base he is running toward (or back toward)
    forward: bool = True
    sliding: bool = False
    run_through: bool = False  # player pressed R: don't stop at the next bag
    turn_cooldown: float = 0.0
    recovery: float = 0.0      # getting up after a slide


@dataclass
class FieldPlay:
    hit: Hit
    runner: Runner
    fielders: list
    ball: Ball
    others: list               # other runners already on base: dicts (start, end, pos)
    others_runs: int           # runs those runners will score
    new_bases: list            # where those runners end up
    index: dict                # fielder name -> index
    chaser: int                # the fielder going after the ball
    boost: float               # chaser speed multiplier (guarantees fly-ball catches)
    time: float = 0.0
    pending: tuple = None      # (outcome, base) once the play is decided
    pending_time: float = 0.0  # how long to wait before showing the result
    dead_time: float = 0.0
    dive_plan: bool = False    # rare animation: this ground ball will get a diving stop
    dive: dict = None          # the dive in progress: idx (fielder), t (seconds), dir (-1 left / +1 right)
    dived: bool = False
    leap_plan: bool = False    # rare animation: this fly out will get a leaping catch
    leap: dict = None          # the leap in progress: t (seconds)
    leaped: bool = False
    broken: dict = None        # the broken bat: t (seconds), dir (unit vector the pieces fly along)
    catch: dict = None         # a fly ball was caught: t (seconds)
    landed: dict = None        # a hit landed on the grass: t, x, y (dust puff)
    skin: tuple = None         # the batter-runner's skin tone
    gait: dict = field(default_factory=dict)      # step-cycle phase for every moving player (drives the sway)
    prev: dict = field(default_factory=dict)      # where each player was last frame
    moving: set = field(default_factory=set)      # who is moving right now
    dust: list = field(default_factory=list)      # dust / grass particles under running feet
    walk: dict = None          # after an out: the batter walking back to the dugout (sx, sy, tx, ty, t, done)


# =============================================================================
# 3. DRAWING HELPERS  -  these only draw, they never change the game
# =============================================================================

_font_cache = {}
_title_font_cache = {}

def get_font(size):
    if size not in _font_cache:
        _font_cache[size] = pygame.font.SysFont("verdana,dejavusans,arial", size, bold=True)
    return _font_cache[size]


def get_title_font(size):
    """The big lettering font: your own title_font.ttf if present, else a heavy system font, else a bold fallback."""
    if size not in _title_font_cache:
        font = None
        if os.path.exists(TITLE_FONT_FILE):
            try:
                font = pygame.font.Font(TITLE_FONT_FILE, size)
            except pygame.error:
                font = None
        if font is None:
            path = pygame.font.match_font(TITLE_FONT_NAMES)
            if path:
                font = pygame.font.Font(path, size)
                font.set_italic(True)                         # slanted for speed
            else:
                font = pygame.font.SysFont("verdana,dejavusans,arial", size, bold=True, italic=True)
        _title_font_cache[size] = font
    return _title_font_cache[size]


def draw_text(surface, text, x, y, size=16, color=WHITE, outline=True, align="center"):
    """Text with a black outline so it reads on any background. (x, y) is the baseline position."""
    font = get_font(size)
    image = font.render(text, True, color)
    rect = image.get_rect()
    setattr(rect, {"center": "midtop", "left": "topleft", "right": "topright"}[align], (x, y - size))
    if outline:
        shadow = font.render(text, True, BLACK)
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)):
            surface.blit(shadow, rect.move(dx, dy))
    surface.blit(image, rect)


def lerp(a, b, t):
    return a + (b - a) * t


def clamp(value, low, high):
    return max(low, min(high, value))


def point_on_path(pos):
    """Screen position for a base-path position (0..4)."""
    pos = clamp(pos, 0, 4)
    i = min(3, int(pos))
    t = pos - i
    return lerp(BASES[i][0], BASES[i + 1][0], t), lerp(BASES[i][1], BASES[i + 1][1], t)


def unit(dx, dy):
    n = math.hypot(dx, dy)
    return dx / n, dy / n


U_LEFT = unit(B3[0] - HOME[0], B3[1] - HOME[1])      # direction of the left-field foul line
U_RIGHT = unit(B1[0] - HOME[0], B1[1] - HOME[1])     # direction of the right-field foul line


def _grass_polygon():
    """The outline of the outfield lawn (the same shape the background draws)."""
    half = LOGICAL_W / 2
    arc = [math.pi * i / 40 for i in range(41)]
    grass_top = [(half + half * math.cos(a), 268 - 72 * math.sin(a)) for a in reversed(arc)]
    left_end = (0, HOME[1] + U_LEFT[1] * (HOME[0] / -U_LEFT[0]))
    right_end = (LOGICAL_W, HOME[1] + U_RIGHT[1] * ((LOGICAL_W - HOME[0]) / U_RIGHT[0]))
    return [HOME, left_end] + grass_top + [right_end]


GRASS_POLY = _grass_polygon()


def point_in_polygon(x, y, poly):
    inside, j = False, len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def dist_to_segment(px, py, a, b):
    abx, aby = b[0] - a[0], b[1] - a[1]
    t = clamp(((px - a[0]) * abx + (py - a[1]) * aby) / (abx * abx + aby * aby), 0, 1)
    return math.hypot(px - (a[0] + abx * t), py - (a[1] + aby * t))


def terrain_at(x, y):
    """What a player is standing on in the field view: 'sand' (infield dirt: base paths, base circles, mound, home),
    'grass' (the lawn) or 'track' (the red warning track / foul ground)."""
    if math.hypot(x - HOME[0], y - HOME[1]) < 78 or math.hypot(x - MOUND[0], y - MOUND[1]) < 34:
        return "sand"
    if any(math.hypot(x - b[0], y - b[1]) < 50 for b in (B1, B2, B3)):
        return "sand"
    if any(dist_to_segment(x, y, BASES[i], BASES[i + 1]) < 37 for i in range(4)):
        return "sand"
    return "grass" if point_in_polygon(x, y, GRASS_POLY) else "track"


# shadow colour and dust for each surface. "blades" = bits of grass flung up, "puff" = a little cloud of dirt
TERRAIN = {
    "grass": dict(shadow=(35, 85, 35),  dust=[(92, 172, 70), (66, 140, 56), (122, 192, 92)], kind="blades"),
    "sand":  dict(shadow=(150, 98, 58), dust=[(226, 184, 132), (208, 160, 106), (190, 140, 90)], kind="puff"),
    "track": dict(shadow=(104, 56, 40), dust=[(178, 110, 82), (156, 92, 66), (192, 124, 92)], kind="puff"),
}


def landing_spot(kind, sideways):
    """Where a batted ball lands on the field. Early swings pull to left, late swings go to right."""
    t = (sideways + 300) / 600
    ux, uy = unit(lerp(U_LEFT[0], U_RIGHT[0], t), lerp(U_LEFT[1], U_RIGHT[1], t))
    lo, hi = HIT_INFO[kind]["distance"]
    d = random.uniform(lo, hi)
    return clamp(HOME[0] + ux * d, 80, 1200), clamp(HOME[1] + uy * d, 262, 700)


def draw_person(surf, x, y, scale=1.0, body=(40, 60, 120), cap=(30, 40, 90), sliding=False, shadow=True,
                skin=SKIN_DEFAULT, shadow_color=(35, 85, 35), sway=0.0, bob=0.0):
    """A tiny baseball person. (x, y) is where his feet are. sway / bob (pixels) make a running player rock side to side
    and bounce a little; the shadow stays on the ground and takes the colour of whatever he is standing on."""
    s = scale
    if shadow:
        pygame.draw.ellipse(surf, shadow_color, (x - 11 * s, y - 3 * s, 22 * s, 8 * s))      # shadow
    if sliding:
        pygame.draw.ellipse(surf, body, (x - 15 * s, y - 11 * s, 30 * s, 11 * s))
        pygame.draw.circle(surf, skin, (x + 14 * s, y - 8 * s), 5 * s)
        return
    top = y - bob                                                  # the body lifts off the ground a touch with each step
    pygame.draw.ellipse(surf, body, (x - 6 * s + sway * 0.5 * s, top - 26 * s, 12 * s, 26 * s))
    pygame.draw.circle(surf, skin, (x + sway * s, top - 31 * s), 5 * s)
    pygame.draw.circle(surf, cap, (x + sway * s, top - 33 * s), 5.5 * s, draw_top_left=True, draw_top_right=True)


def build_default_logo(name, color):
    """The home team's logo until you draw one: a badge in the team colour with the team's first letter."""
    s = pygame.Surface((LOGO_PX, LOGO_PX), pygame.SRCALPHA)
    dark = tuple(int(c * 0.6) for c in color)
    pygame.draw.circle(s, color, (24, 24), 23)
    pygame.draw.circle(s, WHITE, (24, 24), 23, 3)
    pygame.draw.circle(s, dark, (24, 24), 17, 2)
    letter = (name.strip()[:1] or "H").upper()
    image = get_font(26).render(letter, True, WHITE)
    s.blit(image, image.get_rect(center=(24, 25)))
    return s


def build_cpu_logo():
    """The CPU team's logo: a dark shield with a red border."""
    s = pygame.Surface((LOGO_PX, LOGO_PX), pygame.SRCALPHA)
    shield = [(5, 5), (43, 5), (43, 26), (24, 44), (5, 26)]
    pygame.draw.polygon(s, (58, 64, 86), shield)
    pygame.draw.polygon(s, (225, 60, 60), shield, 3)
    image = get_font(13).render("CPU", True, WHITE)
    s.blit(image, image.get_rect(center=(24, 20)))
    pygame.draw.rect(s, (225, 60, 60), (14, 28, 20, 3))
    return s


def compose_logo(drawing, color):
    """Your drawing, stitched onto a patch in the team colour."""
    s = pygame.Surface((LOGO_PX, LOGO_PX), pygame.SRCALPHA)
    pygame.draw.rect(s, color, (0, 0, LOGO_PX, LOGO_PX), border_radius=9)
    s.blit(drawing, (0, 0))
    pygame.draw.rect(s, WHITE, (0, 0, LOGO_PX, LOGO_PX), 2, border_radius=9)
    return s


def draw_logo(surf, logo, x, y, size):
    surf.blit(pygame.transform.smoothscale(logo, (size, size)), (x, y))


def draw_button(surf, x, y, label, color=TEAL):
    """The Run (teal) / Slide (green) button: ellipse on the bag, an up-arrow, and a label."""
    rect = pygame.Rect(0, 0, 70, 32)
    rect.center = (x, y)
    pygame.draw.ellipse(surf, color, rect)
    pygame.draw.ellipse(surf, (225, 255, 235), rect, 2)
    pygame.draw.polygon(surf, color, [(x, y + 20), (x - 13, y + 36), (x + 13, y + 36)])
    pygame.draw.rect(surf, color, (x - 5, y + 36, 10, 12))
    draw_text(surf, label, x, y + 72, 20, color)


def draw_next_pitch_button(surf, t):
    """Big round glossy NEXT PITCH button, shown after every ball in play."""
    x, y = NEXT_BUTTON
    r = NEXT_BUTTON_RADIUS + int(3 * math.sin(t * 5))                  # gentle pulse
    pygame.draw.circle(surf, (15, 30, 40), (x, y + 5), r + 6)            # shadow
    pygame.draw.circle(surf, (195, 210, 220), (x, y), r + 4)             # silver rim
    pygame.draw.circle(surf, (22, 140, 155), (x, y), r)                  # teal body
    pygame.draw.ellipse(surf, (80, 215, 225), (x - r * 0.72, y - r * 0.95, r * 1.44, r * 0.85))   # gloss
    draw_text(surf, "NEXT", x, y - 4, 30)
    draw_text(surf, "PITCH", x, y + 30, 30)


def fill_polygon_stripes(surf, points, color_a, color_b, band=26):
    """Fill a (convex) polygon with horizontal mowing stripes."""
    ys = [p[1] for p in points]
    for y in range(int(min(ys)), int(max(ys)) + 1):
        xs = []
        for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
            if y1 <= y < y2 or y2 <= y < y1:
                xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
        if len(xs) >= 2:
            pygame.draw.line(surf, color_a if (y // band) % 2 else color_b, (min(xs), y), (max(xs), y))


# --- the living crowd + the dugouts --------------------------------------------------
CROWD_COLORS = [(150, 110, 100), (190, 180, 170), (120, 125, 140), (170, 70, 70), (210, 200, 120), (90, 120, 170), (205, 205, 215)]
CROWD_BASE_ENERGY = 0.18         # how lively the crowd is when nothing is happening (0 = statues)
CROWD_DECAY = 0.30               # energy drained per second after a cheer
CROWD_WAVE_EVERY = 28.0          # seconds between "stadium waves" while things are quiet
CROWD_WAVE_LENGTH = 7.0          # how long each wave lasts
CROWD_TEAM_FANS = 0.12           # fraction of the crowd wearing your team colour
CROWD_CPU_FANS = 0.08            # ...and the CPU's red


def build_field_crowd():
    """Positions + personalities for every fan in the overhead view's stands."""
    rnd, crowd, half = random.Random(11), [], LOGICAL_W / 2
    for _ in range(2700):
        x = rnd.random() * LOGICAL_W
        wall_y = 240 - 70 * math.sqrt(max(0, 1 - ((x - half) / half) ** 2))
        if wall_y - 12 > 108:
            crowd.append(make_fan(rnd, x, rnd.uniform(108, wall_y - 12), 4))
    return crowd


def build_bat_crowd():
    """Fans for the batting view's stands (smaller squares)."""
    rnd = random.Random(12)
    return [make_fan(rnd, rnd.random() * BAT_W, 31 + rnd.random() * 82, 3) for _ in range(620)]


def make_fan(rnd, x, y, size):
    roll = rnd.random()
    kind = 1 if roll < CROWD_TEAM_FANS else 2 if roll < CROWD_TEAM_FANS + CROWD_CPU_FANS else 0
    return (x, y, rnd.randrange(len(CROWD_COLORS)), rnd.randrange(len(CROWD_COLORS)), rnd.random() * 6.283,
            rnd.uniform(2.2, 4.6), size, kind)


def draw_crowd(surf, crowd, t, energy, team_color, width):
    """Every fan bobs, sways and sometimes changes colour (a new jersey, a jacket coming off...). The bigger the energy,
    the higher they jump, and fans with energy to spare throw their arms up. Now and then a stadium wave rolls across
    and a few camera flashes pop."""
    e = clamp(CROWD_BASE_ENERGY + energy, 0, 1.4)
    amp = 0.7 + 4.2 * e
    wave_on = (t % CROWD_WAVE_EVERY) < CROWD_WAVE_LENGTH or e > 0.85
    wave_phase = t * 3.2
    fill = surf.fill
    sin = math.sin
    for x, y, c1, c2, phase, rate, size, kind in crowd:
        local = t * rate + phase
        lift = max(0.0, sin(local)) * amp
        if wave_on:
            lift += max(0.0, sin(x / width * 9.4 - wave_phase)) * (3 + 2 * e)
        if kind == 1:
            color = team_color
        elif kind == 2:
            color = (205, 60, 60)
        else:
            color = CROWD_COLORS[c2 if int(t * 0.4 + phase * 3) % 5 == 0 else c1]      # an occasional change of colour
        px, py = x + sin(local * 0.6 + phase) * (0.7 + e), y - lift
        fill(color, (px, py, size, size))
        if lift > 2.6 + size * 0.2:                                                    # arms up!
            fill(color, (px - 1, py - 2, 1, 3))
            fill(color, (px + size, py - 2, 1, 3))
        if int(t * 12 + phase * 50) % 1100 == 0:                                       # a camera flash
            fill((255, 255, 255), (px - 2, py - 2, size + 4, size + 4))


def draw_dugout_back(surf, dx, dy):
    """The part of a dugout that never moves: concrete apron, roof, dark interior, bench, water cooler, bat rack."""
    pygame.draw.rect(surf, (112, 116, 124), (dx - 80, dy - 46, 160, 76), border_radius=7)               # concrete apron
    pygame.draw.rect(surf, (140, 144, 152), (dx - 80, dy - 46, 160, 76), 2, border_radius=7)
    pygame.draw.rect(surf, (24, 26, 34), (dx - 70, dy - 38, 140, 52), border_radius=5)                  # dark interior
    for i in range(-4, 5):                                                                              # back-wall slats
        pygame.draw.line(surf, (36, 39, 50), (dx + i * 15, dy - 36), (dx + i * 15, dy + 4), 2)
    pygame.draw.rect(surf, (66, 72, 92), (dx - 74, dy - 48, 148, 14), border_radius=4)                  # roof
    pygame.draw.rect(surf, (112, 120, 144), (dx - 74, dy - 48, 148, 14), 2, border_radius=4)
    for i in range(-7, 8):
        pygame.draw.line(surf, (50, 55, 74), (dx + i * 10, dy - 46), (dx + i * 10, dy - 36), 1)         # roof ribs
    pygame.draw.rect(surf, (150, 108, 64), (dx - 64, dy - 1, 128, 9), border_radius=2)                  # wooden bench
    pygame.draw.rect(surf, (188, 142, 90), (dx - 64, dy - 1, 128, 3), border_radius=2)
    pygame.draw.rect(surf, (96, 66, 38), (dx - 64, dy + 6, 128, 3))
    for i in range(5):                                                                                  # bat rack on the left wall
        pygame.draw.line(surf, (214, 176, 90), (dx - 66 + i * 3, dy - 14), (dx - 64 + i * 3, dy - 30), 2)
    pygame.draw.rect(surf, (80, 84, 98), (dx - 69, dy - 15, 16, 3))
    pygame.draw.rect(surf, (230, 126, 30), (dx + 52, dy - 17, 11, 15), border_radius=2)                 # water cooler
    pygame.draw.rect(surf, (240, 240, 244), (dx + 50, dy - 20, 15, 4), border_radius=2)
    pygame.draw.circle(surf, (120, 190, 235), (dx + 57, dy - 9), 2)


def draw_dugout_front(surf, dx, dy):
    """The lip and railing in FRONT of the players (so they look like they are sitting inside)."""
    pygame.draw.rect(surf, (70, 76, 96), (dx - 72, dy + 8, 144, 11), border_radius=3)
    pygame.draw.rect(surf, (120, 128, 150), (dx - 72, dy + 8, 144, 3), border_radius=3)
    pygame.draw.line(surf, (214, 219, 228), (dx - 70, dy + 3), (dx + 70, dy + 3), 2)                    # railing
    for i in range(7):
        pygame.draw.rect(surf, (214, 219, 228), (dx - 70 + i * 23, dy + 3, 3, 7))


def draw_dugout_players(surf, dx, dy, body, cap, t, energy, seed):
    """Five teammates sitting on the bench. They bob and clap quietly, and jump up with their arms in the air when the
    team's energy is high. (energy: 0 = just sitting, 1 = going wild)"""
    for i in range(5):
        x = dx - 46 + i * 21
        phase = seed + i * 1.7
        lvl = clamp(0.12 + energy * 1.25 + 0.28 * math.sin(t * 0.5 + phase * 3), 0, 1.4)    # each guy gets excited on his own
        bounce = max(0.0, math.sin(t * (4.0 + i * 0.5) + phase)) * (0.6 + 3.6 * lvl) if lvl > 0.35 else 0.0
        by = dy + 7 - bounce
        skin = SKIN_TONES[(i * 3 + seed.__int__()) % len(SKIN_TONES)]
        pygame.draw.ellipse(surf, body, (x - 6.5, by - 21, 13, 21))                                    # torso
        if lvl > 0.5:                                                                                  # cheering: both arms up
            wave = math.sin(t * 9 + phase) * 2.5
            for sign in (-1, 1):
                hand = (x + sign * (9 + wave * 0.3), by - 31 + wave * sign * 0.4)
                pygame.draw.line(surf, body, (x + sign * 5, by - 17), hand, 3)
                pygame.draw.circle(surf, skin, hand, 2)
        else:                                                                                          # sitting: arms resting, a little head bob
            pygame.draw.line(surf, body, (x - 5, by - 16), (x - 7, by - 7), 3)
            pygame.draw.line(surf, body, (x + 5, by - 16), (x + 7, by - 7), 3)
        head_y = by - 25 + math.sin(t * 1.6 + phase) * (0.5 if lvl <= 0.5 else 0.0)
        pygame.draw.circle(surf, skin, (x, head_y), 4.6)
        pygame.draw.circle(surf, cap, (x, head_y - 1.5), 5, draw_top_left=True, draw_top_right=True)
        pygame.draw.rect(surf, cap, (x - 1, head_y - 2, 7, 2))                                         # cap brim


def build_field_background():
    """The overhead stadium: skyline, stands, wall, striped grass, dirt, bases, foul lines."""
    surf = pygame.Surface((LOGICAL_W, LOGICAL_H))
    surf.fill((150, 82, 58))                                              # red-brown dirt / warning track
    half = LOGICAL_W / 2
    arc = [math.pi * i / 40 for i in range(41)]                          # angles from right edge to left edge
    wall = [(half + half * math.cos(a), 240 - 70 * math.sin(a)) for a in arc]
    grass_top = [(half + half * math.cos(a), 268 - 72 * math.sin(a)) for a in reversed(arc)]  # left to right
    for y in range(0, 270):                                               # sky
        t = y / 270
        pygame.draw.line(surf, (int(lerp(60, 140, t)), int(lerp(100, 180, t)), int(lerp(160, 215, t))), (0, y), (LOGICAL_W, y))
    for _ in range(40):                                                   # skyline
        bx, bw, bh = random.randint(0, LOGICAL_W), random.randint(30, 80), random.randint(25, 85)
        pygame.draw.rect(surf, (random.randint(95, 130),) * 3, (bx, 100 - bh, bw, bh))
    pygame.draw.polygon(surf, (84, 76, 74), [(0, 100), (LOGICAL_W, 100)] + wall)        # stands
    # (the crowd is NOT painted here any more - build_field_crowd() makes it and draw_crowd() animates it every frame)
    pygame.draw.polygon(surf, (30, 80, 52), wall + [(x, y + 26) for x, y in reversed(wall)])  # outfield wall
    # grass: the wedge between the two foul lines
    left_end = (0, HOME[1] + U_LEFT[1] * (HOME[0] / -U_LEFT[0]))
    right_end = (LOGICAL_W, HOME[1] + U_RIGHT[1] * ((LOGICAL_W - HOME[0]) / U_RIGHT[0]))
    grass = [HOME, left_end] + grass_top + [right_end]
    fill_polygon_stripes(surf, grass, (58, 134, 52), (70, 150, 62))
    # infield dirt: thick base paths + circles around each base
    dirt = (198, 140, 86)
    for i in range(4):
        pygame.draw.line(surf, dirt, BASES[i], BASES[i + 1], 74)
    for p, r in ((B1, 50), (B2, 50), (B3, 50), (HOME, 78)):
        pygame.draw.circle(surf, dirt, p, r)
    cx = sum(p[0] for p in BASES[:4]) / 4
    cy = sum(p[1] for p in BASES[:4]) / 4
    pygame.draw.polygon(surf, (74, 158, 60), [(p[0] + (cx - p[0]) * 0.4, p[1] + (cy - p[1]) * 0.4) for p in BASES[:4]])
    pygame.draw.circle(surf, dirt, MOUND, 34)                             # pitcher's mound
    pygame.draw.rect(surf, WHITE, (MOUND[0] - 9, MOUND[1] - 2, 18, 4))
    pygame.draw.line(surf, WHITE, HOME, left_end, 3)                      # foul lines
    pygame.draw.line(surf, WHITE, HOME, right_end, 3)
    pygame.draw.circle(surf, WHITE, HOME, 62, 3)                          # chalk circle around home
    for bx in (HOME[0] - 54, HOME[0] + 26):                               # batter's boxes
        pygame.draw.rect(surf, WHITE, (bx, HOME[1] - 18, 28, 46), 2)
    for p in (B1, B2, B3):                                                # bags
        pygame.draw.polygon(surf, WHITE, [(p[0], p[1] - 10), (p[0] + 12, p[1]), (p[0], p[1] + 10), (p[0] - 12, p[1])])
    pygame.draw.polygon(surf, WHITE, [(HOME[0] - 11, HOME[1] - 8), (HOME[0] + 11, HOME[1] - 8), (HOME[0] + 11, HOME[1] + 2),
                                      (HOME[0], HOME[1] + 12), (HOME[0] - 11, HOME[1] + 2)])
    for dx, dy in DUGOUTS.values():                                       # the two dugouts, down in foul territory
        draw_dugout_back(surf, dx, dy)                                    # (players + front rail are drawn live)
    return surf


def build_bat_background():
    """The batting view (behind the batter): sky, crowd, grass, dirt, lines. Drawn once."""
    surf = pygame.Surface((BAT_W, BAT_H))
    for y in range(130):
        t = y / 130
        pygame.draw.line(surf, (int(lerp(42, 111, t)), int(lerp(74, 179, t)), int(lerp(122, 200, t))), (0, y), (BAT_W, y))
    pygame.draw.rect(surf, (76, 81, 89), (0, 20, BAT_W, 95))
    # (the crowd is animated live - see build_bat_crowd() and draw_crowd())
    pygame.draw.rect(surf, (58, 157, 181), (0, 112, BAT_W, 22))
    for i in range(8):
        pygame.draw.rect(surf, (63, 143, 46) if i % 2 else (71, 153, 47), (0, 134 + i * 32, BAT_W, 32))
    dirt = (198, 138, 82)
    pygame.draw.ellipse(surf, dirt, (385 - 400, 300 - 115, 800, 230))
    pygame.draw.polygon(surf, (74, 154, 53), [(385, 240), (580, 300), (385, 392), (190, 300)])
    pygame.draw.ellipse(surf, dirt, (385 - 48, 212 - 12, 96, 24))
    pygame.draw.rect(surf, WHITE, (380, 210, 10, 3))
    pygame.draw.line(surf, WHITE, (385, 392), (0, 214), 4)
    pygame.draw.line(surf, WHITE, (385, 392), (BAT_W, 214), 4)
    pygame.draw.polygon(surf, WHITE, [(372, 368), (408, 368), (408, 378), (390, 388), (372, 378)])
    return surf


# --- batting-view drawing -----------------------------------------------------

def draw_bat_scoreboard(surf, game):
    """The scoreboard. When a home run hits it (game.board_time >= 0) it rocks back and forth and flickers."""
    board = pygame.Surface((190, 92), pygame.SRCALPHA)
    t = game.board_time
    angle, lit = 0.0, True
    if t >= 0:
        angle = 9 * math.exp(-2.6 * t) * math.sin(t * 22)                # damped rocking, in degrees
        lit = not (t < 2.0 and int(t * 18) % 3 == 0)                     # lights flicker for the first two seconds
    pygame.draw.rect(board, (31, 35, 39) if lit else (14, 16, 18), (0, 0, 190, 92), border_radius=6)
    pygame.draw.rect(board, (102, 102, 102), (0, 0, 190, 92), 2, border_radius=6)
    if lit:
        for i in range(OUTS_PER_INNING):
            pygame.draw.circle(board, (232, 232, 232), (20 + i * 14, 16), 5, 0 if i < game.outs else 1)
        draw_text(board, f"INN {game.inning}/{game.innings}", 95, 21, 11, (232, 232, 232), outline=False)
        draw_text(board, f"B{game.balls} S{game.strikes}", 180, 21, 11, (232, 232, 232), outline=False, align="right")
        score_text = f"{game.runs} - {game.cpu_runs}"
        score_size = 38
        while score_size > 18 and get_font(score_size).size(score_text)[0] > 112:     # leave room for the logos
            score_size -= 2
        draw_text(board, score_text, 95, 70, score_size, (232, 232, 232), outline=False)
        draw_logo(board, game.home_logo, 5, 27, 28)
        draw_logo(board, game.cpu_logo, 157, 27, 28)
        name_size = 10                                                   # shrink long team names so the whole name fits
        while name_size > 6 and get_font(name_size).size(game.team_name)[0] > 118:
            name_size -= 1
        draw_text(board, game.team_name, 8, 86, name_size, (232, 232, 232), outline=False, align="left")
        draw_text(board, "CPU", 182, 86, 10, (232, 232, 232), outline=False, align="right")
    rotated = pygame.transform.rotate(board, angle)
    surf.blit(rotated, rotated.get_rect(center=(385, 68)))
    if 0 <= t < 0.7:                                                      # a burst of sparks on impact
        for i in range(10):
            a = i * 0.63
            r0, r1 = 30 + 120 * t, 45 + 190 * t
            pygame.draw.line(surf, (255, 225, 90), (385 + r0 * math.cos(a), 68 + r0 * math.sin(a) * 0.6),
                             (385 + r1 * math.cos(a), 68 + r1 * math.sin(a) * 0.6), 2)


def draw_base_indicator(surf, x, y, bases, armed):
    """A little diamond in the corner showing who is on base (gold = occupied)."""
    pts = [(x, y + 20), (x + 20, y), (x, y - 20), (x - 20, y)]           # home, first, second, third
    pygame.draw.polygon(surf, (30, 70, 40), pts)
    pygame.draw.polygon(surf, (230, 230, 230), pts, 2)
    for i, occupied in enumerate(bases):
        bx, by = pts[i + 1]
        pygame.draw.rect(surf, GOLD if occupied else (110, 115, 125), (bx - 5, by - 5, 10, 10))
        if occupied and armed:
            pygame.draw.rect(surf, GREEN, (bx - 8, by - 8, 16, 16), 2)


def draw_bat_ball(surf, x, y, radius):
    pygame.draw.ellipse(surf, (50, 100, 40), (x - radius, max(y, 200) + radius + 2 - radius * 0.4, radius * 2, radius * 0.8))
    pygame.draw.circle(surf, WHITE, (x, y), radius)
    pygame.draw.circle(surf, (204, 51, 51), (x, y), radius, 1)


def smooth(u):
    u = clamp(u, 0, 1)
    return u * u * (3 - 2 * u)


def draw_limb(surf, points, width, color, outline=None):
    """A bent arm or leg: thick line segments with round joints (optionally with a darker edge)."""
    if outline:
        draw_limb(surf, points, width + 4, outline)
    for a, b in zip(points, points[1:]):
        pygame.draw.line(surf, color, a, b, width)
    for pt in points:
        pygame.draw.circle(surf, color, pt, width // 2)


def two_bone(shoulder, hand, l1, l2, left):
    """Where the elbow goes so an arm with two bones of length l1 / l2 reaches from the shoulder to the hand (bent down and out)."""
    dx, dy = hand[0] - shoulder[0], hand[1] - shoulder[1]
    raw = math.hypot(dx, dy) or 1.0
    d = clamp(raw, 10, l1 + l2 - 1)
    ux, uy = dx / raw, dy / raw
    a = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, l1 * l1 - a * a))
    candidates = [(shoulder[0] + ux * a - uy * h * k, shoulder[1] + uy * a + ux * h * k) for k in (1, -1)]
    return max(candidates, key=lambda e: e[1] * 0.7 + (-e[0] if left else e[0]) * 0.3)


def path(p, keys):
    """Like keyframes(), but for a point: keys is [(p, (x, y)), ...]."""
    return (keyframes(p, [(k, v[0]) for k, v in keys]), keyframes(p, [(k, v[1]) for k, v in keys]))


# The swing, in the order a real hitter does it (all positions are batting-view pixels, angles in degrees):
#   STANCE  hands up by the rear shoulder, bat cocked back over it
#   LOAD    hands drift back and UP behind his head, bat tucks behind the helmet, front foot lifts (the stride)
#   LAUNCH  front foot plants, HIPS fire first, hands drop DOWN and in to the slot while the barrel lags behind them
#   SWING   shoulders unwind, arms extend, the barrel whips around to meet the ball out in front
#   FINISH  the bat wraps all the way around his body and ends lying across his back, hands up by his front shoulder
SWING_HANDS = [(0.0, (306, 274)), (0.30, (310, 292)), (0.65, (332, 305)), (1.0, (352, 308))]      # up/back -> drop -> extend
SWING_YAW = [(0.0, -104), (0.30, -98), (0.62, -35), (0.85, 62), (1.0, 105)]                        # barrel lags, then whips
SWING_ELEV = [(0.0, 80), (0.30, 54), (0.62, 20), (1.0, -18)]                                       # bat drops to level
FINISH_YAW = [(0.0, 105), (0.45, 235), (1.0, 420)]                                                 # around the front, over the shoulder, across the back
FINISH_ELEV = [(0.0, -18), (0.4, 38), (1.0, -22)]


def batter_pose(t, clock, load=0.0, big=False):
    """The batter's pose at swing time t (-1 = not swinging yet).
    load (0..1) is how far he has LOADED (hands back and up, bat tucked behind his head).
    Returns (hands, yaw, elevation, lean). The bat is a 3-D stick: yaw is its direction around the batter
    (0 = toward the camera, 90 deg = across the plate, 180 = toward the pitcher), elevation is how far it is raised.
    big=True (a PERFECT PERFECT homer) is a bigger, higher finish."""
    b = 1.0 if big else 0.0
    if t < 0:
        k = smooth(load)
        w = math.sin(clock * 5) * (1 - k)                                  # the waggle stops once he has loaded
        w2 = math.sin(clock * 5 + 1) * (1 - k)
        hands = (lerp(330, 306, k) + 2 * w, lerp(282, 274, k) + 2 * w2)
        return (hands, math.radians(lerp(-48, -104, k) + 7 * w), math.radians(lerp(66, 80, k) + 3 * w2), -5 * k)
    if t < SWING_TIME:
        u = t / SWING_TIME
        return (path(u, SWING_HANDS), math.radians(keyframes(u, SWING_YAW)), math.radians(keyframes(u, SWING_ELEV)),
                lerp(-5, 8, smooth(u)))
    v = smooth((t - SWING_TIME) / (FOLLOW_TIME + 0.1 * b))                 # then HOLD: v stays at 1 for as long as you like
    hands = path(v, [(0.0, (352, 308)), (0.4, (336, 268)), (1.0, (293 - 3 * b, 252 - 16 * b))])      # up past his face to the front shoulder
    return (hands, math.radians(keyframes(v, FINISH_YAW)), math.radians(keyframes(v, FINISH_ELEV) + 14 * b * v), lerp(8, 12 + 4 * b, v))


def batter_body(t, load=0.0):
    """How the body is turned. Returns (turn, hip, stride, pivot, behind):
    turn   shoulders: 0 = side-on to the pitcher, 1 = chest square to the pitcher (back to the camera)
    hip    hips: they open BEFORE the shoulders (that is where a swing's power comes from)
    stride 0 = front foot back, 0.5 = lifted in the stride, 1 = planted
    pivot  how far the back foot has pivoted up onto its toes
    behind 0..1: how much his arms are on the far side of his body (hidden by his torso and head)"""
    if t < 0:
        k = smooth(load)
        return (lerp(0.12, 0.0, k), lerp(0.10, 0.0, k), 0.55 * k, 0.0, 0.0)
    if t < SWING_TIME:
        u = t / SWING_TIME
        hip = lerp(0.0, 0.9, smooth(u / 0.72))
        turn = lerp(0.0, 0.74, smooth((u - 0.12) / 0.88))
        return (turn, hip, lerp(0.55, 1.0, smooth(u / 0.35)), smooth(u), smooth((turn - 0.35) / 0.3))
    v = smooth((t - SWING_TIME) / FOLLOW_TIME)
    return (lerp(0.74, 1.0, v), lerp(0.9, 1.0, v), 1.0, lerp(1.0, 1.4, v), 1.0)


def bat_tip(hands, yaw, elev, length=BAT_DRAW_LENGTH):
    """Screen position of the bat's tip, and bz (> 0 = the bat is on the camera's side of the batter)."""
    bx, by, bz = math.cos(elev) * math.sin(yaw), math.sin(elev), math.cos(elev) * math.cos(yaw)
    return (hands[0] + length * bx, hands[1] - length * by + 0.3 * length * bz), bz


# --- bats: real wooden-bat shape, in the finishes real MLB players use ---------------------------
# body = the wood colour, handle = (two-tone bats only) the handle's colour, tape = grip tape, knob = the knob,
# cap = the end cap, label = the maker's band on the barrel, shine = the highlight stripe.
BAT_STYLES = [
    dict(name="Natural",    body=(222, 184, 130), handle=None,          tape=(34, 34, 38),    knob=(46, 36, 30),    cap=(150, 112, 70),  label=(120, 40, 36),   shine=(250, 230, 190)),
    dict(name="Blonde",     body=(240, 216, 166), handle=None,          tape=(30, 30, 34),    knob=(60, 50, 40),    cap=(176, 144, 96),  label=(30, 30, 34),    shine=(255, 246, 216)),
    dict(name="Black",      body=(32, 32, 36),    handle=None,          tape=(205, 205, 212), knob=(205, 205, 212), cap=(70, 70, 78),    label=(214, 176, 70),  shine=(110, 110, 124)),
    dict(name="Cherry",     body=(104, 50, 30),   handle=None,          tape=(30, 30, 34),    knob=(30, 30, 34),    cap=(64, 30, 18),    label=(220, 190, 120), shine=(170, 100, 70)),
    dict(name="Red",        body=(168, 36, 36),   handle=None,          tape=(30, 30, 34),    knob=(30, 30, 34),    cap=(110, 20, 22),   label=(240, 240, 240), shine=(230, 110, 100)),
    dict(name="Two-Tone",   body=(32, 32, 36),    handle=(222, 184, 130), tape=(34, 34, 38),  knob=(34, 34, 38),    cap=(70, 70, 78),    label=(214, 176, 70),  shine=(110, 110, 124)),
    dict(name="Driftwood",  body=(150, 140, 128), handle=None,          tape=(34, 34, 38),    knob=(60, 56, 52),    cap=(104, 96, 88),   label=(40, 40, 44),    shine=(200, 192, 180)),
    dict(name="Navy",       body=(28, 44, 96),    handle=None,          tape=(235, 235, 240), knob=(235, 235, 240), cap=(18, 28, 66),    label=(214, 176, 70),  shine=(100, 124, 190)),
]
CURRENT_BAT = BAT_STYLES[0]      # the bat the current batter is using (a new batter picks a new one)


def pick_bat_style():
    """A new batter steps in with a randomly chosen bat."""
    global CURRENT_BAT
    CURRENT_BAT = random.choice(BAT_STYLES)


def _smooth(u):
    u = clamp(u, 0.0, 1.0)
    return u * u * (3 - 2 * u)


def bat_half_width(t):
    """Half-width of a bat (0..1 of its barrel radius) at position t along it: t=0 knob end, t=1 end cap.
    A flared knob, a thin handle, a long smooth taper into the barrel, and a rounded end cap."""
    if t < 0.04:
        return 0.62 * math.sqrt(clamp(t / 0.012, 0, 1))
    if t < 0.075:
        return lerp(0.62, 0.30, _smooth((t - 0.04) / 0.035))
    if t < 0.34:
        return 0.30
    if t < 0.74:
        return lerp(0.30, 1.0, _smooth((t - 0.34) / 0.40))
    if t < 0.965:
        return 1.0
    return math.sqrt(max(0.0, 1 - ((t - 0.965) / 0.035) ** 2))


def draw_real_bat(surf, a, b, width, style=None, t0=0.0, t1=1.0, jag0=False, jag1=False):
    """Draw a baseball bat whose knob is at a and whose end cap is at b. `width` = the barrel's thickness in pixels.
    t0..t1 draws only part of the bat (used for the broken pieces); jag0 / jag1 give that cut end a splintered edge."""
    style = style or CURRENT_BAT
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 2:
        return
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux
    half = width / 2

    def band(ta, tb, jag_a=False, jag_b=False):
        ta, tb = max(ta, t0), min(tb, t1)
        if tb - ta < 0.004:
            return None
        n = max(3, int((tb - ta) / 0.012))
        ts = [lerp(ta, tb, i / n) for i in range(n + 1)]
        left = [(a[0] + ux * length * t + nx * half * bat_half_width(t), a[1] + uy * length * t + ny * half * bat_half_width(t)) for t in ts]
        right = [(a[0] + ux * length * t - nx * half * bat_half_width(t), a[1] + uy * length * t - ny * half * bat_half_width(t)) for t in ts]
        pts = left + right[::-1]
        if jag_a or jag_b:                                           # a splintered, zig-zag break
            def zigzag(p, q, sign):
                return [(lerp(p[0], q[0], k / 6) + ux * sign * length * 0.03 * (k % 2), lerp(p[1], q[1], k / 6) + uy * sign * length * 0.03 * (k % 2))
                        for k in range(7)]
            if jag_a:
                pts = zigzag(right[0], left[0], 1) + left[1:] + right[::-1][:-1]
            if jag_b:
                pts = left[:-1] + zigzag(left[-1], right[-1], -1) + right[::-1][1:]
        return pts

    handle_col = style["handle"] or style["body"]
    tape = style["tape"]
    dark = tuple(int(c * 0.55) for c in style["body"])
    cut_a = 0.02 if jag0 else 0.0                                    # keep trim inside the broken edge
    cut_b = 0.02 if jag1 else 0.0
    if style["handle"]:                                              # two-tone: handle colour up to the middle of the taper, barrel colour after
        parts = ((0.0, 0.50, handle_col, jag0, False), (0.50, 1.0, style["body"], False, jag1))
    else:
        parts = ((0.0, 1.0, style["body"], jag0, jag1),)
    for ta, tb, color, ja, jb in parts:
        pts = band(ta, tb, ja and ta <= t0 + 1e-6, jb and tb >= t1 - 1e-6)
        if pts:
            pygame.draw.polygon(surf, color, pts)
            if width >= 7:
                pygame.draw.polygon(surf, dark, pts, 1)
    for ta, tb, color in ((0.0, 0.04, style["knob"]), (0.085, 0.31, tape), (0.52, 0.575, style["label"]), (0.925, 0.965, style["cap"])):
        pts = band(max(ta, t0 + cut_a), min(tb, t1 - cut_b))
        if pts:
            pygame.draw.polygon(surf, color, pts)
    if width >= 8:                                                   # the shine along one side of the barrel
        lo, hi = max(0.42, t0 + cut_a), min(0.93, t1 - cut_b)
        if hi - lo > 0.03:
            p1 = (a[0] + ux * length * lo + nx * half * 0.45 * bat_half_width(lo), a[1] + uy * length * lo + ny * half * 0.45 * bat_half_width(lo))
            p2 = (a[0] + ux * length * hi + nx * half * 0.45 * bat_half_width(hi), a[1] + uy * length * hi + ny * half * 0.45 * bat_half_width(hi))
            pygame.draw.line(surf, style["shine"], p1, p2, max(1, int(width * 0.13)))


def draw_bat_stick(surf, hands, tip, bz):
    scale = 1 + 0.12 * bz
    draw_real_bat(surf, hands, tip, 11 * scale)                                              # a real bat shape


def draw_batter(surf, swing_clock, cap, skin=SKIN_DEFAULT, clock=0.0, load=0.0, settle=1.0, big=False):
    """The batter seen from behind. His hips open first, then his shoulders; his arms and the bat go BEHIND his body
    (hidden by his torso and head) during the load and again at the end of the follow-through, and swing out in front of
    him through the hitting zone, with the barrel trailing his hands until the last moment."""
    hands, yaw, elev, lean = batter_pose(swing_clock, clock, load, big)
    turn, hip, stride, pivot, behind = batter_body(swing_clock, load)
    if swing_clock < 0 and settle < 1.0:                                  # the next pitch: ease from the held finish back to the stance
        h0, y0, e0, l0 = batter_pose(1e9, clock, 0.0, big)
        k = smooth(settle)
        if yaw < y0 - math.pi:
            yaw += 2 * math.pi
        hands = (lerp(h0[0], hands[0], k), lerp(h0[1], hands[1], k))
        yaw, elev, lean = lerp(y0, yaw, k), lerp(e0, elev, k), lerp(l0, lean, k)
        b0 = batter_body(1e9, 0.0)
        turn, hip, stride, pivot, behind = (lerp(b0[i], v, k) for i, v in enumerate((turn, hip, stride, pivot, behind)))
    tip, bz = bat_tip(hands, yaw, elev)
    pants, edge, jersey = (236, 236, 240), (150, 152, 165), (246, 246, 246)
    cx = 315 + lean                                                       # centre of his body
    sw, hw = lerp(15, 46, turn), lerp(22, 34, hip)                        # shoulder / hip width: they spread as he opens up
    sh_f, sh_r = (cx - sw / 2, 274), (cx + sw / 2, 274)                   # front (far) shoulder, rear (near) shoulder

    if 0 < swing_clock < SWING_TIME + FOLLOW_TIME * 0.5:                  # a white swoosh behind the bat
        trail = []
        for k in range(8):
            tk = swing_clock - k * 0.012
            if tk < 0:
                break
            h, yw, el, _ = batter_pose(tk, clock, 1.0, big)
            tp, _ = bat_tip(h, yw, el)
            trail.append(((lerp(h[0], tp[0], 0.5), lerp(h[1], tp[1], 0.5)), tp))
        if len(trail) > 1:
            overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            for k in range(len(trail) - 1):
                (m0, t0), (m1, t1) = trail[k], trail[k + 1]
                pygame.draw.polygon(overlay, (255, 255, 255, max(0, 95 - k * 12)), [m0, t0, t1, m1])
            surf.blit(overlay, (0, 0))

    def draw_arm(shoulder, left):
        elbow = two_bone(shoulder, hands, 32, 32, left)
        draw_limb(surf, [shoulder, elbow], 11, jersey, edge)                                   # sleeve
        draw_limb(surf, [elbow, hands], 9, skin)                                               # forearm

    def draw_hands():
        pygame.draw.circle(surf, cap, hands, 6)                                                # batting gloves
        pygame.draw.circle(surf, BLACK, hands, 6, 1)

    arms_behind = behind > 0.5                                            # arms on the far side of his body: drawn BEFORE the torso
    if bz < 0:
        draw_bat_stick(surf, hands, tip, bz)                              # the bat is on the far side: behind the body
    if arms_behind:
        draw_arm(sh_f, True)
        draw_arm(sh_r, False)
        draw_hands()
    else:
        draw_arm(sh_f, True)                                              # the front arm is always the far one: behind his chest
    # legs: the back foot pivots up onto its toes, the front foot strides forward (lifting) and plants
    lift = 7 * max(0.0, math.sin(math.pi * clamp(stride, 0, 1)))
    rear = [(cx - hw * 0.5, 334), (lerp(290, 304, hip), 362), (lerp(290, 299, pivot / 1.4 if pivot > 1 else pivot), 386 - 5 * min(pivot, 1.4))]
    front = [(cx + hw * 0.5, 334), (lerp(346, 340, hip), 362 - lift * 0.4), (lerp(340, 348, smooth(stride)), 386 - lift)]
    for leg in (rear, front):
        draw_limb(surf, leg, 17, pants, edge)
        pygame.draw.ellipse(surf, (40, 40, 46), (leg[-1][0] - 10, leg[-1][1] - 3, 22, 9))      # shoes
    torso = [(sh_f[0] - 5, 270), (sh_r[0] + 5, 270), (cx + hw / 2, 342), (cx - hw / 2, 342)]
    pygame.draw.polygon(surf, jersey, torso)
    pygame.draw.polygon(surf, edge, torso, 2)
    for shoulder in (sh_f, sh_r):
        pygame.draw.circle(surf, jersey, shoulder, 11)
    pygame.draw.line(surf, cap, (cx - hw / 2 + 2, 339), (cx + hw / 2 - 2, 339), 5)             # belt in the team colour
    pygame.draw.rect(surf, skin, (cx - 6, 257, 12, 13))                                        # neck
    pygame.draw.circle(surf, skin, (cx, 247), 19)                                              # head
    pygame.draw.circle(surf, cap, (cx, 243), 21, draw_top_left=True, draw_top_right=True)      # helmet
    flap_x = cx - 27 if turn > 0.5 else cx + 19                                                # ear flap on the pitcher side
    pygame.draw.rect(surf, cap, (flap_x, 243, 8, 14), border_radius=3)
    if not arms_behind:
        draw_arm(sh_r, False)                                             # the rear arm is the near one: in front of his chest
    if bz >= 0:
        draw_bat_stick(surf, hands, tip, bz)                              # the bat is on the camera's side: over his shoulder / arm
    if not arms_behind:
        draw_hands()


def keyframes(p, keys):
    """Piecewise value over time: keys is [(p, value), ...] in order. Eases a little inside each segment."""
    if p <= keys[0][0]:
        return keys[0][1]
    for (p0, v0), (p1, v1) in zip(keys, keys[1:]):
        if p <= p1:
            u = (p - p0) / (p1 - p0)
            return lerp(v0, v1, lerp(u, smooth(u), 0.35))
    return keys[-1][1]


# the throwing arm (angles in radians inside the arm's swing plane, measured from "straight ahead", growing clockwise):
#   1.6 = hanging down   3.1 = pointing straight back   4.7 = straight up   5.5 = forward and up (release)   7.0 = forward and down
# "lag" is how far the forearm trails behind the upper arm (it snaps to 0 as the arm whips through)
PITCH_ARM_ANGLE = [(0.0, 1.6), (0.30, 2.7), (0.55, 3.5), (0.78, 4.5), (1.0, 5.5), (1.3, 7.0)]
PITCH_ARM_LAG = [(0.0, 1.3), (0.30, 0.3), (0.55, 0.5), (0.78, 1.3), (1.0, 0.0), (1.3, -0.1)]
# how far each half of his body has turned, in degrees: 0 = facing third base (side-on to the plate), 90 = facing home
PITCH_HIP_TURN = [(0.0, 0), (0.45, 0), (0.8, 35), (1.0, 75), (1.3, 90)]
PITCH_SHOULDER_TURN = [(0.0, 0), (0.5, 0), (0.78, 20), (1.0, 90), (1.3, 100)]
# He is drawn in 3-D and projected: x is across the screen (toward first base), z is toward the camera (toward home plate), y is up.


def _add(a, *terms):
    """a + sum(k * v for k, v in terms)  (3-D points)"""
    return (a[0] + sum(k * v[0] for k, v in terms), a[1] + sum(k * v[1] for k, v in terms), a[2] + sum(k * v[2] for k, v in terms))


def _toward_3b(turn):
    """Horizontal 'forward' direction of a body turned by `turn` radians: 0 = toward third base, pi/2 = toward home plate."""
    return (-math.cos(turn), 0.0, math.sin(turn))


def _right_of(turn):
    """His right-hand side for that turn (a right-hander: far side from the camera when he faces third base)."""
    return (-math.sin(turn), 0.0, -math.cos(turn))


def leg_knee(hip, foot, l1, l2, toward):
    """3-D knee position for a leg of two bones spanning hip -> foot; the knee bends toward the direction `toward`."""
    v = (foot[0] - hip[0], foot[1] - hip[1], foot[2] - hip[2])
    full = max(0.001, math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2))
    dist = clamp(full, 0.001, l1 + l2 - 0.01)
    u = (v[0] / full, v[1] / full, v[2] / full)
    dot = toward[0] * u[0] + toward[1] * u[1] + toward[2] * u[2]
    perp = (toward[0] - dot * u[0], toward[1] - dot * u[1], toward[2] - dot * u[2])
    n = max(0.001, math.sqrt(perp[0] ** 2 + perp[1] ** 2 + perp[2] ** 2))
    h = math.sqrt(max(0.0, l1 * l1 - (dist / 2) ** 2))
    return (hip[0] + u[0] * dist / 2 + perp[0] / n * h, hip[1] + u[1] * dist / 2 + perp[1] / n * h,
            hip[2] + u[2] * dist / 2 + perp[2] / n * h)


def pitcher_pose(progress):
    """All the joints of the pitcher (3-D), plus where each lands on the screen.
    progress: 0 = standing, hands together, facing third base ... 0.4 = knee at its highest, arm swinging back ...
              0.8 = front foot planted, arm cocked, hips opening ... 1 = release (facing home) ... 1.3 = follow-through."""
    p = clamp(progress, 0, 1.3)
    cx = 386.0
    kick = smooth(p / 0.4)
    stride = smooth((p - 0.4) / 0.4)
    fin = smooth((p - 0.45) / 0.55)                                       # how far he has uncoiled toward the plate
    follow = clamp((p - 1.0) / 0.3, 0, 1)
    hip_turn = math.radians(keyframes(p, PITCH_HIP_TURN))
    sh_turn = math.radians(keyframes(p, PITCH_SHOULDER_TURN))
    Fl, Rl, Fu, Ru = _toward_3b(hip_turn), _right_of(hip_turn), _toward_3b(sh_turn), _right_of(sh_turn)
    up, down = (0.0, 1.0, 0.0), (0.0, -1.0, 0.0)
    tilt = lerp(lerp(0.0, -0.18, kick), 0.42, fin) + 0.12 * follow         # rocks back on the kick, then drives toward the plate
    hip_c = (cx - 2 * stride, 18 - 5 * stride, 6 * stride + 3 * follow)
    hip_r, hip_l = _add(hip_c, (2.5, Rl)), _add(hip_c, (-2.5, Rl))
    lean = (math.sin(tilt), math.cos(tilt))
    sh_c = _add(hip_c, (26 * lean[0], Fu), (26 * lean[1], up))
    sh_r, sh_l = _add(sh_c, (5.5, Ru)), _add(sh_c, (-5.5, Ru))
    head = _add(sh_c, (9 * lean[0] + 1.5, Fu), (9 * lean[1], up))
    # lead leg (his left): the knee comes up toward third base, then the leg reaches out toward HOME and plants
    thigh = lerp(0.15, 2.15, kick) if p < 0.4 else lerp(2.15, 0.8, stride)
    shin = lerp(0.0, -0.45, kick) if p < 0.4 else lerp(-0.45, 0.7, stride)
    reach_dir = _toward_3b(math.radians(85) * stride)
    knee_l = _add(hip_l, (9 * math.sin(thigh), reach_dir), (9 * math.cos(thigh), down))
    foot_l = _add(knee_l, (9 * math.sin(shin), reach_dir), (9 * math.cos(shin), down))
    # back leg (his right): stays on the rubber, and the heel comes up as he finishes
    foot_r = (cx - 1 - 3 * follow, 7 * follow, -2.5)
    knee_r = leg_knee(hip_r, foot_r, 9, 9, Fl)
    # throwing arm (his right): swings back behind him, rises, cocks, then whips around toward the plate
    a_u = keyframes(p, PITCH_ARM_ANGLE)
    a_f = a_u - keyframes(p, PITCH_ARM_LAG)
    elbow = _add(sh_r, (9 * math.cos(a_u), Fu), (-9 * math.sin(a_u), up))
    hand = _add(elbow, (9 * math.cos(a_f), Fu), (-9 * math.sin(a_f), up))
    # glove arm (his left): at the chest, reaches out for balance, then tucks in
    reach = kick - 0.6 * smooth((p - 0.6) / 0.3)
    glove = _add(sh_l, (6 + 6 * reach, Fu), (-(9 - 6 * reach), up))
    glove_elbow = ((sh_l[0] + glove[0]) / 2, (sh_l[1] + glove[1]) / 2 - 3, (sh_l[2] + glove[2]) / 2)
    pose = dict(hip_c=hip_c, hip_r=hip_r, hip_l=hip_l, sh_c=sh_c, sh_r=sh_r, sh_l=sh_l, head=head, knee_l=knee_l, foot_l=foot_l,
                knee_r=knee_r, foot_r=foot_r, elbow=elbow, hand=hand, glove=glove, glove_elbow=glove_elbow,
                face=Fu, toe_l=reach_dir, toe_r=Fl)
    pose["screen_hand"] = project_pitcher(hand)
    return pose


def project_pitcher(pt):
    """3-D point -> screen position. Things nearer the camera (toward home) sit lower and a touch bigger."""
    x, y, z = pt
    s = 1 + 0.004 * z
    return (386.0 + (x - 386.0) * s, 209.0 - y * s + 0.35 * z)


def draw_bat_pitcher(surf, windup_progress, skin=SKIN_DEFAULT):
    """Draws the pitcher and returns where his throwing hand is.
    He starts side-on to the plate facing third base, kicks his knee toward third, strides toward home and turns to face the
    plate as the arm comes through. windup_progress: 0 = standing ... 1 = release ... 1.3 = follow-through."""
    pose = pitcher_pose(windup_progress)
    body, shoe = FIELD_BODY, (230, 230, 235)
    P = project_pitcher
    pygame.draw.ellipse(surf, (150, 105, 66), (386 - 20, 205, 40, 8))                              # a darker patch of mound under him
    parts = []                                                                                     # (depth, draw function): far things first

    def limb(depth, points, widths, hand_color=None, ball=None):
        def draw():
            pts = [P(q) for q in points]
            for a, b, w in zip(pts, pts[1:], widths):
                pygame.draw.line(surf, body, a, b, w)
            for q in pts[1:-1]:
                pygame.draw.circle(surf, body, q, 3)
            if hand_color:
                pygame.draw.circle(surf, hand_color, pts[-1], ball)
        parts.append((depth, draw))

    def foot(depth, ankle, toe_dir):
        def draw():
            a = P(ankle)
            b = P(_add(ankle, (5, toe_dir)))
            pygame.draw.line(surf, shoe, a, b, 3)
        parts.append((depth, draw))

    for hip, knee, ank, toe in (("hip_r", "knee_r", "foot_r", "toe_r"), ("hip_l", "knee_l", "foot_l", "toe_l")):
        pts = (pose[hip], pose[knee], pose[ank])
        depth = sum(q[2] for q in pts) / 3
        limb(depth, pts, (6, 5))
        foot(depth + 0.1, pose[ank], pose[toe])
    # torso
    def draw_torso():
        a, b = P(pose["hip_c"]), P(pose["sh_c"])
        pygame.draw.line(surf, body, a, b, 12)
        pygame.draw.circle(surf, body, a, 6)
        pygame.draw.circle(surf, body, b, 6)
    parts.append(((pose["hip_c"][2] + pose["sh_c"][2]) / 2, draw_torso))
    # head and cap (the brim points where he is facing)
    def draw_head():
        h = P(pose["head"])
        brim = P(_add(pose["head"], (9, pose["face"])))
        front = pose["face"][2] > 0.5                                    # facing the camera: show the whole face, brim toward us
        pygame.draw.circle(surf, skin, h, 6)
        pygame.draw.circle(surf, FIELD_CAP, (h[0], h[1] - 1.5), 6.5, draw_top_left=True, draw_top_right=True)
        if front:                                                        # facing us: the brim is a bar across his forehead
            pygame.draw.line(surf, FIELD_CAP, (h[0] - 6, h[1] - 1), (h[0] + 6, h[1] - 1), 2)
        else:                                                            # side-on: the brim sticks out the way he is facing
            pygame.draw.line(surf, FIELD_CAP, (h[0] + (brim[0] - h[0]) * 0.35, h[1] - 1), (brim[0], brim[1] - 2), 2)
    parts.append((pose["head"][2] + 0.5, draw_head))
    # arms
    ra = (pose["sh_r"], pose["elbow"], pose["hand"])
    la = (pose["sh_l"], pose["glove_elbow"], pose["glove"])
    limb(sum(q[2] for q in ra) / 3 + 0.2, ra, (5, 4), skin, 2.5)
    limb(sum(q[2] for q in la) / 3 + 0.2, la, (4, 4), (120, 75, 40), 4)
    for _, draw in sorted(parts, key=lambda item: item[0]):
        draw()
    return pose["screen_hand"]


def pitch_position(pitch, u):
    """Batting-view position + radius of the pitch. u = 0 at release, 1 at the plate."""
    u = min(u, 1.25)
    if pitch.name == "Changeup" and u < 1:
        u = 1 - (1 - u) ** CHANGEUP_HOT_START             # hot out of the hand, then it slows way down
    x = BAT_RELEASE_POINT[0] + u * 8 + pitch.zone * 16 * min(u, 1)       # inside = toward the batter (left)
    y = 212 + 120 * u ** 1.7
    if pitch.name == "Curveball":
        bend = math.sin(math.pi * min(u, 1))
        y -= 40 * bend
        x -= 40 * bend * (1 - u * 0.3)
    if pitch.name == "Splitter":
        y += 55 * max(0, (u - 0.65) / 0.35) ** 2
    if pitch.name == "Slider":
        x += 38 * min(max(0, (u - 0.35) / 0.65), 1.3) ** 1.6
        y += 22 * max(0, (u - 0.6) / 0.4) ** 2
    return x, y, 2 + 7 * u


def hr_k(distance):
    """0 = a short homer (350 ft), 1 = a long one (450 ft+) in the batting view."""
    return clamp((distance - 350) / 100, 0, 1) if distance else 0.5


def hr_end_y(distance):
    """Where a home run lands in the batting view: short ones barely clear the wall, long ones go up into the top deck."""
    return lerp(105, 22, hr_k(distance))


def hr_position(hit):
    """Batting-view position + radius of a home run ball. Longer homers fly higher, with a bigger arc and a smaller ball at the end."""
    u = min(1, hit.time / hit.flight)
    k = hr_k(hit.distance)
    end_y, peak, end_r = hr_end_y(hit.distance), lerp(20, 80, k), lerp(6.5, 2, k)
    return hit.start_x + hit.sideways * u, hit.start_y - (hit.start_y - end_y) * u - peak * math.sin(math.pi * u), 9 - (9 - end_r) * u


def draw_bat_fielders(surf):
    """Fielders standing around the batting view. Just for looks - the real ones are in the field view."""
    for x, y, s in BAT_FIELDERS:
        pygame.draw.ellipse(surf, (40, 66, 58), (x - 8 * s, y - 18 * s, 16 * s, 36 * s))
        pygame.draw.circle(surf, (40, 66, 58), (x, y - 22 * s), 6 * s)


def make_seam_curve(points=90, k=0.4):
    """3-D points of a baseball seam, lying on a sphere of radius 1."""
    curve = []
    for i in range(points + 1):
        t = 2 * math.pi * i / points
        curve.append(((1 - k) * math.cos(t) + k * math.cos(3 * t),
                      (1 - k) * math.sin(t) - k * math.sin(3 * t),
                      2 * math.sqrt(k * (1 - k)) * math.sin(2 * t)))
    return curve


SEAM_POINTS = make_seam_curve()


def draw_seam_window(surf, game):
    """A magnified ball whose red seams give away the pitch:
         seams rolling UP fast ..... fastball (backspin)
         seams rolling UP slower ... changeup (Hard)
         seams rolling DOWN ........ curveball (topspin)
         tilted / sideways ......... slider (Hard)
         barely spinning ........... splitter"""
    pitch = game.pitch
    if not SHOW_SEAM_WINDOW or not pitch:
        return
    if game.state == "PITCH":
        t = SEAM_PREVIEW_TIME + pitch.time
    elif game.state == "WIND_UP" and game.state_time > WIND_UP_TIME - SEAM_PREVIEW_TIME:
        t = game.state_time - (WIND_UP_TIME - SEAM_PREVIEW_TIME)
    else:
        return
    rate, tilt = SEAM_SPIN[pitch.name]
    cx, cy, radius = 700, 64, 38
    pygame.draw.circle(surf, (20, 24, 30), (cx, cy), radius + 7)
    pygame.draw.circle(surf, (245, 242, 232), (cx, cy), radius)
    spin, cos_t, sin_t = rate * t + 0.6, math.cos(tilt), math.sin(tilt)
    last = None
    for x, y, z in SEAM_POINTS:
        y2 = y * math.cos(spin) - z * math.sin(spin)         # spin the ball about its horizontal axis
        z2 = y * math.sin(spin) + z * math.cos(spin)
        x3, y3 = x * cos_t - y2 * sin_t, x * sin_t + y2 * cos_t     # tilt the spin axis
        if z2 > 0:                                           # only the half facing you is visible
            point = (cx + x3 * radius, cy - y3 * radius)
            if last:
                pygame.draw.line(surf, (200, 40, 40), last, point, 3)
            last = point
        else:
            last = None
    pygame.draw.circle(surf, (120, 120, 120), (cx, cy), radius, 2)
    if SHOW_SEAM_LEGEND:
        for i, name in enumerate(game.diff["pitches"]):
            draw_text(surf, SEAM_LEGEND_TEXT[name], cx, 126 + i * 11, 9, (235, 235, 235), outline=False)


# --- the PERFECT PERFECT home run cutscene (side view) --------------------------
# Everything here is drawn in "world" pixels; the camera offset is subtracted when drawing.

BATTER_FEET = (420, 600)         # world position of the side-view batter's feet (the ground is y=600)
BAT_LENGTH = 190
TORSO_LEN = 74


def track(frames, t):
    """Smoothly interpolate keyframes [(time, value), ...] with a Catmull-Rom spline: it passes through every key but
    never comes to a stop between them, so the motion flows. Values can be numbers or tuples."""
    if t <= frames[0][0]:
        return frames[0][1]
    if t >= frames[-1][0]:
        return frames[-1][1]
    i = 0
    while not frames[i][0] <= t <= frames[i + 1][0]:
        i += 1
    (t0, v0), (t1, v1) = frames[i], frames[i + 1]
    vm = frames[i - 1][1] if i > 0 else v0
    vp = frames[i + 2][1] if i + 2 < len(frames) else v1
    u = (t - t0) / (t1 - t0)

    def spline(a, b, c, d):
        return 0.5 * (2 * b + (-a + c) * u + (2 * a - 5 * b + 4 * c - d) * u * u + (-a + 3 * b - 3 * c + d) * u ** 3)
    if isinstance(v0, tuple):
        return tuple(spline(vm[k], v0[k], v1[k], vp[k]) for k in range(len(v0)))
    return spline(vm, v0, v1, vp)


# The side-view swing, as keyframes (seconds; the bat meets the ball at 0.8):
#   0.0 stance -> 0.3 LOAD (weight back, hands back and up) -> 0.5 cock -> 0.45-0.6 front foot STRIDES forward
#   -> 0.65 barrel drops -> 0.76 WHIP (hips and shoulders open up) -> 0.8 CONTACT -> follow-through wraps the bat
#   around behind him -> 1.25 he HOLDS the finish.
SLUGGER_HIP_X = [(0, 0), (0.3, -14), (0.5, -10), (0.65, 2), (0.8, 16), (1.0, 24), (1.25, 26)]          # hips slide back, then drive forward
SLUGGER_HIP_H = [(0, 96), (0.3, 88), (0.5, 90), (0.65, 92), (0.8, 90), (1.0, 96), (1.25, 100)]          # hip height: sinks into the load, rises through the finish
SLUGGER_LEAN = [(0, 0.12), (0.3, -0.08), (0.5, -0.12), (0.65, 0.02), (0.8, 0.30), (1.0, 0.0), (1.15, -0.28), (1.25, -0.36)]   # torso: coils back, drives forward, arches back
SLUGGER_HANDS = [(0, (16, 16)), (0.3, (-12, -6)), (0.5, (-16, 2)), (0.65, (-4, 18)), (0.7, (8, 24)), (0.76, (36, 26)),
                 (0.8, (56, 22)), (0.86, (50, 10)), (0.95, (34, -14)), (1.05, (14, -34)), (1.15, (-4, -44)), (1.25, (-14, -48))]   # hands relative to the shoulders
SLUGGER_YAW = [(0, 15), (0.3, -5), (0.5, 5), (0.65, 30), (0.72, 75), (0.76, 125), (0.8, 180), (0.86, 225), (0.95, 265),
               (1.05, 305), (1.15, 335), (1.25, 355)]       # bat direction around the batter: 0 = back, 90 = toward the camera, 180 = at the pitcher
SLUGGER_ELEV = [(0, 62), (0.3, 72), (0.5, 58), (0.65, 25), (0.72, 8), (0.76, 0), (0.8, -8), (0.86, -2), (0.95, 12),
                (1.05, 30), (1.15, 48), (1.25, 56)]         # how far the bat is raised (degrees)
SLUGGER_REAR_FOOT = [(0, (-34, 0)), (0.7, (-34, 0)), (0.8, (-32, -1)), (1.0, (-22, -7)), (1.25, (-18, -9))]    # back heel lifts and pivots
SLUGGER_FRONT_FOOT = [(0, (40, 0)), (0.3, (40, 0)), (0.45, (46, -24)), (0.6, (70, -6)), (0.66, (70, 0)), (1.25, (70, 0))]   # the stride


def slugger_pose(t):
    """Every joint of the side-view batter at cutscene time t, in world pixels.
    Before contact the keyframes are stretched to fit SLUGGER_HIT_TIME; after contact they run in real seconds."""
    tt = t * 0.8 / SLUGGER_HIT_TIME if t < SLUGGER_HIT_TIME else 0.8 + (t - SLUGGER_HIT_TIME)
    ox, oy = BATTER_FEET
    hip = (ox + track(SLUGGER_HIP_X, tt), oy - track(SLUGGER_HIP_H, tt))
    lean = track(SLUGGER_LEAN, tt)
    shoulder = (hip[0] + TORSO_LEN * math.sin(lean), hip[1] - TORSO_LEN * math.cos(lean))
    head = (shoulder[0] + 6 + 16 * lean, shoulder[1] - 30)
    offset = track(SLUGGER_HANDS, tt)
    hands = (shoulder[0] + offset[0], shoulder[1] + offset[1])
    yaw, elev = math.radians(track(SLUGGER_YAW, tt)), math.radians(track(SLUGGER_ELEV, tt))
    bx, by, bz = -math.cos(yaw) * math.cos(elev), math.sin(elev), math.sin(yaw) * math.cos(elev)
    tip = (hands[0] + BAT_LENGTH * bx, hands[1] - BAT_LENGTH * by + 0.25 * BAT_LENGTH * bz)
    rear, front = track(SLUGGER_REAR_FOOT, tt), track(SLUGGER_FRONT_FOOT, tt)
    return dict(hip=hip, shoulder=shoulder, head=head, hands=hands, tip=tip, bz=bz, lean=lean,
                rear_foot=(ox + rear[0], oy + min(0, rear[1])), front_foot=(ox + front[0], oy + min(0, front[1])))


CONTACT_POINT = slugger_pose(SLUGGER_HIT_TIME)["tip"]        # where the barrel is at the moment of contact: the ball arrives here


def build_slugger_assets():
    """Pre-draw the scrolling backdrop pieces (sky, skyline, stands, grass) so the cutscene is cheap to draw."""
    w = LOGICAL_W
    sky = pygame.Surface((w, LOGICAL_H))
    for y in range(LOGICAL_H):
        k = clamp(y / 560, 0, 1) ** 1.4
        pygame.draw.line(sky, (int(lerp(25, 255, k)), int(lerp(35, 165, k)), int(lerp(105, 110, k))), (0, y), (w, y))
    pygame.draw.circle(sky, (255, 225, 160), (980, 430), 80)
    skyline = pygame.Surface((w, 220), pygame.SRCALPHA)
    x = 0
    while x < w:
        bw, bh = random.randint(40, 110), random.randint(50, 200)
        pygame.draw.rect(skyline, (70, 55, 100), (x, 220 - bh, bw, bh))
        x += bw + random.randint(0, 12)
    stands = pygame.Surface((w, 260))
    stands.fill((70, 62, 78))
    for _ in range(1800):
        stands.fill(random.choice([(170, 120, 110), (210, 200, 190), (130, 135, 160), (190, 80, 80)]),
                    (random.randint(0, w), random.randint(30, 250), 5, 5))
    pygame.draw.rect(stands, (40, 38, 50), (0, 0, w, 28))
    grass = pygame.Surface((w, 240))
    grass.fill((50, 125, 48))
    for sx in range(0, w, 160):
        pygame.draw.rect(grass, (58, 140, 55), (sx, 0, 80, 240))
    return dict(sky=sky, skyline=skyline, stands=stands, grass=grass)


def slugger_ball_world(t, k=0.5):
    """World position of the ball: the slow-motion pitch, then the rocket after contact."""
    s = t - SLUGGER_HIT_TIME
    if s < 0:
        u = t / SLUGGER_HIT_TIME
        return lerp(1300, CONTACT_POINT[0], u), lerp(CONTACT_POINT[1] - 40, CONTACT_POINT[1], u * u)
    # k = 0 for a 400 ft shot, 1 for 550 ft: longer ones fly faster and higher
    return CONTACT_POINT[0] + lerp(850, 1500, k) * s, CONTACT_POINT[1] - (lerp(430, 720, k) * s - 150 * s * s)


def ik_joint(a, b, l1, l2, toward):
    """The knee / elbow position for a limb with bones l1 and l2 reaching from a to b, bent toward the direction `toward`."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    raw = math.hypot(dx, dy) or 1.0
    d = clamp(raw, 6, l1 + l2 - 1)
    ux, uy = dx / raw, dy / raw
    along = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, l1 * l1 - along * along))
    candidates = [(a[0] + ux * along - uy * h * k, a[1] + uy * along + ux * h * k) for k in (1, -1)]
    return max(candidates, key=lambda e: (e[0] - a[0]) * toward[0] + (e[1] - a[1]) * toward[1])


def draw_taper_bat(surf, hands, tip, bz):
    """A big bat in the cutscene. bz > 0 means it is on the camera's side of the batter (so it looks a bit bigger)."""
    draw_real_bat(surf, hands, tip, 19 * (1 + 0.15 * bz))


def draw_side_batter(surf, cam, t, cap, skin=SKIN_DEFAULT):
    """The slugger in the side-view cutscene, posed from slugger_pose(t): knees and elbows bent, weight shifting back
    in the load, a stride, a whip of the hips and shoulders, and a held follow-through."""
    p = slugger_pose(t)
    to_screen = lambda pt: (pt[0] - cam[0], pt[1] - cam[1])
    hip, shoulder, head, hands, tip = (to_screen(p[k]) for k in ("hip", "shoulder", "head", "hands", "tip"))
    rear_foot, front_foot = to_screen(p["rear_foot"]), to_screen(p["front_foot"])
    bz, lean = p["bz"], p["lean"]
    uniform, shade, edge = (240, 240, 240), (212, 212, 224), (170, 172, 185)

    if SLUGGER_HIT_TIME * 0.65 < t < SLUGGER_HIT_TIME + 0.4:                       # swoosh behind the bat
        trail = []
        for k in range(12):
            q = slugger_pose(t - k * 0.01)
            h, tp = to_screen(q["hands"]), to_screen(q["tip"])
            trail.append(((lerp(h[0], tp[0], 0.45), lerp(h[1], tp[1], 0.45)), tp))
        overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        for k in range(len(trail) - 1):
            (m0, t0), (m1, t1) = trail[k], trail[k + 1]
            pygame.draw.polygon(overlay, (255, 255, 255, max(0, 150 - k * 13)), [m0, t0, t1, m1])
        surf.blit(overlay, (0, 0))

    if bz < 0:
        draw_taper_bat(surf, hands, tip, bz)                                      # bat on the far side: behind his body
    rear_hip, front_hip = (hip[0] - 8, hip[1]), (hip[0] + 8, hip[1])
    for hip_pt, foot, color in ((rear_hip, rear_foot, shade), (front_hip, front_foot, uniform)):
        knee = ik_joint(hip_pt, foot, 58, 58, (1, 0))                              # knees bend toward the pitcher
        draw_limb(surf, [hip_pt, knee, foot], 26, color, edge)
        pygame.draw.ellipse(surf, (40, 40, 46), (foot[0] - 14, foot[1] - 8, 44, 15))   # shoe
    draw_limb(surf, [hip, shoulder], 52, (248, 248, 248), edge)                    # torso
    nx, ny = math.cos(lean), math.sin(lean)
    pygame.draw.line(surf, cap, (hip[0] - nx * 24, hip[1] - ny * 24), (hip[0] + nx * 24, hip[1] + ny * 24), 6)    # belt
    draw_limb(surf, [shoulder, head], 14, skin)                                    # neck
    pygame.draw.circle(surf, skin, head, 25)
    pygame.draw.circle(surf, cap, (head[0], head[1] - 5), 27, draw_top_left=True, draw_top_right=True)         # helmet
    pygame.draw.rect(surf, cap, (head[0], head[1] - 8, 40, 9))                     # brim
    if bz >= 0:
        draw_taper_bat(surf, hands, tip, bz)                                       # bat on the camera's side: in front
    for dx, color, grip in ((-8, shade, (-4, 4)), (6, uniform, (0, 0))):           # far arm, then near arm
        shoulder_pt = (shoulder[0] + dx, shoulder[1] + 2)
        hand_pt = (hands[0] + grip[0], hands[1] + grip[1])
        elbow = ik_joint(shoulder_pt, hand_pt, 38, 38, (0.3, 1))                   # elbows hang down and out
        draw_limb(surf, [shoulder_pt, elbow], 15, color, edge)
        draw_limb(surf, [elbow, hand_pt], 12, skin)
    pygame.draw.circle(surf, cap, hands, 9)                                        # batting gloves
    pygame.draw.circle(surf, BLACK, hands, 9, 1)


def draw_explosion(surf, cx, cy, s):
    """Starburst + shockwave at the moment of contact. s = seconds since contact."""
    if not 0 <= s < 0.5:
        return
    fade = 1 - s / 0.5
    outer = 60 + 420 * s ** 0.6
    points = []
    for i in range(24):
        r = outer if i % 2 == 0 else outer * 0.45
        a = i * math.pi / 12 + 0.2
        points.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    pygame.draw.polygon(surf, (255, 120, 30), points)
    pygame.draw.polygon(surf, (255, 235, 90), [(cx + (x - cx) * 0.62, cy + (y - cy) * 0.62) for x, y in points])
    pygame.draw.circle(surf, WHITE, (cx, cy), int(40 * fade) + 4)
    pygame.draw.circle(surf, WHITE, (cx, cy), int(60 + 620 * s), max(1, int(10 * fade)))


# --- rare animations (these only draw; the Game decides when they happen) --------

FIELD_BODY, FIELD_CAP = (40, 60, 120), (30, 40, 90)     # the CPU fielders' colours (same as draw_person's defaults)


def draw_loose_ball(surf, x, y):
    pygame.draw.circle(surf, WHITE, (x, y), 6)
    pygame.draw.circle(surf, (204, 51, 51), (x, y), 6, 1)


def dive_glove(x, y, scale, direction):
    """Where the glove is once a diving fielder is stretched out on the ground."""
    return x + 32 * direction * scale, y - 13 * scale


def draw_dive(surf, x, y, scale, body, cap, t, direction=1, skin=SKIN_DEFAULT, shadow_color=(35, 85, 35), dust_color=(214, 176, 126)):
    """A fielder flying through the air and sliding on his belly. t = seconds since the dive began."""
    s, d = scale, direction
    p = clamp(t / DIVE_TIME, 0, 1)
    lift = math.sin(math.pi * p) * 18 * s                          # up off the ground, then back down
    cy = y - 8 * s - lift
    pygame.draw.ellipse(surf, shadow_color, (x - 16 * s, y - 3 * s, 32 * s, 8 * s))                       # shadow
    pygame.draw.line(surf, body, (x - 12 * d * s, cy), (x - 30 * d * s, cy + 3 * s), max(1, int(6 * s)))  # legs
    pygame.draw.ellipse(surf, body, (x - 16 * s, cy - 6 * s, 32 * s, 12 * s))                             # torso
    pygame.draw.line(surf, body, (x + 10 * d * s, cy - 2 * s), (x + 30 * d * s, cy - 5 * s), max(1, int(4 * s)))   # arm
    pygame.draw.circle(surf, skin, (x + 19 * d * s, cy - 3 * s), 5 * s)                        # head
    pygame.draw.circle(surf, cap, (x + 19 * d * s, cy - 5 * s), 5.5 * s, draw_top_left=True, draw_top_right=True)
    pygame.draw.circle(surf, (120, 75, 40), (x + 32 * d * s, cy - 5 * s), 5 * s)                          # glove
    age = t - DIVE_TIME * 0.5                                      # a cloud of dust kicks up as he lands
    if age > 0:
        for i in range(7):
            a = i / 6
            r = (3 + 7 * a) * s * max(0.0, 1 - age / 0.9)
            if r >= 1:
                pygame.draw.circle(surf, dust_color, (x - d * s * age * (30 + 60 * a), y - 2 * s - age * 40 * a * s), r)


def leap_lift(t):
    return LEAP_HEIGHT * math.sin(math.pi * clamp(t / LEAP_TIME, 0, 1))


def leap_glove(x, y, scale, t):
    """Where the glove is during a leaping catch (t = seconds since the jump began)."""
    return x + 3 * scale, y - leap_lift(t) - 47 * scale


def draw_leap(surf, x, y, scale, body, cap, t, skin=SKIN_DEFAULT, shadow_color=(35, 85, 35)):
    """A fielder jumping with his glove stretched high. The shadow stays on the ground."""
    s = scale
    lift = leap_lift(t)
    shrink = 1 - 0.25 * lift / LEAP_HEIGHT
    pygame.draw.ellipse(surf, shadow_color, (x - 11 * s * shrink, y - 3 * s, 22 * s * shrink, 8 * s * shrink))
    draw_person(surf, x, y - lift, s, body, cap, shadow=False, skin=skin)
    gx, gy = leap_glove(x, y, s, t)
    pygame.draw.line(surf, body, (x + 3 * s, y - lift - 22 * s), (gx, gy + 5 * s), max(1, int(4 * s)))   # raised arm
    pygame.draw.circle(surf, (120, 75, 40), (gx, gy), 5 * s)


def draw_bat_stub(surf, x, y):
    """The handle of a snapped bat, still in the batter's hands (a jagged break at the top)."""
    start = (x + 5, y - 17)
    ux, uy = unit(10, -19)
    draw_real_bat(surf, start, (start[0] + ux * 50, start[1] + uy * 50), 8, t1=0.45, jag1=True)


def draw_broken_bat(surf, x, y, t, direction):
    """The barrel of the bat spinning away plus a spray of splinters. t = seconds since contact."""
    if not 0 <= t < BROKEN_BAT_TIME:
        return
    ux, uy = direction
    cy = y - 30
    if t < 0.25:                                                   # impact ring
        pygame.draw.circle(surf, WHITE, (x, cy), int(10 + 70 * t / 0.25), 3)
    k = clamp(t / BROKEN_BAT_TIME, 0, 1)
    dist = 240 * (1 - (1 - k) ** 2)
    ground_x, ground_y = x + ux * dist, y + uy * dist * 0.8
    bx, by = ground_x, cy + uy * dist * 0.8 - 50 * math.sin(math.pi * k)
    angle = t * 15
    dx, dy = math.cos(angle) * 34, math.sin(angle) * 34
    pygame.draw.ellipse(surf, (35, 85, 35), (ground_x - 20, ground_y - 5, 40, 10))
    full, mid_t = 113, 0.72                                           # the barrel is the outer part of a 113 px bat, spinning
    ux2, uy2 = math.cos(angle), math.sin(angle)
    start = (bx - ux2 * full * mid_t, by - uy2 * full * mid_t)
    draw_real_bat(surf, start, (start[0] + ux2 * full, start[1] + uy2 * full), 11, t0=0.45, jag0=True)
    if t < 1.0:
        for i in range(10):                                        # wood splinters
            a = i * 0.63 + 0.3
            speed = 80 + 18 * (i % 4)
            px = x + math.cos(a) * speed * t
            py = cy + math.sin(a) * speed * t * 0.7 + 160 * t * t
            la = a + t * 9
            pygame.draw.line(surf, tuple(min(255, c + 40) for c in CURRENT_BAT['handle'] or CURRENT_BAT['body']), (px, py), (px + 9 * math.cos(la), py + 9 * math.sin(la)), 3)


def draw_fan(surf, gx, gy, p, clock, has_ball=False, k=FAN_SCALE):
    """A (small) fan in the stands popping up to catch a home run. (gx, gy) is where his glove ends up.
       p = 0..1 how far he has risen; clock = running time (he waves once he has the ball); k = size."""
    rise = (1 - p) * 34 * k
    feet = gy + 52 * k + rise
    thick = max(1, int(4 * k))
    pygame.draw.rect(surf, (52, 56, 66), (gx - 20 * k, feet - 8 * k, 40 * k, 14 * k), border_radius=2)   # seat back
    pygame.draw.ellipse(surf, (200, 60, 60), (gx - 8 * k, feet - 40 * k, 16 * k, 40 * k))                # body
    pygame.draw.circle(surf, (224, 190, 150), (gx, feet - 46 * k), 7 * k)                                # head
    pygame.draw.circle(surf, (40, 60, 120), (gx, feet - 48 * k), 7.5 * k, draw_top_left=True, draw_top_right=True)   # cap
    wave = math.sin(clock * 12) * 6 * k if p >= 1 else 0
    pygame.draw.line(surf, (200, 60, 60), (gx - 6 * k, feet - 34 * k), (gx - 16 * k + wave * 0.3, feet - 52 * k + wave), thick)  # free arm
    pygame.draw.line(surf, (200, 60, 60), (gx + 4 * k, feet - 34 * k), (gx, gy + rise), thick)           # glove arm
    pygame.draw.circle(surf, (120, 75, 40), (gx, gy + rise), max(2, 6 * k))
    if has_ball:
        pygame.draw.circle(surf, WHITE, (gx, gy + rise - 1), max(1, 3 * k))


# --- start-screen drawing ------------------------------------------------------

def build_title(text, max_width=1100, size=130):
    """Pre-render the fancy title: arched, slanted letters with a gradient fill, white outline and a deep 3-D shadow.
    Returns the finished picture plus a silhouette mask (used for the moving shine)."""
    while True:
        font = get_title_font(size)
        spacing = size * 0.04
        widths = [font.size(ch)[0] for ch in text]
        total = sum(widths) + spacing * (len(text) - 1)
        if total <= max_width or size <= 40:
            break
        size -= 6
    pad = 30
    w, h = int(total) + pad * 2, int(font.get_height() + size * 0.2) + pad * 2
    mask = pygame.Surface((w, h), pygame.SRCALPHA)                       # white letters, no colour
    x, mid = pad, pad + total / 2
    for ch, cw in zip(text, widths):
        cx = x + cw / 2
        u = clamp((cx - mid) / (total / 2), -1, 1)                       # -1 at the far left letter, +1 at the far right
        if ch != " ":
            glyph = pygame.transform.rotate(font.render(ch, True, WHITE), -u * 5)      # letters lean along an arch
            cy = pad + font.get_height() / 2 + size * 0.12 * u * u
            mask.blit(glyph, glyph.get_rect(center=(cx, cy)))
        x += cw + spacing
    top, bottom = pad, pad + font.get_height()
    gradient = pygame.Surface((w, h), pygame.SRCALPHA)                   # yellow at the top, orange at the bottom
    for y in range(h):
        t = clamp((y - top) / (bottom - top), 0, 1)
        pygame.draw.line(gradient, (255, int(lerp(248, 110, t)), int(lerp(120, 20, t)), 255), (0, y), (w, y))
    gradient.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)     # keep the gradient only inside the letters
    navy = mask.copy()
    navy.fill((18, 28, 90, 255), special_flags=pygame.BLEND_RGBA_MIN)
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    for d in range(16, 0, -1):                                           # deep extrusion down and to the right
        out.blit(navy, (d, d))
    for k in range(16):                                                  # white sticker outline
        a = k * math.pi / 8
        out.blit(mask, (int(round(5 * math.cos(a))), int(round(5 * math.sin(a)))))
    out.blit(gradient, (0, 0))
    return dict(image=out, mask=mask)


def draw_title(surf, title, cx, cy, t):
    """Blit the title and sweep a bright diagonal 'flash' across the letters every few seconds."""
    image = title["image"]
    rect = image.get_rect(center=(cx, cy))
    surf.blit(image, rect)
    w, h = image.get_size()
    period = 3.4
    progress = (t % period) / period * 1.7 - 0.35
    if not -0.2 < progress < 1.2:
        return
    x0 = progress * (w + h) - h
    shine = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.polygon(shine, (255, 255, 255, 215), [(x0, 0), (x0 + 70, 0), (x0 + 70 - h * 0.5, h), (x0 - h * 0.5, h)])
    shine.blit(title["mask"], (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surf.blit(shine, rect)


BOLT = [(0.05, -0.5), (0.32, -0.5), (0.12, -0.12), (0.3, -0.12), (-0.2, 0.5), (-0.05, 0.0), (-0.25, 0.0)]


def draw_bolt(surf, cx, cy, height, flip, t):
    """A flickering lightning bolt."""
    sign = -1 if flip else 1
    points = [(cx + sign * x * height, cy + y * height) for x, y in BOLT]
    glow = 0.5 + 0.5 * math.sin(t * 8 + (3 if flip else 0))
    pygame.draw.polygon(surf, (255, int(lerp(190, 240, glow)), int(lerp(40, 110, glow))), points)
    pygame.draw.polygon(surf, WHITE, points, 4)


def build_menu_background():
    """Night game: sky, stadium light beams, packed stands, striped grass, light towers."""
    surf = pygame.Surface((LOGICAL_W, LOGICAL_H))
    for y in range(LOGICAL_H):
        t = y / LOGICAL_H
        pygame.draw.line(surf, (int(lerp(10, 58, t)), int(lerp(14, 38, t)), int(lerp(46, 105, t))), (0, y), (LOGICAL_W, y))
    beams = pygame.Surface((LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)
    for lx in (110, 1170):
        pygame.draw.polygon(beams, (255, 250, 205, 26), [(lx, 80), (lx - 330, 720), (lx + 330, 720)])
    surf.blit(beams, (0, 0))
    pygame.draw.rect(surf, (30, 28, 50), (0, 170, LOGICAL_W, 150))                       # stands
    for _ in range(2600):
        surf.fill(random.choice([(120, 90, 85), (150, 145, 140), (95, 100, 125), (135, 60, 60), (60, 60, 80)]),
                  (random.randint(0, LOGICAL_W), random.randint(174, 316), 4, 4))
    pygame.draw.rect(surf, (20, 70, 50), (0, 318, LOGICAL_W, 24))                        # outfield wall
    pygame.draw.rect(surf, GOLD, (0, 318, LOGICAL_W, 4))
    fill_polygon_stripes(surf, [(0, 342), (LOGICAL_W, 342), (LOGICAL_W, LOGICAL_H), (0, LOGICAL_H)], (28, 84, 44), (34, 96, 50))
    for lx in (110, 1170):                                                               # light towers
        pygame.draw.rect(surf, (55, 55, 70), (lx - 6, 120, 12, 210))
        pygame.draw.rect(surf, (40, 40, 52), (lx - 48, 62, 96, 66), border_radius=6)
        for row in range(3):
            for col in range(4):
                pygame.draw.circle(surf, (255, 252, 225), (lx - 33 + col * 22, 78 + row * 20), 7)
    return surf


# =============================================================================
# 4. THE GAME  -  all the rules live here
# =============================================================================

class Game:
    def __init__(self):
        self.bat_background = build_bat_background()
        self.field_background = build_field_background()
        self.field_crowd = build_field_crowd()
        self.bat_crowd = build_bat_crowd()
        self.slugger = build_slugger_assets()
        self.bat_surface = pygame.Surface((BAT_W, BAT_H))
        self.preview_scene = pygame.Surface((LOGICAL_W, LOGICAL_H))      # used by the Animations gallery
        self.preview_bat = pygame.Surface((BAT_W, BAT_H))
        self.mouse = (-1, -1)
        self.configure(DEFAULT_TEAM_NAME, TEAM_COLORS[0][1], DEFAULT_DIFFICULTY, DEFAULT_INNINGS)

    def configure(self, team_name, team_color, difficulty, innings, logo=None):
        """Apply the start-screen choices and begin a fresh game."""
        self.team_name, self.team_color, self.innings = team_name, team_color, innings
        self.home_logo = logo if logo is not None else build_default_logo(team_name, team_color)
        self.cpu_logo = build_cpu_logo()
        self.set_difficulty(difficulty)
        self.reset()

    def set_difficulty(self, difficulty):
        """Switch difficulty (also used mid-game from the pause menu)."""
        self.difficulty = difficulty
        self.diff = DIFFICULTIES[difficulty]
        scale = self.diff["window"]                       # every timing window grows / shrinks together
        self.win_pp = PERFECT_PERFECT_WINDOW * scale
        self.win_perfect = PERFECT_WINDOW * scale
        self.win_good = GOOD_WINDOW * scale
        self.win_contact = CONTACT_WINDOW * scale
        self.win_foul = FOUL_WINDOW * scale

    def reset(self):
        self.inning, self.outs = 1, 0
        self.balls = self.strikes = 0
        self.runs = self.cpu_runs = 0
        self.crowd_energy = self.cpu_cheer = 0.0     # how fired up your crowd / the CPU's dugout is (decays over time)
        self.cpu_roll = random.random()      # 0-1: how much of its allowed maximum the CPU will score this game
        self.my_line, self.cpu_line, self.inning_start_runs = [], [], 0      # line score
        self.stats = dict(hits=0, hr=0, k=0, bb=0, perfect=0, steals=0, steal_att=0)
        self.bases = [0, 0, 0]               # [first, second, third]: 1 if a runner is on it
        self.pitch = self.hit = self.fp = None
        self.skin = random.choice(SKIN_TONES)                    # the current batter's skin tone (he keeps it on the bases)
        pick_bat_style()                                        # ...and a bat
        self.new_batter = False                                  # True after an at-bat ends: the next batter gets a new skin tone
        self.settle, self.finish_big = 1.0, False                # easing back from the held follow-through (1 = done)
        self.fielder_skins = {name: random.choice(SKIN_TONES) for name in FIELDER_POSTS}
        self.pitch_history = []              # the last few pitch names (the pitching brain avoids being predictable)
        self.steal_armed = False             # S pressed before the pitch
        self.swing_clock = -1
        self.confetti = []
        self.celebrating = self.wait_click = False
        self.quit_to_menu = False            # set when the player clicks away from the GAME OVER screen
        self.clock = 0.0                     # running time, used for waving fans etc.
        self.fan = None                      # (x, y) of the fan catching a home run, or None
        self.board_hit, self.board_time = False, -1.0     # a home run hit the scoreboard / seconds since it did
        self.hr_distance = 0                 # feet, for the home run message
        self.shake = self.shake_mag = 0.0    # screen shake on solid contact
        self.paused, self.pause_screen, self.pause_index = False, "main", 0
        self.anim_index, self.anim_clock = 0, 0.0
        self.view, self.fade = "bat", 0.0
        self.set_state("WAIT")

    # ---- states & views ------------------------------------------------------
    # WAIT -> WIND_UP -> PITCH -> BALL_IN_FLIGHT (home run) | FIELD_PLAY (everything else) -> MESSAGE -> WAIT ...
    def cheer(self, amount):
        """Fire up the crowd and your dugout."""
        self.crowd_energy = min(1.5, self.crowd_energy + amount)

    def cheer_cpu(self, amount):
        """Fire up the CPU's dugout (it just got an out or scored)."""
        self.cpu_cheer = min(1.5, self.cpu_cheer + amount)

    def blit_bat_scene(self, surf, t=None, energy=None):
        """The batting-view background with the moving crowd on top."""
        surf.blit(self.bat_background, (0, 0))
        draw_crowd(surf, self.bat_crowd, self.clock if t is None else t,
                   self.crowd_energy if energy is None else energy, self.team_color, BAT_W)

    def blit_field_scene(self, surf, t=None, energy=None):
        """The overhead field with the moving crowd and the two dugouts (with players) on top."""
        t = self.clock if t is None else t
        e = self.crowd_energy if energy is None else energy
        surf.blit(self.field_background, (0, 0))
        draw_crowd(surf, self.field_crowd, t, e, self.team_color, LOGICAL_W)
        cpu_e = self.cpu_cheer if energy is None else energy * 0.8
        (hx, hy), (cx, cy) = DUGOUTS["left"], DUGOUTS["right"]
        draw_dugout_players(surf, hx, hy, (240, 240, 240), self.team_color, t, e, 0.4)       # your guys: left dugout
        draw_dugout_players(surf, cx, cy, FIELD_BODY, FIELD_CAP, t, cpu_e, 2.9)              # the CPU's guys: right dugout
        draw_dugout_front(surf, hx, hy)
        draw_dugout_front(surf, cx, cy)

    def set_state(self, state):
        self.state, self.state_time = state, 0.0
        if state != "MESSAGE":
            self.celebrating = False                         # stop the fireworks once we leave the message
        if state == "WAIT" and self.new_batter:              # the at-bat is over: a fresh batter steps in, already in his stance
            self.skin, self.new_batter = random.choice(SKIN_TONES), False
            pick_bat_style()                                    # a new batter brings a new bat
            self.swing_clock, self.settle = -1, 1.0          # (no follow-through held over from the last batter)
        if state in ("WAIT", "WIND_UP", "PITCH", "BALL_IN_FLIGHT", "HR_CUTSCENE", "GAME_OVER"):
            self.set_view("bat")

    def set_view(self, view):
        if view != self.view:
            self.view, self.fade = view, FADE_TIME

    def show_message(self, big, small="", duration=MESSAGE_TIME, then=None, wait=False):
        """Show a result. wait=True (used after contact) keeps it up until the player clicks NEXT PITCH."""
        self.message, self.sub_message = big, small
        self.message_duration, self.after_message, self.wait_click = duration, then, wait
        self.celebrating = False
        self.set_state("MESSAGE")

    def continue_after_message(self):
        after, self.after_message, self.wait_click = self.after_message, None, False
        self.fan = None
        if after:
            after()
        else:
            self.set_state("WAIT")

    # ---- input ---------------------------------------------------------------
    def press_swing(self):
        if self.paused:
            return
        if self.state == "GAME_OVER":
            self.quit_to_menu = True                         # back to the start screen
        elif self.state == "PITCH" and not self.pitch.swung:
            self.swing()
        elif self.state == "HR_CUTSCENE" and self.state_time > 0.8:
            self.finish_slugger()                            # click / SPACE skips the cutscene
        elif self.state == "MESSAGE" and self.wait_click and self.state_time >= NEXT_PITCH_DELAY:
            self.continue_after_message()                    # SPACE = NEXT PITCH

    def press_click(self, pos):
        """Mouse click at a canvas position."""
        if self.paused:
            return self.pause_click(pos)
        if self.state == "MESSAGE" and self.wait_click:      # only the NEXT PITCH button continues
            if self.state_time >= NEXT_PITCH_DELAY and math.hypot(pos[0] - NEXT_BUTTON[0], pos[1] - NEXT_BUTTON[1]) <= NEXT_BUTTON_RADIUS:
                self.continue_after_message()
            return
        if self.state != "FIELD_PLAY":
            return self.press_swing()
        button = self.field_button()
        if button and pygame.Rect(button[1] - 40, button[2] - 22, 80, 96).collidepoint(pos):
            return self.action_slide() if button[0] == "Slide" else self.action_send()
        runner = self.fp.runner
        rx, ry = point_on_path(runner.pos)
        if math.hypot(pos[0] - rx, pos[1] - (ry - 16)) <= 30:
            self.action_turn() if runner.moving else self.action_send()

    def press_run_key(self):
        """R: send a standing runner, or tell a moving runner to run THROUGH the next bag."""
        if self.state != "FIELD_PLAY" or self.fp.pending:
            return
        runner = self.fp.runner
        if not runner.moving:
            self.action_send()
        elif runner.forward and not runner.sliding and self.can_continue_from(runner.target):
            runner.run_through = True

    def press_slide_key(self):
        """S: slide during a play, or (before the pitch, runners on) tell the runners to steal."""
        if self.state == "FIELD_PLAY":
            self.action_slide()
        elif self.state in ("WAIT", "WIND_UP") and any(self.bases):
            self.steal_armed = not self.steal_armed

    # ---- pitching ------------------------------------------------------------
    def choose_pitch(self):
        """The pitching brain: weights each pitch by the count, the runners and what he just threw."""
        names = list(self.diff["pitches"])
        weights = {n: PITCHES[n]["chance"] for n in names}
        chase = [n for n in names if not PITCHES[n]["hittable"]]         # splitter / slider: always balls
        if self.strikes == 2:                                            # put him away with something he'll chase
            for n in chase:
                weights[n] *= 2.2
            weights["Curveball"] *= 1.3
        elif self.balls == 3:                                            # can't walk him: throw a strike
            for n in chase:
                weights[n] *= 0.15
            weights["Fastball"] *= 2.0
        elif self.balls >= 2 and self.strikes == 0:
            weights["Fastball"] *= 1.4
        if self.balls == 0 and self.strikes == 0:                        # first-pitch strike
            weights["Fastball"] *= 1.3
        if any(self.bases):                                              # hold the runners with the heat
            weights["Fastball"] *= 1.3
        if self.pitch_history:
            last = self.pitch_history[-1]
            weights[last] *= 0.55                                        # don't be predictable
            if last == "Fastball" and "Changeup" in weights:
                weights["Changeup"] *= 1.8                               # change speeds after the heat
        return random.choices(names, weights=[weights[n] for n in names])[0]

    def choose_zone(self):
        weights = list(ZONE_WEIGHTS)
        if self.strikes == 2:
            weights = [35, 30, 35]                                       # work the edges with two strikes
        elif self.balls == 3:
            weights = [15, 70, 15]                                       # right down the middle
        return random.choices([-1, 0, 1], weights=weights)[0]

    def start_pitch(self):
        self.finish_big = bool(self.hit and self.hit.quality == "perfect_perfect")      # which finish was he holding?
        self.settle = 0.0 if (self.swing_clock >= 0 and not self.new_batter) else 1.0   # same batter: ease back to the stance
        if self.new_batter:                                  # a new batter steps in with his own skin tone
            self.skin, self.new_batter = random.choice(SKIN_TONES), False
            pick_bat_style()                                    # a new batter brings a new bat
        name = self.choose_pitch()
        cfg = PITCHES[name]
        t = random.random()
        speed = self.diff["speed"]                           # difficulty: >1 = faster pitches, <1 = slower
        zone = self.choose_zone()
        self.pitch = Pitch(name, lerp(*cfg["seconds"], t) / speed, round(lerp(*cfg["mph"], t) * speed), cfg["hittable"],
                           zone=zone, offset=zone * self.diff["zone_offset"])
        self.pitch_history = (self.pitch_history + [name])[-3:]
        self.hit = self.fp = self.fan = None
        self.board_hit, self.board_time = False, -1.0
        self.swing_clock = -1
        self.set_state("WIND_UP")

    def swing(self):
        """Judge the swing by how far it was from the perfect moment (which depends on pitch location)."""
        pitch = self.pitch
        pitch.swung, pitch.swing_time = True, pitch.time
        self.swing_clock = 0
        raw_error = pitch.time - pitch.duration                  # vs. the plate: used for which way the ball is pulled
        error = pitch.time - (pitch.duration + pitch.offset)     # vs. the perfect swing for this location
        size = abs(error)
        # a normally unhittable pitch (the splitter) can be hit on Easy, but only inside the green window
        can_hit = pitch.hittable or (self.diff["splitter_in_green"] and size < self.win_perfect)
        if not can_hit:
            pitch.label = "MISS"
        elif size < self.win_pp:
            pitch.label = "PERFECT PERFECT"
        elif size < self.win_perfect:
            pitch.label = "PERFECT"
        elif size < self.win_good:
            pitch.label = "GOOD"
        else:
            pitch.label = "EARLY" if error < 0 else "LATE"
        if can_hit and size < self.win_perfect:
            self.stats["perfect"] += 1
            self.cheer(0.9 if size < self.win_pp else 0.4)                 # the crowd loves a great swing

        if not can_hit or size > self.win_foul:
            pitch.result = "miss"
        elif size > self.win_contact:
            pitch.result = "foul"
        else:
            quality = ("perfect_perfect" if size < self.win_pp else "perfect" if size < self.win_perfect
                       else "good" if size < self.win_good else "weak")
            self.make_contact(quality, raw_error)

    def resolve_steal(self, pitch):
        """Runners go on the pitch. Returns (note, third_out)."""
        first, second, third = self.bases
        self.stats["steal_att"] += 1
        if random.random() < STEAL_CHANCE[pitch.name]:
            self.stats["steals"] += 1
            scored = 1 if third else 0
            self.runs += scored
            self.bases = [0, first, second]                  # everybody moves up one base
            return "Stolen base!" + (" Run scores!" if scored else ""), False
        if third:                                            # the lead runner is the one who gets thrown out
            third = 0
        elif second:
            second = 0
        else:
            first = 0
        self.bases = [first, second, third]
        self.outs += 1
        return "Caught stealing!", self.outs >= OUTS_PER_INNING

    def finish_pitch_without_contact(self):
        """The ball passed: strike, ball, foul, or swing-and-miss."""
        pitch = self.pitch
        armed, self.steal_armed = self.steal_armed, False
        note = ""
        if armed and pitch.result != "foul" and any(self.bases):      # on a foul the runners go back
            note, third_out = self.resolve_steal(pitch)
            if third_out:
                self.end_at_bat()
                return self.show_message("CAUGHT STEALING", "Side retired", then=self.end_inning)
        info = f"{pitch.name} {pitch.mph} MPH"
        if note:
            info += f"  |  {note}"
        if pitch.result == "foul":
            if random.random() < FOUL_CAUGHT_CHANCE:                  # a foul pop that gets caught
                return self.record_out("FOUL OUT", "Caught in foul territory")
            if self.strikes == STRIKES_FOR_OUT - 1 and random.random() < FOUL_TIP_CHANCE:
                return self.record_out("STRIKEOUT (FOUL TIP)", info)
            self.strikes = min(self.strikes + 1, STRIKES_FOR_OUT - 1)
            self.show_message("FOUL BALL", info)
        elif pitch.result == "miss" or pitch.hittable:       # swung and missed, or took a strike
            self.strikes += 1
            if self.strikes >= STRIKES_FOR_OUT:
                self.record_out("STRIKEOUT" if pitch.result else "STRIKEOUT LOOKING", info)
            else:
                self.show_message("SWING & MISS" if pitch.result else "STRIKE", info)
        else:                                                # took a splitter / slider -> ball
            self.balls += 1
            if self.balls >= BALLS_FOR_WALK:
                self.walk(note)
            else:
                self.show_message("BALL", info)

    # ---- contact -------------------------------------------------------------
    def make_contact(self, quality, raw_error):
        self.steal_armed = False                             # the steal is called off when the ball is put in play
        roll = random.random()
        kind = next(result for chance, result in HIT_TABLES[quality] if roll < chance)
        info = HIT_INFO[kind]
        x, y, _ = pitch_position(self.pitch, self.pitch.time / self.pitch.duration)
        sideways = clamp(raw_error * 1500 + (random.random() - 0.5) * 120, -300, 300)   # early = left, late = right
        if kind == "HR":
            sideways = clamp(sideways + random.uniform(-110, 110), -300, 300)          # homers spray around the stands
        self.hit = Hit(kind, quality, x, y, sideways, info["flight"], info["arc"])
        self.hit.broken_bat = quality == "weak" and random.random() < BROKEN_BAT_CHANCE     # rare animation roll
        self.fan = None
        self.board_hit = False
        if quality == "perfect":                             # screen shake on the big ones
            self.shake, self.shake_mag = SHAKE_TIME, SHAKE_PERFECT
        elif quality == "perfect_perfect":
            self.shake, self.shake_mag = SHAKE_TIME, SHAKE_PERFECT_PERFECT
        self.hr_distance = 0
        if kind == "HR" and quality == "perfect_perfect" and SLUGGER_CUTSCENE:
            self.hr_distance = random.randint(400, 550)
            self.hit.distance = self.hr_distance
            self.set_state("HR_CUTSCENE")                    # the special side-view cutscene
        elif kind == "HR":
            self.hr_distance = random.randint(350, 449) if quality == "perfect" else random.randint(400, 550)
            self.hit.distance = self.hr_distance
            end_x = x + sideways
            if BOARD_X_MIN <= end_x <= BOARD_X_MAX:          # headed for the scoreboard...
                if random.random() < BOARD_HIT_CHANCE:       # rare animation: it smacks the scoreboard
                    self.board_hit = True
                else:                                        # ...usually it just clears it to one side
                    end_x = random.choice((BOARD_X_MIN - random.uniform(10, 70), BOARD_X_MAX + random.uniform(10, 70)))
                    self.hit.sideways = end_x - x
            if not self.board_hit and random.random() < FAN_CATCH_CHANCE:    # rare animation: a fan catches it
                self.fan = (end_x, hr_end_y(self.hr_distance))
            self.set_state("BALL_IN_FLIGHT")                 # stays in the batting view
        else:
            self.start_field_play()                          # cut to the overhead view

    def start_field_play(self):
        hit = self.hit
        hit.land_x, hit.land_y = landing_spot(hit.kind, hit.sideways)
        fielders = [Fielder(name, post, post[0], post[1]) for name, post in FIELDER_POSTS.items()]
        index = {f.name: i for i, f in enumerate(fielders)}
        # the closest fielder (not the catcher) chases the ball
        chaser = min((i for i, f in enumerate(fielders) if f.name != "C"),
                     key=lambda i: math.hypot(fielders[i].x - hit.land_x, fielders[i].y - hit.land_y))
        boost = 1.0
        if hit.arc > 0:
            # FLY BALL: the fielder reads where it will land (not perfectly), runs there, and when the ball comes down
            # it is a catch if he is inside the catch circle - otherwise it falls in for a hit.
            f = fielders[chaser]
            a, r = random.uniform(0, 2 * math.pi), FIELDER_MISJUDGE * math.sqrt(random.random())
            hit.read_x, hit.read_y = hit.land_x + r * math.cos(a), hit.land_y + r * math.sin(a)
            dx, dy = hit.read_x - f.x, hit.read_y - f.y
            dist = math.hypot(dx, dy)
            travel = min(dist, FIELDER_SPEED * max(0.0, hit.flight - FIELDER_REACTION))
            hit.catch_x = f.x + dx / dist * travel if dist else f.x
            hit.catch_y = f.y + dy / dist * travel if dist else f.y
            gap = math.hypot(hit.catch_x - hit.land_x, hit.catch_y - hit.land_y)
            hit.caught = gap <= CATCH_RADIUS.get(hit.quality, CATCH_RADIUS["good"])
            if hit.caught:
                hit.kind = "FLY_OUT"                         # inside the circle: an out, however it was hit
            elif hit.kind == "FLY_OUT":                      # outside the circle: a pop-up that drops in is a hit
                hit.kind = "1B" if math.hypot(hit.land_x - HOME[0], hit.land_y - HOME[1]) < 310 else "2B"
        info = HIT_INFO[hit.kind]

        # runners already on base advance automatically (as many bases as the hit earned, or forced on a grounder)
        if hit.kind == "GROUND_OUT":
            first, second, third = self.bases
            advance = [1 if first else 0, 1 if first and second else 0, 1 if first and second and third else 0]
        else:
            advance = [info["earned"]] * 3
        others, runs, new_bases = [], 0, [0, 0, 0]
        for i, on_base in enumerate(self.bases):
            if on_base:
                end = min(4, i + 1 + advance[i])
                others.append(dict(start=i + 1, end=end, pos=float(i + 1), skin=on_base))     # on_base holds his skin tone
                if end >= 4: runs += 1
                else: new_bases[end - 1] = on_base

        runner = Runner(earned=0, moving=True, wait=BATTER_START_DELAY)   # batter runs to first by himself (even on likely outs)
        self.fp = FieldPlay(hit, runner, fielders, Ball(HOME[0], HOME[1] - 10), others, runs, new_bases, index, chaser, boost)
        self.fp.skin = self.skin
        self.fp.dive_plan = hit.kind == "GROUND_OUT" and random.random() < DIVE_CHANCE      # rare animation rolls
        self.fp.leap_plan = hit.kind == "FLY_OUT" and random.random() < LEAP_CHANCE
        if hit.broken_bat:
            self.fp.broken = dict(t=0.0, dir=unit(hit.land_x - HOME[0], hit.land_y - HOME[1]))
        # better fielding: a backup runs behind the ball, and the pitcher backs up home on deep hits
        if hit.kind in ("1B", "2B", "3B") and math.hypot(hit.land_x - HOME[0], hit.land_y - HOME[1]) > 250:
            others_f = [f for i, f in enumerate(fielders) if i != chaser and f.name not in ("C", "P")]
            backup = min(others_f, key=lambda f: math.hypot(f.x - hit.land_x, f.y - hit.land_y))
            ux, uy = unit(hit.land_x - HOME[0], hit.land_y - HOME[1])
            backup.post = (clamp(hit.land_x + ux * BACKUP_DISTANCE, 60, 1220), clamp(hit.land_y + uy * BACKUP_DISTANCE, 255, 700))
            fielders[index["P"]].post = (HOME[0], HOME[1] - 60)
        self.set_view("field")
        self.set_state("FIELD_PLAY")

    # ---- the field play: update ----------------------------------------------
    def update_field_play(self, dt):
        fp = self.fp
        fp.time += dt
        for other in fp.others:                              # other runners jog to their new bases
            if fp.time > RUNNER_START_DELAY:
                other["pos"] = min(other["end"], other["pos"] + RUNNER_SPEED * dt)
        if fp.pending:
            fp.pending_time -= dt
            if fp.pending_time <= 0:
                self.finish_field_play(*fp.pending)
                return
        else:
            self.update_runner(dt)
        self.update_ball(dt)
        self.update_fielders(dt)
        self.update_rare(dt)
        self.update_gait(dt)
        self.age_dust(dt)
        if not fp.pending:
            self.fielder_ai()
            self.check_dead_ball(dt)
            if fp.time > FIELD_PLAY_TIMEOUT:
                self.decide_standing()

    def decide(self, outcome, base, delay):
        """The play is decided; wait `delay` seconds so the player can see it, then show the result."""
        self.fp.pending, self.fp.pending_time = (outcome, base), delay
        self.fp.runner.moving = False

    def decide_standing(self):
        """Play over with the runner standing still: safe on his bag, or out if he never left home."""
        base = round(self.fp.runner.pos)
        self.decide("safe" if base > 0 else "norun", base, 0)

    def update_runner(self, dt):
        r = self.fp.runner
        r.turn_cooldown = max(0.0, r.turn_cooldown - dt)
        r.recovery = max(0.0, r.recovery - dt)
        if not r.moving:
            return
        if r.wait > 0:                                       # reaction time at the start
            r.wait -= dt
            return
        step = RUNNER_SPEED * (SLIDE_SPEED_MULT if r.sliding else 1.0) * dt
        r.pos = min(r.pos + step, r.target) if r.forward else max(r.pos - step, r.target)
        if r.pos == r.target:
            self.runner_arrives()                            # he reaches the bag first; only THEN can he be called out

    def runner_arrives(self):
        r = self.fp.runner
        base = r.target
        if base > r.earned and self.ball_at_base(base):      # ball beat him to the bag
            return self.decide("out", base, 0.9)
        if base >= 4:
            return self.decide("score", 4, 0.5)
        if r.forward and (base < r.earned or (r.run_through and self.can_continue_from(base) and not r.sliding)):
            r.target, r.run_through = base + 1, False        # keep running (earned bases / run-through)
            return
        r.moving, r.run_through = False, False               # stop on the bag
        if r.sliding:
            r.sliding, r.recovery = False, SLIDE_RECOVERY

    def update_ball(self, dt):
        fp, ball, hit = self.fp, self.fp.ball, self.fp.hit
        if ball.mode == "flying":
            ball.t += dt
            u = min(1, ball.t / hit.flight)
            end_x, end_y = (hit.catch_x, hit.catch_y) if hit.caught else (hit.land_x, hit.land_y)   # a caught ball drops into the glove
            ball.x, ball.y = lerp(HOME[0], end_x, u), lerp(HOME[1], end_y, u)
            ball.z = abs(math.sin(u * math.pi * 5)) * 12 * (1 - u) if hit.arc == 0 else hit.arc * math.sin(math.pi * u)
            if fp.leap_plan:
                ball.z += LEAP_GLOVE_Z * u ** 3              # the ball arrives at glove height for the leaping catch
            elif hit.kind == "FLY_OUT":
                ball.z += 10 * u ** 3                        # a normal catch: the ball comes down into the glove
                ball.x += 8 * u ** 3
            if u >= 1:
                ball.z = 0
                if hit.kind == "FLY_OUT":                    # caught in the air
                    ball.mode, ball.holder, ball.hold_time, ball.quick = "held", fp.chaser, 0.0, False
                    fp.catch = dict(t=0.0)
                    self.decide("flyout", 0, 0.9)
                else:                                        # it falls in: bounce and keep rolling
                    ball.mode, ball.bt = "loose", 0.0
                    ux, uy = unit(hit.land_x - HOME[0], hit.land_y - HOME[1])
                    speed = HIT_ROLL_SPEED if hit.arc > 0 else GROUNDER_ROLL_SPEED
                    ball.vx, ball.vy = ux * speed, uy * speed
                    if hit.arc > 0:
                        fp.landed = dict(t=0.0, x=ball.x, y=ball.y)
        elif ball.mode == "loose":
            ball.bt += dt
            drag = math.exp(-ROLL_DRAG * dt)
            ball.vx *= drag
            ball.vy *= drag
            ball.x = clamp(ball.x + ball.vx * dt, 40, 1240)
            ball.y = clamp(ball.y + ball.vy * dt, 255, 700)
            ball.z = abs(math.sin(ball.bt * 9)) * 14 * math.exp(-3 * ball.bt) if hit.arc > 0 else 0
            chaser = fp.fielders[fp.chaser]
            if math.hypot(chaser.x - ball.x, chaser.y - ball.y) < 14:
                ball.mode, ball.holder, ball.hold_time, ball.quick = "held", fp.chaser, 0.0, False
        elif ball.mode == "thrown":
            ball.t += dt
            u = min(1, ball.t / ball.dur)
            ball.x, ball.y = lerp(ball.sx, ball.tx, u), lerp(ball.sy, ball.ty, u)
            ball.z = 25 * math.sin(math.pi * u)
            if u >= 1:
                ball.mode, ball.holder, ball.hold_time, ball.z, ball.quick = "held", ball.receiver, 0.0, 0.0, True
        if ball.mode == "held":
            holder = fp.fielders[ball.holder]
            ball.x, ball.y, ball.z = holder.x, holder.y, 0
            ball.hold_time += dt

    def update_fielders(self, dt):
        fp = self.fp
        for i, f in enumerate(fp.fielders):
            chasing = i == fp.chaser and fp.ball.mode in ("flying", "loose")
            if i == fp.chaser and fp.pending and fp.pending[0] == "flyout":
                continue                                       # he made the catch: stand still with the ball
            if chasing and fp.ball.mode == "loose":
                tx, ty = fp.ball.x, fp.ball.y                  # chase the rolling ball
            elif chasing:
                if fp.hit.arc > 0:
                    if fp.time < FIELDER_REACTION:
                        continue                               # reading the fly ball
                    tx, ty = fp.hit.read_x, fp.hit.read_y      # runs to where he thinks it will land
                else:
                    tx, ty = fp.hit.land_x, fp.hit.land_y
            else:
                tx, ty = f.post
            speed = FIELDER_SPEED * (fp.boost if chasing else 1.0 if f.post in BASES else 0.8)
            if fp.dive and fp.dive["idx"] == i:
                if fp.dive["t"] < DIVE_TIME:
                    speed = FIELDER_SPEED * 2.2              # the dive carries him forward fast
                elif fp.ball.mode == "held":
                    speed = 0                                # then he stays down with the ball until he gets up
            dx, dy = tx - f.x, ty - f.y
            dist = math.hypot(dx, dy)
            if dist > 1:
                step = min(dist, speed * dt)
                f.x += dx / dist * step
                f.y += dy / dist * step

    def load_amount(self):
        """0..1: how far the batter has loaded (hands back and up) as the pitch comes in."""
        if self.state == "WIND_UP":
            return smooth((self.state_time - (WIND_UP_TIME - LOAD_TIME)) / LOAD_TIME)
        return 1.0 if self.state == "PITCH" else 0.0

    # ---- gait: sway + dust under the feet ---------------------------------------
    def gait(self, key):
        """(sway, bob) in pixels for a player, 0 if he is standing still."""
        fp = self.fp
        if key not in fp.moving:
            return 0.0, 0.0
        phase = fp.gait.get(key, 0.0)
        return math.sin(phase) * SWAY_AMOUNT, abs(math.sin(phase)) * BOB_AMOUNT

    def runner_xy(self):
        """Where the batter-runner is: on the base path, or (after an out) on his walk back to the dugout."""
        fp = self.fp
        if fp.walk:
            w = fp.walk
            k = min(1.0, DUGOUT_WALK_SPEED * w["t"] / w["dist"])
            return w["sx"] + (w["tx"] - w["sx"]) * k, w["sy"] + (w["ty"] - w["sy"]) * k
        return point_on_path(fp.runner.pos)

    def start_dugout_walk(self):
        """The batter made an out: he heads for the nearer dugout (he doesn't have to get there before the next pitch)."""
        fp = self.fp
        fp.runner.sliding = False                            # (no more sliding on the ground once he is out)
        fp.runner.moving = False
        sx, sy = point_on_path(fp.runner.pos)
        tx, ty = DUGOUTS["right"] if sx > HOME[0] + 20 else DUGOUTS["left"]
        fp.walk = dict(sx=sx, sy=sy, tx=tx, ty=ty, t=0.0, dist=max(1.0, math.hypot(tx - sx, ty - sy)), done=False)

    def update_walk(self, dt):
        w = self.fp.walk
        if w and not w["done"]:
            w["t"] += dt
            if DUGOUT_WALK_SPEED * w["t"] >= w["dist"]:
                w["done"] = True                             # he has stepped into the dugout

    def shadow_at(self, x, y):
        return TERRAIN[terrain_at(x, y)]["shadow"]

    def update_gait(self, dt):
        """Work out who moved this frame: advance their step cycle and kick up dust from their feet."""
        fp = self.fp
        movers = {("f", i): (f.x, f.y, False) for i, f in enumerate(fp.fielders)}
        r = fp.runner
        movers["runner"] = self.runner_xy() + (r.sliding,)
        for n, other in enumerate(fp.others):
            if other["pos"] < 4:
                movers[("o", n)] = point_on_path(other["pos"]) + (False,)
        fp.moving = set()
        for key, (x, y, sliding) in movers.items():
            prev = fp.prev.get(key)
            fp.prev[key] = (x, y)
            if prev is None or dt <= 0:
                continue
            dx, dy = x - prev[0], y - prev[1]
            d = math.hypot(dx, dy)
            if d < 0.15:
                continue
            if not sliding:
                fp.moving.add(key)
                fp.gait[key] = fp.gait.get(key, 0.0) + d * STRIDE_PER_PIXEL
            self.emit_dust(x, y, dx / d, dy / d, d / dt, sliding, dt)

    def emit_dust(self, x, y, ux, uy, speed, sliding, dt):
        """Throw a few particles back from the feet, in the colour of the ground he is on."""
        fp = self.fp
        terrain = TERRAIN[terrain_at(x, y)]
        expected = (SLIDE_DUST_RATE if sliding else DUST_RATE) * dt * clamp(speed / FIELDER_SPEED, 0.6, 1.8)
        for _ in range(int(expected) + (1 if random.random() < expected % 1 else 0)):
            if len(fp.dust) >= MAX_DUST:
                return
            back = random.uniform(12, 42) * (1.6 if sliding else 1.0)
            fp.dust.append(dict(x=x + random.uniform(-5, 5), y=y + random.uniform(-1, 2), z=random.uniform(0, 2),
                                vx=-ux * back + random.uniform(-14, 14), vy=-uy * back * 0.6 + random.uniform(-8, 8),
                                vz=random.uniform(30, 80) if terrain["kind"] == "blades" else random.uniform(10, 36),
                                life=0.0, max=random.uniform(0.35, 0.65), size=random.uniform(2.0, 3.6),
                                color=random.choice(terrain["dust"]), kind=terrain["kind"]))

    def age_dust(self, dt):
        fp = self.fp
        for p in fp.dust:
            p["life"] += dt
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["z"] = max(0.0, p["z"] + p["vz"] * dt)
            if p["kind"] == "blades":
                p["vz"] -= 260 * dt                              # flung up, then falls back
            else:
                p["vx"] *= math.exp(-3 * dt)                     # a puff of dirt hangs and drifts
                p["vy"] *= math.exp(-3 * dt)
        fp.dust = [p for p in fp.dust if p["life"] < p["max"]]

    def draw_dust(self, surf):
        for p in self.fp.dust:
            age = p["life"] / p["max"]
            if p["kind"] == "blades":
                a = (p["x"], p["y"] - p["z"])
                pygame.draw.line(surf, p["color"], a, (a[0] + (2 if p["vx"] > 0 else -2), a[1] - 3), 2)
            else:
                r = p["size"] * (0.6 + 0.9 * age) * (1 - 0.55 * age)
                pygame.draw.circle(surf, p["color"], (p["x"], p["y"] - p["z"]), max(1, r))

    def update_rare(self, dt, allow_trigger=True):
        """Timers for the rare animations (broken bat, diving stop, leaping catch) and the moment each one starts."""
        fp = self.fp
        ball, hit = fp.ball, fp.hit
        if fp.catch:
            fp.catch["t"] += dt
        if fp.landed:
            fp.landed["t"] += dt
        if fp.broken:
            fp.broken["t"] += dt
        if fp.dive:
            fp.dive["t"] += dt
            if fp.dive["t"] > DIVE_TIME + DIVE_RECOVERY:
                fp.dive = None
        elif allow_trigger and fp.dive_plan and not fp.dived and ball.mode in ("flying", "loose") and fp.time > 0.3:
            f = fp.fielders[fp.chaser]
            if math.hypot(f.x - ball.x, f.y - ball.y) < 60:       # the ball is nearly in reach: dive for it
                fp.dive, fp.dived = dict(idx=fp.chaser, t=0.0, dir=1 if ball.x >= f.x else -1), True
        if fp.leap:
            fp.leap["t"] += dt
            if fp.leap["t"] > LEAP_TIME:
                fp.leap = None
        elif allow_trigger and fp.leap_plan and not fp.leaped and ball.mode == "flying" and hit.flight - ball.t < LEAP_TIME / 2:
            fp.leap, fp.leaped = dict(t=0.0), True                # jump so the catch lands at the top of the leap

    def ball_at_base(self, base):
        """True if a fielder holding the ball is standing at this bag."""
        fp = self.fp
        if fp.ball.mode != "held":
            return False
        f = fp.fielders[fp.ball.holder]
        return math.hypot(f.x - BASES[base][0], f.y - BASES[base][1]) <= BAG_RADIUS

    def fielder_ai(self):
        """The fielder holding the ball decides what to do with it.
        If the runner is heading for a bag, the ball goes to whoever is CLOSEST to that bag (never to an empty bag),
        and that fielder runs to the bag with it to get the runner out. If the holder is the closest, he runs it himself."""
        fp, ball, runner = self.fp, self.fp.ball, self.fp.runner
        if ball.mode != "held" or ball.hold_time < (RELAY_TIME if ball.quick else FIELDER_PICKUP_TIME):
            return
        if fp.dive and fp.dive["idx"] == ball.holder:
            return                                           # still on the ground after the dive
        holder = fp.fielders[ball.holder]
        if runner.moving:
            base = runner.target
            if self.ball_at_base(base):
                return                                       # already waiting for him at the bag
            bag = BASES[base]
            if holder.post == bag:
                return                                       # he is already carrying it to the bag
            def closeness(i):                                # distance to the bag; outfielders count as farther (they don't cover bags)
                f = fp.fielders[i]
                weight = 1.5 if f.name in ("LF", "CF", "RF") else 0.85 if f.name == BASE_FIELDERS[base] else 1.0
                return math.hypot(f.x - bag[0], f.y - bag[1]) * weight
            nearest = min(range(len(fp.fielders)), key=closeness)
            if nearest == ball.holder:
                holder.post = bag                            # he is the closest one: run it to the bag himself
                return
            if holder.name in ("LF", "CF", "RF") and math.hypot(holder.x - bag[0], holder.y - bag[1]) > CUTOFF_MIN_THROW:
                cutoff = fp.index["SS" if holder.x < 640 else "2B"]      # long throw: hit the cutoff man halfway
                if cutoff != nearest and cutoff != ball.holder:
                    mid = ((holder.x + bag[0]) / 2, (holder.y + bag[1]) / 2)
                    return self.throw_ball(cutoff, mid)
            self.throw_ball(nearest, bag)                    # throw to the man closest to the bag; he runs the bag
        elif holder.name != "P":                             # nobody running: get the ball back to the pitcher
            self.throw_ball(fp.index["P"], FIELDER_POSTS["P"])

    def throw_ball(self, receiver, post):
        """Throw to a fielder (not to a spot). He is sent running toward `post`, and the throw leads him: the ball
        goes to where he will be when it arrives."""
        fp = self.fp
        ball, thrower = fp.ball, fp.fielders[fp.ball.holder]
        r = fp.fielders[receiver]
        r.post = post
        speed = FIELDER_SPEED * (1.0 if post in BASES else 0.8)     # a fielder running to a bag runs flat out
        dx, dy = post[0] - r.x, post[1] - r.y
        run = math.hypot(dx, dy)
        tx, ty = r.x, r.y
        for _ in range(3):                                   # where will he be when the ball gets there?
            dur = max(0.15, math.hypot(tx - thrower.x, ty - thrower.y) / THROW_SPEED)
            travel = min(run, speed * dur)
            tx, ty = (r.x + dx / run * travel, r.y + dy / run * travel) if run > 0 else (r.x, r.y)
        ball.mode, ball.t, ball.dur = "thrown", 0.0, max(0.15, math.hypot(tx - thrower.x, ty - thrower.y) / THROW_SPEED)
        ball.sx, ball.sy, ball.tx, ball.ty, ball.receiver = thrower.x, thrower.y, tx, ty, receiver

    def pitcher_has_ball(self):
        fp = self.fp
        return fp.ball.mode == "held" and fp.fielders[fp.ball.holder].name == "P"

    def check_dead_ball(self, dt):
        """Pitcher has the ball and the runner is standing on a bag: the play is over."""
        fp = self.fp
        if self.pitcher_has_ball() and not fp.runner.moving and fp.ball.hold_time >= FIELDER_PICKUP_TIME:
            fp.dead_time += dt
            if fp.dead_time >= DEAD_BALL_DELAY:
                self.decide_standing()
        else:
            fp.dead_time = 0.0

    # ---- runner actions (what the buttons do) ----------------------------------
    def can_continue_from(self, base):
        """Can a runner on/at `base` go on to the next one? (not home, and the next bag is free)"""
        return base < 4 and (base == 3 or not self.fp.new_bases[base])

    def can_send(self):
        fp = self.fp
        r = fp.runner
        return (self.state == "FIELD_PLAY" and not fp.pending and not r.moving and fp.hit.kind != "FLY_OUT" and 0 <= round(r.pos) <= 3
                and r.recovery <= 0 and not self.pitcher_has_ball() and self.can_continue_from(round(r.pos)))

    def action_send(self):
        if self.can_send():
            r = self.fp.runner
            r.target, r.forward, r.moving = round(r.pos) + 1, True, True
            r.pos, r.wait, r.run_through = float(round(r.pos)), 0.0, False
            r.turn_cooldown = TURN_COOLDOWN                  # can't be turned around instantly

    def action_slide(self):
        if self.field_button() and self.field_button()[0] == "Slide":
            self.fp.runner.sliding = True

    def action_turn(self):
        """Click the runner mid-run: he reverses direction (after a short cooldown)."""
        fp = self.fp
        r = fp.runner
        if fp.pending or not r.moving or r.sliding or r.turn_cooldown > 0 or r.wait > 0:
            return
        if r.forward:
            if r.target <= max(r.earned, 1):                 # can't turn back toward home or during the guaranteed part
                return
            r.target, r.forward = r.target - 1, False
        else:
            r.target, r.forward = r.target + 1, True
        r.run_through = False
        r.turn_cooldown = TURN_COOLDOWN

    def field_button(self):
        """(label, x, y) of the on-screen button right now, or None."""
        if self.state != "FIELD_PLAY" or self.fp.pending:
            return None
        r = self.fp.runner
        if r.moving:
            if r.forward and not r.sliding and r.wait <= 0 and r.target >= r.earned and r.target - r.pos <= SLIDE_RANGE:
                return ("Slide",) + tuple(BASES[r.target])           # SLIDE shows on the bag you are approaching
            return None
        if self.can_send():
            return ("Run",) + tuple(point_on_path(r.pos))             # RUN shows under a standing runner
        return None

    # ---- ending a play -------------------------------------------------------
    def finish_field_play(self, outcome, base):
        fp = self.fp
        runs, new_bases = fp.others_runs, fp.new_bases[:]
        for other in fp.others:
            other["pos"] = other["end"]
        self.end_at_bat()
        third_out = False
        if outcome in ("out", "flyout", "norun"):
            self.outs += 1
            self.start_dugout_walk()                         # he walks back to the dugout while the result is shown
            if self.outs >= OUTS_PER_INNING:                 # third out: no runs count
                runs, new_bases, third_out = 0, [0, 0, 0], True
        elif outcome == "score":
            runs += 1
            self.stats["hits"] += 1
            self.stats["hr"] += 1
        else:
            new_bases[base - 1] = fp.skin or 1                 # the batter stays on base with his own skin tone
            self.stats["hits"] += 1
        self.runs += runs
        self.bases = new_bases
        if outcome in ("out", "flyout", "norun"):
            self.cheer_cpu(0.8)                                            # the CPU's dugout celebrates your out
        else:
            self.cheer(0.6 + 0.2 * base + 0.35 * min(runs, 3))
        score_text = f"{runs} run{'s' if runs > 1 else ''} scored" if runs else ""
        if outcome == "flyout":
            big = "FLY OUT"
        elif outcome == "norun":
            big = "OUT"
        elif outcome == "out":
            big = f"OUT at {BASE_NAMES[base - 1].upper()}"
        elif outcome == "score":
            big = "INSIDE-THE-PARK HR!"
        else:
            big = {1: "SINGLE", 2: "DOUBLE", 3: "TRIPLE"}[base]
            if base == 1 and fp.hit.kind == "GROUND_OUT":
                big = "INFIELD SINGLE"
        small = "Side retired" if third_out else score_text or ("Never ran to first" if outcome == "norun" else "")
        self.show_message(big, small, then=self.end_inning if third_out else None, wait=True)

    def end_at_bat(self):
        self.balls = self.strikes = 0
        self.new_batter = True

    def record_out(self, text, note=""):
        self.outs += 1
        if text.startswith("STRIKEOUT"):
            self.stats["k"] += 1
        self.end_at_bat()
        self.cheer_cpu(0.8)                                                # the CPU's dugout celebrates your out
        third_out = self.outs >= OUTS_PER_INNING
        self.show_message(text, "Side retired" if third_out else note, then=self.end_inning if third_out else None)

    def walk(self, note=""):
        first, second, third = self.bases
        if first and second and third: self.runs += 1
        if first and second: third = second                  # runners keep their skin tones as they move up
        if first: second = first
        self.bases = [self.skin, second, third]
        self.stats["bb"] += 1
        self.end_at_bat()
        self.show_message("WALK", "Take your base" + (f"  |  {note}" if note else ""))

    def finish_slugger(self):
        self.fade = FADE_TIME
        self.home_run()

    def home_run(self):
        runs = 1 + sum(1 for b in self.bases if b)
        self.runs += runs
        self.bases = [0, 0, 0]
        self.stats["hits"] += 1
        self.stats["hr"] += 1
        self.end_at_bat()
        small = f"{runs} runs score" if runs > 1 else "Gone!"
        if self.fan:
            small += "  A fan makes the catch!"
        if self.board_hit:
            small += "  Off the scoreboard!"
            self.board_time = 0.0                            # start the rock-and-flicker animation
        big = f"HOME RUN!  {self.hr_distance} FT" if self.hr_distance else "HOME RUN!"
        self.cheer(1.3)                                                    # the whole place erupts
        self.show_message(big, small, HOME_RUN_MESSAGE_TIME, wait=True)
        self.celebrating, self.fireworks_launched = True, 0
        self.add_fireworks(385, 70)

    def cpu_cap(self):
        """The most the CPU can score: 15, or 80% of your runs once you have more than 15."""
        return CPU_MAX_TOTAL if self.runs <= CPU_MAX_TOTAL else int(self.runs * CPU_RATIO_ABOVE_MAX)

    def cpu_half_inning(self):
        """The CPU's turn at bat. Its final total is a random 0 to cap (cap = 15, or 80% of your score above 15).
        The roll is made once per game and its runs arrive a bit at a time, so the line score looks natural."""
        target = round(self.cpu_roll * self.cpu_cap())
        if self.inning >= self.innings:                      # last inning (or extra innings): reach the total
            new_total = target
        else:                                                # earlier innings: on pace, with some wobble
            pace = target * self.inning / self.innings
            new_total = round(pace + random.uniform(-1.5, 1.5))
        new_total = clamp(new_total, self.cpu_runs, max(target, self.cpu_runs))
        added = new_total - self.cpu_runs
        self.cpu_runs = new_total
        return added

    def end_inning(self):
        self.steal_armed = False
        self.my_line.append(self.runs - self.inning_start_runs)
        cpu_scored = self.cpu_half_inning()
        self.cpu_line.append(cpu_scored)
        if cpu_scored:
            self.cheer_cpu(0.9)                                            # the CPU scored: its dugout is up
        self.inning_start_runs = self.runs
        if self.inning >= self.innings and self.runs != self.cpu_runs:     # tied after the last inning = extra innings
            self.set_state("GAME_OVER")
            return
        self.inning += 1
        self.outs = 0
        self.bases = [0, 0, 0]
        self.set_state("WAIT")

    # ---- home run celebration ------------------------------------------------
    def add_fireworks(self, x, y):
        colors = [GOLD, RED, GREEN, (110, 198, 255), WHITE]
        for i in range(30):
            angle, speed = random.random() * 6.28, 60 + random.random() * 140
            self.confetti.append(dict(x=x, y=y, vx=math.cos(angle) * speed, vy=math.sin(angle) * speed - 40,
                                      size=3 + random.random() * 3, life=1.4 + random.random(), color=colors[i % 5]))

    def update_celebration(self, dt):
        for p in self.confetti:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vy"] += 260 * dt
            p["life"] -= dt
        self.confetti = [p for p in self.confetti if p["life"] > 0]
        if self.celebrating:
            if self.fireworks_launched < 6 and self.state_time > self.fireworks_launched * 0.4:
                self.add_fireworks(150 + random.random() * 470, 50 + random.random() * 80)
                self.fireworks_launched += 1
            if random.random() < 0.5:
                self.confetti.append(dict(x=random.random() * BAT_W, y=-5, vx=0, vy=60, size=4, life=3,
                                          color=random.choice([GOLD, RED, GREEN, (110, 198, 255)])))

    # ---- per-frame update ----------------------------------------------------
    def update(self, dt):
        if self.paused:                                      # the game freezes; only the gallery animations keep running
            self.anim_clock += dt
            return
        self.clock += dt
        self.crowd_energy = max(0.0, self.crowd_energy - CROWD_DECAY * dt)
        self.cpu_cheer = max(0.0, self.cpu_cheer - CROWD_DECAY * dt)
        self.state_time += dt
        self.fade = max(0.0, self.fade - dt)
        self.settle = min(1.0, self.settle + dt / SETTLE_TIME)
        self.shake = max(0.0, self.shake - dt)
        if self.board_time >= 0:                             # scoreboard rock-and-flicker clock
            self.board_time += dt
            if self.board_time > BOARD_ANIM_TIME:
                self.board_time = -1.0
        if self.swing_clock >= 0:
            self.swing_clock += dt
        self.update_celebration(dt)

        if self.state == "WAIT" and self.state_time > PAUSE_BEFORE_PITCH:
            self.start_pitch()
        elif self.state == "WIND_UP" and self.state_time > WIND_UP_TIME:
            self.set_state("PITCH")
        elif self.state == "PITCH":
            self.pitch.time += dt
            if self.pitch.time >= self.pitch.duration + METER_EXTRA_TIME:
                self.finish_pitch_without_contact()
        elif self.state == "HR_CUTSCENE":
            if self.state_time >= SLUGGER_TIME:
                self.finish_slugger()
        elif self.state == "BALL_IN_FLIGHT":
            self.hit.time += dt
            if self.hit.time >= self.hit.flight:
                self.home_run()
        elif self.state == "FIELD_PLAY":
            self.update_field_play(dt)
        elif self.state == "MESSAGE" and self.state_time > self.message_duration and not self.wait_click:
            self.continue_after_message()
        if self.state == "MESSAGE" and self.fp and self.view == "field":
            self.update_rare(dt, allow_trigger=False)        # let a dive / leap / bat finish while the result is shown
            self.update_walk(dt)                             # an out: the batter strolls toward the dugout
            self.update_gait(dt)                             # (his step cycle + a little dust under his feet)
            self.age_dust(dt)

    # ---- per-frame drawing ---------------------------------------------------
    def draw(self, canvas):
        if self.state == "HR_CUTSCENE":
            self.draw_slugger_cutscene(canvas)
        elif self.view == "bat":
            self.draw_bat_view(self.bat_surface)
            bat_h = int(LOGICAL_W * BAT_H / BAT_W)
            canvas.fill((14, 17, 22))
            canvas.blit(pygame.transform.smoothscale(self.bat_surface, (LOGICAL_W, bat_h)), (0, (LOGICAL_H - bat_h) // 2))
        else:
            self.draw_field_view(canvas)
        if self.state == "MESSAGE" and self.wait_click and self.state_time >= NEXT_PITCH_DELAY:
            draw_next_pitch_button(canvas, self.state_time)
        if self.state == "GAME_OVER":
            self.draw_game_over(canvas)
        if self.fade > 0:                                    # fade in after a view change
            shade = pygame.Surface((LOGICAL_W, LOGICAL_H))
            shade.set_alpha(int(255 * self.fade / FADE_TIME))
            canvas.blit(shade, (0, 0))
        if self.shake > 0 and not self.paused and self.state != "HR_CUTSCENE":      # screen shake on PERFECT hits
            amp = self.shake_mag * self.shake / SHAKE_TIME
            snapshot = canvas.copy()
            canvas.blit(snapshot, (random.uniform(-amp, amp), random.uniform(-amp, amp)))
        if self.paused:
            self.draw_pause(canvas)

    # ---- PERFECT PERFECT home run cutscene -------------------------------------
    def draw_slugger_cutscene(self, surf):
        self.draw_slugger_scene(surf, self.state_time)

    def draw_slugger_scene(self, surf, t_real):
        """The cutscene at time t_real (also used by the Animations gallery).
        At the moment of contact there is a short HIT-STOP: the picture freezes on the connecting swing while the
        explosion and flash play over it. Then the ball takes off, the camera waits so you can see him HOLD his
        follow-through, and only then does it whip over to chase the ball."""
        hit = SLUGGER_HIT_TIME
        contacted = t_real >= hit
        fx = max(0.0, t_real - hit)                                   # real seconds since contact (effects keep playing in the hit-stop)
        t = t_real if t_real < hit else hit if t_real < hit + SLUGGER_HITSTOP else t_real - SLUGGER_HITSTOP
        s = max(0.0, t - hit)                                         # game seconds since contact (frozen during the hit-stop)
        dist_k = clamp((self.hr_distance - 400) / 150, 0, 1) if self.hr_distance else 0.5
        ball_x, ball_y = slugger_ball_world(t, dist_k)
        if s <= 0:
            cam_x = cam_y = 0.0
        else:                                                          # the camera drifts after the ball a little, then chases it
            w = max(smooth((s - 0.45) / 0.7), 0.45 * smooth(s / 0.3))
            cam_x = (ball_x - lerp(CONTACT_POINT[0], 800, smooth((s - 0.8) / 0.6))) * w
            cam_y = (ball_y - lerp(CONTACT_POINT[1], 300, smooth(s / 0.5))) * 0.55 * w
        if 0 <= fx < 0.4:                                              # screen shake on impact
            shake = 20 * (1 - fx / 0.4)
            cam_x += random.uniform(-shake, shake)
            cam_y += random.uniform(-shake, shake)

        art = self.slugger
        surf.blit(art["sky"], (0, 0))

        def scroll(image, speed, y):                           # repeating layer that scrolls at its own speed (parallax)
            x0 = -((cam_x * speed) % LOGICAL_W)
            surf.blit(image, (int(x0), int(y)))
            surf.blit(image, (int(x0 + LOGICAL_W), int(y)))

        stands_y = 340 - cam_y * 0.6
        scroll(art["skyline"], 0.35, stands_y - 200)           # skyline sits right behind the stands (same height, slower scroll)
        scroll(art["stands"], 0.5, stands_y)
        ground_y = BATTER_FEET[1] - cam_y
        pygame.draw.rect(surf, (34, 84, 48), (0, stands_y + 260, LOGICAL_W, max(0, ground_y - stands_y - 260)))
        scroll(art["grass"], 1.0, ground_y)
        pygame.draw.rect(surf, (44, 108, 44), (0, ground_y + 240, LOGICAL_W, LOGICAL_H))

        draw_side_batter(surf, (cam_x, cam_y), t, self.team_color, self.skin)
        if not contacted:                                      # the slow-motion pitch
            pygame.draw.circle(surf, WHITE, (ball_x - cam_x, ball_y - cam_y), 14)
            pygame.draw.circle(surf, (204, 51, 51), (ball_x - cam_x, ball_y - cam_y), 14, 2)
        else:
            if s > 0.1:                                        # speed lines
                for i in range(14):
                    y = (i * 97 + 41) % 640 + 40
                    x = ((i * 211 - cam_x * 1.7) % (LOGICAL_W + 400)) - 200
                    pygame.draw.line(surf, (235, 240, 255), (x, y), (x + 140 + (i % 3) * 60, y), 2)
            draw_explosion(surf, CONTACT_POINT[0] - cam_x, CONTACT_POINT[1] - cam_y, fx)
            for k in range(12, 0, -1):                         # fiery trail = where the ball was a moment ago
                px, py = slugger_ball_world(max(SLUGGER_HIT_TIME, t - k * 0.03), dist_k)
                pygame.draw.circle(surf, (255, 90 + k * 12, 30), (px - cam_x, py - cam_y), max(2, int(18 - k * 1.1)))
            radius = int(lerp(20, 7, clamp(s / 2.2, 0, 1)))    # the ball shrinks as it leaves the park
            pygame.draw.circle(surf, WHITE, (ball_x - cam_x, ball_y - cam_y), radius)
            if fx < 0.18:                                      # white flash on contact (holds through the hit-stop, then fades)
                flash = pygame.Surface((LOGICAL_W, LOGICAL_H))
                flash.fill(WHITE)
                flash.set_alpha(int(230 * (1 - fx / 0.18)))
                surf.blit(flash, (0, 0))
            if s < 1.4:
                draw_text(surf, "PERFECT PERFECT!", 640, 170, int(78 + 8 * math.sin(fx * 14)), GOLD)
            else:
                draw_text(surf, f"HOME RUN!  {self.hr_distance} FT" if self.hr_distance else "HOME RUN!", 640, 170, 84, WHITE)
        pygame.draw.rect(surf, BLACK, (0, 0, LOGICAL_W, 48))                  # cinematic bars
        pygame.draw.rect(surf, BLACK, (0, LOGICAL_H - 48, LOGICAL_W, 48))

    # ---- pause menu + animation gallery ----------------------------------------
    PAUSE_OPTIONS = ("Resume", "Difficulty", "Animations", "Restart Game", "Quit to Title")
    BACK_RECT = pygame.Rect(60, 650, 200, 46)
    PREVIEW_RECT = pygame.Rect(480, 130, 740, 416)           # 16:9 window the gallery plays animations in

    def pause_rects(self):
        return [pygame.Rect(450, 250 + i * 62, 380, 52) for i in range(len(self.PAUSE_OPTIONS))]

    def gallery_rects(self):
        return [pygame.Rect(60, 150 + i * 76, 380, 64) for i in range(len(ANIMATIONS))]

    def toggle_pause(self):
        self.paused = not self.paused
        self.pause_screen, self.pause_index, self.anim_clock = "main", 0, 0.0

    def pause_choose(self, index):
        option = self.PAUSE_OPTIONS[index]
        if option == "Resume":
            self.paused = False
        elif option == "Difficulty":                         # cycle Easy -> Medium -> Hard, takes effect on the next pitch
            names = list(DIFFICULTIES)
            self.set_difficulty(names[(names.index(self.difficulty) + 1) % len(names)])
        elif option == "Animations":
            self.pause_screen, self.anim_clock = "anims", 0.0
        elif option == "Restart Game":
            self.configure(self.team_name, self.team_color, self.difficulty, self.innings, self.home_logo)     # a fresh game (also unpauses)
        else:
            self.paused, self.quit_to_menu = False, True

    def pause_key(self, key):
        if key == pygame.K_p:
            return self.toggle_pause()
        if self.pause_screen == "main":
            if key == pygame.K_UP:
                self.pause_index = (self.pause_index - 1) % len(self.PAUSE_OPTIONS)
            elif key == pygame.K_DOWN:
                self.pause_index = (self.pause_index + 1) % len(self.PAUSE_OPTIONS)
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                self.pause_choose(self.pause_index)
        else:
            if key == pygame.K_UP:
                self.anim_index, self.anim_clock = (self.anim_index - 1) % len(ANIMATIONS), 0.0
            elif key == pygame.K_DOWN:
                self.anim_index, self.anim_clock = (self.anim_index + 1) % len(ANIMATIONS), 0.0
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                self.anim_clock = 0.0                        # replay
            elif key in (pygame.K_BACKSPACE, pygame.K_LEFT):
                self.pause_screen = "main"

    def pause_hover(self, pos):
        self.mouse = pos
        if self.pause_screen == "main":
            for i, rect in enumerate(self.pause_rects()):
                if rect.collidepoint(pos):
                    self.pause_index = i

    def pause_click(self, pos):
        self.mouse = pos
        if self.pause_screen == "main":
            for i, rect in enumerate(self.pause_rects()):
                if rect.collidepoint(pos):
                    self.pause_index = i
                    self.pause_choose(i)
                    return
        else:
            if self.BACK_RECT.collidepoint(pos):
                self.pause_screen = "main"
            elif self.PREVIEW_RECT.collidepoint(pos):
                self.anim_clock = 0.0
            for i, rect in enumerate(self.gallery_rects()):
                if rect.collidepoint(pos):
                    self.anim_index, self.anim_clock = i, 0.0

    def draw_pause_button(self, surf, rect, label, selected):
        pygame.draw.rect(surf, TEAL if selected else (34, 42, 80), rect, border_radius=12)
        pygame.draw.rect(surf, WHITE if selected else (110, 120, 160), rect, 2, border_radius=12)
        draw_text(surf, label, rect.centerx, rect.centery + 8, 22)

    def draw_pause(self, surf):
        if self.pause_screen == "anims":
            return self.draw_gallery(surf)
        shade = pygame.Surface((LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 170))
        surf.blit(shade, (0, 0))
        draw_text(surf, "PAUSED", 640, 205, 64, GOLD)
        for i, (rect, option) in enumerate(zip(self.pause_rects(), self.PAUSE_OPTIONS)):
            label = f"DIFFICULTY: {self.difficulty.upper()}" if option == "Difficulty" else option.upper()
            self.draw_pause_button(surf, rect, label, i == self.pause_index)
        draw_text(surf, "P: resume   |   UP/DOWN + ENTER: choose   |   ESC: quit the game", 640, 640, 14, (200, 205, 225))
        draw_text(surf, "Difficulty changes take effect on the next pitch", 640, 665, 13, (200, 205, 225))

    def draw_gallery(self, surf):
        """Every animation, on demand: pick one on the left and it loops in the window on the right."""
        surf.fill((12, 16, 36))
        draw_text(surf, "ANIMATIONS", 640, 92, 46, GOLD)
        for i, (rect, (name, _, _)) in enumerate(zip(self.gallery_rects(), ANIMATIONS)):
            selected = i == self.anim_index
            pygame.draw.rect(surf, TEAL if selected else (34, 42, 80), rect, border_radius=10)
            pygame.draw.rect(surf, WHITE if selected else (110, 120, 160), rect, 2, border_radius=10)
            draw_text(surf, f"{i + 1}. {name}", rect.x + 18, rect.centery + 8, 20, align="left")
        name, info, duration = ANIMATIONS[self.anim_index]
        t = min(self.anim_clock % (duration + 0.8), duration)             # plays, pauses a moment, loops
        scene = self.preview_scene
        (self.scene_slugger, self.scene_dive, self.scene_leap, self.scene_broken_bat,
         self.scene_fan, self.scene_board)[self.anim_index](scene, t)
        surf.blit(pygame.transform.smoothscale(scene, self.PREVIEW_RECT.size), self.PREVIEW_RECT.topleft)
        pygame.draw.rect(surf, WHITE, self.PREVIEW_RECT.inflate(8, 8), 3)
        cx = self.PREVIEW_RECT.centerx
        draw_text(surf, name, cx, 590, 26, GOLD)
        draw_text(surf, info, cx, 620, 16)
        self.draw_pause_button(surf, self.BACK_RECT, "BACK", False)
        draw_text(surf, "UP/DOWN: choose   ENTER or click window: replay   BACKSPACE: back   P: resume", cx, 690, 13, (200, 205, 225))

    # ---- the gallery scenes: each one re-creates a rare animation at time t ------
    def scene_slugger(self, scene, t):
        self.draw_slugger_scene(scene, clamp(t, 0, SLUGGER_TIME))

    def scene_dive(self, scene, t):
        """A ground ball up the middle: the shortstop dives, then throws to first."""
        self.blit_field_scene(scene, t * 1.0, 0.55)
        s = FIELDER_SCALE
        for name, post in FIELDER_POSTS.items():
            if name != "SS":
                draw_person(scene, post[0], post[1], s)
        end, direction = (447, 437), -1
        k = clamp((t - 0.3) / 0.65, 0, 1)
        k = k * k * (3 - 2 * k)
        fx, fy = lerp(540, end[0], k), lerp(395, end[1], k)
        dive_t = t - 0.55
        rx, ry = point_on_path(clamp((t - 0.9) * 0.7, 0, 1))
        draw_person(scene, rx, ry, 1.6, (240, 240, 240), self.team_color, skin=self.skin)
        lying = 0 <= dive_t < DIVE_TIME + DIVE_RECOVERY * 0.6
        if lying:
            draw_dive(scene, fx, fy, s, FIELD_BODY, FIELD_CAP, dive_t, direction)
        else:
            draw_person(scene, fx, fy, s)
        glove = dive_glove(end[0], end[1], s, direction)
        held = (fx + 8, fy - 18)
        if t < 1.1:                                                       # the grounder bounces into the glove
            u = t / 1.1
            draw_loose_ball(scene, lerp(HOME[0], glove[0], u), lerp(HOME[1] - 14, glove[1], u) - abs(math.sin(u * math.pi * 5)) * 12 * (1 - u))
        elif t < 1.9:
            draw_loose_ball(scene, *(dive_glove(fx, fy, s, direction) if lying else held))
        elif t < 2.4:                                                     # the throw to first
            u = (t - 1.9) / 0.5
            draw_loose_ball(scene, lerp(held[0], 913, u), lerp(held[1], 434, u) - 25 * math.sin(math.pi * u))
        else:
            draw_loose_ball(scene, 913, 434)
        if 0 <= dive_t < DIVE_TIME + DIVE_RECOVERY:
            draw_text(scene, "DIVING STOP!", fx, fy - 70, 28, GOLD)
        if t >= 2.45:
            draw_text(scene, "OUT at FIRST", 640, 140, 56)

    def scene_leap(self, scene, t):
        """A deep fly ball to center: the fielder leaps and makes the catch at the top of his jump."""
        self.blit_field_scene(scene, t * 1.0, 0.55)
        s = FIELDER_SCALE
        for name, post in FIELDER_POSTS.items():
            if name != "CF":
                draw_person(scene, post[0], post[1], s)
        draw_person(scene, HOME[0], HOME[1], 1.6, (240, 240, 240), self.team_color, skin=self.skin)
        flight, land = 1.8, (640, 250)
        k = clamp(t / 1.2, 0, 1)
        k = k * k * (3 - 2 * k)
        fx, fy = lerp(590, land[0], k), lerp(300, land[1], k)
        leap_t = t - (flight - LEAP_TIME / 2)
        jumping = 0 <= leap_t < LEAP_TIME
        if jumping:
            draw_leap(scene, fx, fy, s, FIELD_BODY, FIELD_CAP, leap_t)
            draw_text(scene, "LEAPING CATCH!", fx, fy - 105, 28, GOLD)
        else:
            draw_person(scene, fx, fy, s)
        if t < flight:
            u = t / flight
            z = 170 * math.sin(math.pi * u) + LEAP_GLOVE_Z * u ** 3
            draw_loose_ball(scene, lerp(HOME[0], land[0], u), lerp(HOME[1] - 10, land[1], u) - z - 4)
        elif jumping:
            draw_loose_ball(scene, *leap_glove(fx, fy, s, leap_t))
        else:
            draw_loose_ball(scene, fx + 8, fy - 18)
        if t >= flight + 0.6:
            draw_text(scene, "FLY OUT", 640, 140, 56)

    def scene_broken_bat(self, scene, t):
        """Weak contact: the bat snaps and the barrel spins away toward third."""
        self.blit_field_scene(scene, t * 1.0, 0.55)
        for name, post in FIELDER_POSTS.items():
            draw_person(scene, post[0], post[1], FIELDER_SCALE)
        contact = 0.5
        bt = t - contact
        draw_person(scene, HOME[0], HOME[1], 1.6, (240, 240, 240), self.team_color, skin=self.skin)
        if bt < 0:                                                        # the swing and the pitch coming in
            angle = lerp(-1.9, 0.4, clamp(t / contact, 0, 1))
            hx, hy = HOME[0] + 6, HOME[1] - 22
            draw_real_bat(scene, (hx, hy), (hx + 60 * math.cos(angle), hy + 60 * math.sin(angle)), 7)
            draw_loose_ball(scene, lerp(MOUND[0], HOME[0], t / contact), lerp(MOUND[1], HOME[1] - 20, t / contact))
        else:
            draw_bat_stub(scene, HOME[0], HOME[1])
            direction = unit(B3[0] - HOME[0], B3[1] - HOME[1])
            draw_broken_bat(scene, HOME[0], HOME[1], bt, direction)
            u = clamp(bt / 1.0, 0, 1)                                     # the weak grounder dribbles out
            draw_loose_ball(scene, lerp(HOME[0], 470, u), lerp(HOME[1] - 14, 520, u) - abs(math.sin(u * math.pi * 4)) * 10 * (1 - u))
            if bt < 1.3:
                draw_text(scene, "BROKEN BAT!", 640, 112, 40, GOLD)

    def scene_homer(self, scene, t, board):
        """A home run in the batting view. board=False: it clears the wall and a small fan catches it.
        board=True: it smacks the scoreboard, which rocks and flickers."""
        bat = self.preview_bat
        self.blit_bat_scene(bat, t, 0.4)
        contact, flight = 0.45, 1.6
        sideways = -5 if board else 150
        bt = t - (contact + flight)                                       # seconds since the ball reached the wall
        saved = self.board_time
        self.board_time = bt if board and bt >= 0 else -1.0
        draw_bat_scoreboard(bat, self)
        self.board_time = saved
        draw_bat_fielders(bat)
        pitch = Pitch("Fastball", contact, 95, True)
        swing = t - (contact - 0.12)
        draw_batter(bat, swing if swing >= 0 else -1, self.team_color, self.skin, t, 1.0)
        if t < contact:
            x, y, r = pitch_position(pitch, t / contact)
            draw_bat_ball(bat, x, y, r)
        else:
            hit = Hit("HR", "perfect", BAT_RELEASE_POINT[0] + 8, 332, sideways, flight, 0, distance=420)
            hit.time = clamp(t - contact, 0, flight)
            u = hit.time / flight
            if not board:
                draw_fan(bat, hit.start_x + hit.sideways, hr_end_y(hit.distance), clamp((u - 0.7) / 0.3, 0, 1), t, u >= 1)
            if u < 1:
                x, y, r = hr_position(hit)
                draw_bat_ball(bat, x, y, r)
            else:
                draw_text(bat, "HOME RUN!", 385, 230, 40)
                draw_text(bat, "Off the scoreboard!" if board else "Gone!  A fan makes the catch!", 385, 262, 16)
        bat_h = int(LOGICAL_W * BAT_H / BAT_W)
        scene.fill((14, 17, 22))
        scene.blit(pygame.transform.smoothscale(bat, (LOGICAL_W, bat_h)), (0, (LOGICAL_H - bat_h) // 2))

    def scene_fan(self, scene, t):
        self.scene_homer(scene, t, False)

    def scene_board(self, scene, t):
        self.scene_homer(scene, t, True)

    # ---- batting view ---------------------------------------------------------
    def draw_bat_view(self, surf):
        self.blit_bat_scene(surf)
        draw_bat_scoreboard(surf, self)
        draw_base_indicator(surf, 60, 88, self.bases, self.steal_armed)
        draw_bat_fielders(surf)
        if self.state == "WIND_UP":
            delivery = min(1, self.state_time / WIND_UP_TIME)
        elif self.state == "PITCH":
            delivery = 1 + 0.3 * smooth(self.pitch.time / PITCH_FOLLOW_TIME)      # the arm carries on through after the release
        else:
            delivery = 0 if self.state == "WAIT" else 1.3                # standing between pitches, holding the finish after the throw
        hand = draw_bat_pitcher(surf, delivery, self.fielder_skins["P"])
        if self.state == "WIND_UP":
            draw_bat_ball(surf, hand[0], hand[1], 3)
        if self.state == "PITCH":
            u = self.pitch.time / self.pitch.duration
            x, y, r = pitch_position(self.pitch, u)
            if u < RELEASE_BLEND:                                        # the ball leaves his hand and settles onto its path
                hx, hy = pitcher_pose(1.0)["screen_hand"]
                k = smooth(u / RELEASE_BLEND)
                x, y = lerp(hx, x, k), lerp(hy, y, k)
            draw_bat_ball(surf, x, y, r)
        if self.fan and self.state in ("BALL_IN_FLIGHT", "MESSAGE"):     # rare animation: a fan catches the home run
            u = min(1.0, self.hit.time / self.hit.flight)
            draw_fan(surf, self.fan[0], self.fan[1], clamp((u - 0.7) / 0.3, 0, 1), self.clock, u >= 1)
        if self.state == "BALL_IN_FLIGHT":
            x, y, r = hr_position(self.hit)
            draw_bat_ball(surf, x, y, r)
        draw_batter(surf, self.swing_clock, self.team_color, self.skin, self.clock, self.load_amount(), self.settle,
                    self.finish_big if self.swing_clock < 0 else bool(self.hit and self.hit.quality == "perfect_perfect"))
        if self.pitch and (self.state in ("PITCH", "BALL_IN_FLIGHT") or self.state == "MESSAGE" and self.state_time < 1.4):
            self.draw_meter(surf)
        for p in self.confetti:
            surf.fill(p["color"], (p["x"], p["y"], p["size"], p["size"]))
        draw_text(surf, "SPACE / click: swing", 8, 14, 11, WHITE, align="left")
        draw_text(surf, self.difficulty.upper(), 8, 28, 10, GOLD, align="left")
        if any(self.bases) and self.state in ("WAIT", "WIND_UP"):
            if self.steal_armed:
                draw_text(surf, "STEAL ON!  (S to cancel)", 8, 42, 10, GREEN, align="left")
            else:
                draw_text(surf, "S: steal", 8, 42, 10, (200, 205, 225), align="left")
        draw_seam_window(surf, self)
        if self.state == "MESSAGE":
            size = 48 + math.sin(self.state_time * 10) * 5 if self.celebrating else 40
            draw_text(surf, self.message, 385, 230, int(size))
            if self.sub_message:
                draw_text(surf, self.sub_message, 385, 262, 16)

    def draw_meter(self, surf):
        """The timing bar: the white marker sweeps right; swing when it is over the green.
        The green sits earlier for inside pitches and later for outside pitches."""
        pitch, bar_x, bar_y, bar_w = self.pitch, 235, 138, 300
        scale = bar_w / (pitch.duration + METER_EXTRA_TIME)               # pixels per second
        center = bar_x + (pitch.duration + pitch.offset) * scale
        pygame.draw.rect(surf, (20, 20, 20), (bar_x - 4, bar_y - 4, bar_w + 8, 22))
        pygame.draw.rect(surf, (34, 34, 34), (bar_x, bar_y, bar_w, 14))
        for window, color in ((self.win_contact, (58, 74, 106)), (self.win_good, (212, 168, 42)),
                              (self.win_perfect, (53, 199, 89)), (self.win_pp, (184, 255, 203))):
            left = max(bar_x, center - window * scale)
            right = min(bar_x + bar_w, center + window * scale)
            pygame.draw.rect(surf, color, (left, bar_y, right - left, 14))
        marker_time = pitch.swing_time if pitch.swung else min(pitch.time, pitch.duration + METER_EXTRA_TIME)
        pygame.draw.rect(surf, WHITE, (bar_x + marker_time * scale - 2, bar_y - 5, 4, 24))
        draw_text(surf, f"{pitch.mph} MPH", bar_x + 30, bar_y - 8, 12)                  # above the bar so the big
        draw_text(surf, LOC_NAMES[pitch.zone + 1].upper(), bar_x + bar_w - 30, bar_y - 8, 12, (200, 205, 225))   # pitch type stays hidden until after the pitch
        if pitch.label:
            color = GREEN if pitch.label.startswith("PERFECT") else GOLD if pitch.label == "GOOD" else RED
            draw_text(surf, pitch.label, 385, bar_y + 40, 22, color)

    def draw_game_over(self, surf):
        """Final score, the line score, and the game stats (drawn full-screen on the 1280x720 canvas)."""
        shade = pygame.Surface((LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 205))
        surf.blit(shade, (0, 0))
        draw_text(surf, f"FINAL  {self.team_name[:10]} {self.runs}  -  {self.cpu_runs} CPU", 640, 110, 42)
        result = f"{self.team_name} win!" if self.runs > self.cpu_runs else "CPU wins" if self.runs < self.cpu_runs else "Tie game"
        draw_text(surf, result, 640, 158, 30, GOLD)
        draw_logo(surf, self.home_logo, 236, 70, 72)
        draw_logo(surf, self.cpu_logo, 972, 70, 72)
        # line score
        n = max(len(self.my_line), len(self.cpu_line), 1)
        col_w = min(56, 560 // n)
        name_w, total_w = 220, 220 + n * col_w + 70
        x0 = 640 - total_w / 2
        pygame.draw.rect(surf, (110, 120, 160), (x0 - 12, 196, total_w + 24, 146), 2, border_radius=8)
        for i in range(n):
            draw_text(surf, str(i + 1), x0 + name_w + i * col_w + col_w / 2, 236, 18, GOLD)
        draw_text(surf, "R", x0 + name_w + n * col_w + 35, 236, 18, GOLD)
        rows = ((self.team_name[:12], self.my_line, self.runs, self.home_logo), ("CPU", self.cpu_line, self.cpu_runs, self.cpu_logo))
        for row, (label, line, total, logo) in enumerate(rows):
            y = 282 + row * 44
            draw_logo(surf, logo, x0 + 6, y - 24, 30)
            draw_text(surf, label, x0 + 42, y, 16, align="left")
            for i, value in enumerate(line):
                draw_text(surf, str(value), x0 + name_w + i * col_w + col_w / 2, y, 20)
            draw_text(surf, str(total), x0 + name_w + n * col_w + 35, y, 24, GOLD)
        # stats
        st = self.stats
        left = [("Hits", st["hits"]), ("Home runs", st["hr"]), ("Perfect swings", st["perfect"])]
        right = [("Strikeouts", st["k"]), ("Walks", st["bb"]), ("Stolen bases", f"{st['steals']}/{st['steal_att']}")]
        draw_text(surf, "YOUR STATS", 640, 392, 20, GOLD)
        for i, (label, value) in enumerate(left):
            draw_text(surf, f"{label}: {value}", 470, 436 + i * 36, 22, align="left")
        for i, (label, value) in enumerate(right):
            draw_text(surf, f"{label}: {value}", 790, 436 + i * 36, 22, align="left")
        draw_text(surf, "Click or press SPACE for the title screen", 640, 620, 18)

    # ---- overhead field view --------------------------------------------------
    def draw_field_view(self, surf):
        self.blit_field_scene(surf)
        fp = self.fp
        if fp:
            self.draw_dust(surf)                                          # dust / grass bits under running feet (behind the people)
            people = []                                                   # (y, drawing function) so lower people overlap higher ones
            button = self.field_button()
            if button:                                                    # the RUN / SLIDE circle sits on the ground, under his feet
                draw_button(surf, button[1], button[2], button[0], SLIDE_GREEN if button[0] == "Slide" else TEAL)
            for n, other in enumerate(fp.others):
                if other["pos"] < 4:
                    x, y = point_on_path(other["pos"])
                    sway, bob = self.gait(("o", n))
                    people.append((y, lambda x=x, y=y, sk=other["skin"], sw=sway, bo=bob: draw_person(
                        surf, x, y, 1.3, (235, 235, 235), self.team_color, skin=sk,
                        shadow_color=self.shadow_at(x, y), sway=sw, bob=bo)))
            for i, f in enumerate(fp.fielders):
                people.append((f.y, lambda i=i, f=f: self.draw_fielder(surf, i, f)))
            r = fp.runner
            rx, ry = self.runner_xy()
            if not (fp.walk and fp.walk["done"]):                         # (once he is in the dugout he is gone)
                people.append((ry, lambda: self.draw_runner(surf, rx, ry)))
            for _, draw in sorted(people, key=lambda p: p[0]):
                draw()
            self.draw_field_ball(surf)
            self.draw_rare_effects(surf)
            if r.moving and r.run_through:
                draw_text(surf, "Running through!", rx, ry - 52, 16, GREEN)
        self.draw_field_hud(surf)

    def draw_fielder(self, surf, i, f):
        """A fielder: standing, swaying as he runs, or (rare animations) diving / leaping. His shadow and dust match the ground."""
        fp = self.fp
        ground = TERRAIN[terrain_at(f.x, f.y)]
        skin = self.fielder_skins[f.name]
        if fp.dive and fp.dive["idx"] == i and fp.dive["t"] < DIVE_TIME + DIVE_RECOVERY * 0.6:
            draw_dive(surf, f.x, f.y, FIELDER_SCALE, FIELD_BODY, FIELD_CAP, fp.dive["t"], fp.dive["dir"], skin=skin,
                      shadow_color=ground["shadow"], dust_color=ground["dust"][0])
        elif fp.leap and i == fp.chaser:
            draw_leap(surf, f.x, f.y, FIELDER_SCALE, FIELD_BODY, FIELD_CAP, fp.leap["t"], skin=skin, shadow_color=ground["shadow"])
        else:
            sway, bob = self.gait(("f", i))
            draw_person(surf, f.x, f.y, FIELDER_SCALE, skin=skin, shadow_color=ground["shadow"], sway=sway, bob=bob)

    def draw_rare_effects(self, surf):
        """Banners and the flying bat for the rare animations, plus the white CAUGHT! effect and the landing dust."""
        fp = self.fp
        if fp.broken:
            draw_broken_bat(surf, HOME[0], HOME[1], fp.broken["t"], fp.broken["dir"])
            if fp.broken["t"] < 1.3:
                draw_text(surf, "BROKEN BAT!", 640, 112, 40, GOLD)
        if fp.dive:
            f = fp.fielders[fp.dive["idx"]]
            draw_text(surf, "DIVING STOP!", f.x, f.y - 70, 28, GOLD)
        if fp.leap:
            f = fp.fielders[fp.chaser]
            draw_text(surf, "LEAPING CATCH!", f.x, f.y - 105, 28, GOLD)
        if fp.catch and fp.catch["t"] < CATCH_FX_TIME:           # every fly out: white, so it never looks like a rare (gold) animation
            t = fp.catch["t"]
            f = fp.fielders[fp.chaser]
            if fp.leap:
                gx, gy = leap_glove(f.x, f.y, FIELDER_SCALE, fp.leap["t"])
            else:
                gx, gy = f.x + 8, f.y - 18
            if t < 0.45:                                         # flash ring + sparks at the glove
                k = t / 0.45
                pygame.draw.circle(surf, WHITE, (gx, gy), int(8 + 46 * k), max(1, int(5 * (1 - k))))
                for j in range(8):
                    a = j * math.pi / 4
                    pygame.draw.line(surf, WHITE, (gx + math.cos(a) * (14 + 40 * k), gy + math.sin(a) * (14 + 40 * k)),
                                     (gx + math.cos(a) * (24 + 50 * k), gy + math.sin(a) * (24 + 50 * k)), 2)
            top = f.y - (135 if fp.leaped else 75)
            draw_text(surf, "CAUGHT!", f.x, top - 14 * min(1, t / 0.3), 30, WHITE)
        if fp.landed and fp.landed["t"] < 0.8:                   # dust where the ball hit the grass
            t, lx, ly = fp.landed["t"], fp.landed["x"], fp.landed["y"]
            dust_color = TERRAIN[terrain_at(lx, ly)]["dust"][0]          # the puff is the colour of the ground it hit
            for j in range(8):
                a = j * math.pi / 4
                r = (3 + 8 * t) * max(0.0, 1 - t / 0.8)
                if r >= 1:
                    pygame.draw.circle(surf, dust_color, (lx + math.cos(a) * 34 * t, ly - 3 + math.sin(a) * 16 * t), r)

    def draw_runner(self, surf, x, y):
        r = self.fp.runner
        ring = (255, 255, 255) if r.turn_cooldown <= 0 else (150, 150, 150)       # grey ring = can't turn around yet
        if r.moving and not r.sliding:
            pygame.draw.ellipse(surf, ring, (x - 18, y - 6, 36, 14), 2)
        sway, bob = self.gait("runner")
        draw_person(surf, x, y, 1.6, (240, 240, 240), self.team_color, sliding=r.sliding, skin=self.fp.skin or SKIN_DEFAULT,
                    shadow_color=self.shadow_at(x, y), sway=sway, bob=bob)
        if self.fp.broken and r.pos == 0:                                        # still holding the stump of the bat
            draw_bat_stub(surf, x, y)

    def draw_field_ball(self, surf):
        ball = self.fp.ball
        if ball.mode == "held":
            x, y, z = ball.x + 8, ball.y - 14, 0
            fp = self.fp
            if fp.dive and fp.dive["idx"] == ball.holder and fp.dive["t"] < DIVE_TIME + DIVE_RECOVERY * 0.6:
                gx, gy = dive_glove(ball.x, ball.y, FIELDER_SCALE, fp.dive["dir"])       # ball is in the stretched-out glove
                x, y = gx, gy + 4
            elif fp.leap and ball.holder == fp.chaser:
                gx, gy = leap_glove(ball.x, ball.y, FIELDER_SCALE, fp.leap["t"])         # ball is in the glove up high
                x, y = gx, gy + 4
            ground_y = y
        else:
            x, y, z = ball.x, ball.y, ball.z
            ground_y = y
            pygame.draw.ellipse(surf, self.shadow_at(x, ground_y), (x - 6, ground_y - 2, 12, 5))
        pygame.draw.circle(surf, WHITE, (x, y - z - 4), 6)
        pygame.draw.circle(surf, (204, 51, 51), (x, y - z - 4), 6, 1)
        fp = self.fp
        if ball.mode == "held" and fp.catch and ball.holder == fp.chaser and fp.hit.kind == "FLY_OUT":
            pygame.draw.circle(surf, WHITE, (x, y - z - 4), 10 + int(2 * math.sin(self.clock * 12)), 2)    # white halo on the caught ball

    def draw_field_hud(self, surf):
        pygame.draw.rect(surf, (31, 35, 39), (410, 8, 460, 64), border_radius=8)
        pygame.draw.rect(surf, (102, 102, 102), (410, 8, 460, 64), 2, border_radius=8)
        draw_logo(surf, self.home_logo, 418, 18, 44)
        draw_logo(surf, self.cpu_logo, 818, 18, 44)
        for i in range(OUTS_PER_INNING):
            pygame.draw.circle(surf, (232, 232, 232), (476 + i * 20, 28), 7, 0 if i < self.outs else 2)
        draw_text(surf, f"INN {self.inning}/{self.innings}", 640, 34, 16, (232, 232, 232), outline=False)
        draw_text(surf, f"B{self.balls} S{self.strikes}", 810, 34, 16, (232, 232, 232), outline=False, align="right")
        score_line = f"{self.team_name} {self.runs}  -  {self.cpu_runs} CPU"
        score_size = 24
        while score_size > 12 and get_font(score_size).size(score_line)[0] > 330:     # shrink to fit the box
            score_size -= 1
        draw_text(surf, score_line, 640, 64, score_size, (232, 232, 232), outline=False)
        draw_text(surf, "RUN button / R: go to next base   S: slide   click runner: turn back", 12, 24, 15, WHITE, align="left")
        if self.state == "MESSAGE":
            draw_text(surf, self.message, 640, 140, 56)
            if self.sub_message:
                draw_text(surf, self.sub_message, 640, 180, 24)


# =============================================================================
# 5. THE START SCREEN  -  title, team name, home color, difficulty, game length
# =============================================================================

class Menu:
    def __init__(self):
        self.background = build_menu_background()
        self.title = build_title(TITLE_TEXT)
        self.name = DEFAULT_TEAM_NAME
        self.color_index = 0
        self.difficulty = DEFAULT_DIFFICULTY
        self.innings = DEFAULT_INNINGS
        self.t = 0.0
        self.flashes = []                                    # little camera flashes in the crowd
        self.mouse = (-1, -1)
        self.name_rect = pygame.Rect(320, 330, 440, 44)
        self.swatches = [(323 + i * 62, 448) for i in range(len(TEAM_COLORS))]
        self.diff_rects = {name: pygame.Rect(299 + i * 166, 514, 150, 42) for i, name in enumerate(DIFFICULTIES)}
        self.inning_rects = {n: pygame.Rect(822 + i * 56, 606, 48, 38) for i, n in enumerate(INNING_OPTIONS)}
        self.start_rect = pygame.Rect(400, 623, 280, 54)
        # logo drawing patch
        self.patch_rect = pygame.Rect(858, 330, 144, 144)          # 3 screen pixels per logo pixel
        self.pen_pos = [(852 + i * 26, 494) for i in range(len(PEN_COLORS) + 1)]     # last one is the eraser
        self.clear_rect = pygame.Rect(885, 516, 90, 24)
        self.logo = pygame.Surface((LOGO_PX, LOGO_PX), pygame.SRCALPHA)
        self.logo_drawn, self.pen, self.drawing, self.last_pt = False, 0, False, None
        if os.path.exists(LOGO_FILE):                              # bring back the logo you drew last time
            try:
                self.logo = pygame.transform.scale(pygame.image.load(LOGO_FILE).convert_alpha(), (LOGO_PX, LOGO_PX))
                self.logo_drawn = True
            except (pygame.error, FileNotFoundError):
                self.logo = pygame.Surface((LOGO_PX, LOGO_PX), pygame.SRCALPHA)
        self.load_settings()

    def load_settings(self):
        """Bring back the team name, color, difficulty and innings from last time (anything missing or invalid is ignored)."""
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        name = data.get("team_name")
        if isinstance(name, str) and name.strip():
            self.name = name[:MAX_NAME_LENGTH]
        labels = [label for label, _ in TEAM_COLORS]
        if data.get("team_color") in labels:
            self.color_index = labels.index(data["team_color"])
        if data.get("difficulty") in DIFFICULTIES:
            self.difficulty = data["difficulty"]
        if data.get("innings") in INNING_OPTIONS:
            self.innings = data["innings"]

    def save_settings(self):
        """Remember the start-screen choices (saved when you press PLAY BALL, just like the logo)."""
        data = {"team_name": self.name, "team_color": TEAM_COLORS[self.color_index][0],
                "difficulty": self.difficulty, "innings": self.innings}
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass

    def stroke(self, pos):
        """Paint on the logo patch with the pen (or erase)."""
        px = self.patch_rect
        pt = (int((pos[0] - px.x) / 3), int((pos[1] - px.y) / 3))
        erase = self.pen == len(PEN_COLORS)
        color = (0, 0, 0, 0) if erase else PEN_COLORS[self.pen] + (255,)
        width = 5 if erase else 3
        if self.last_pt:
            pygame.draw.line(self.logo, color, self.last_pt, pt, width)
        pygame.draw.circle(self.logo, color, pt, width // 2)
        self.last_pt = pt
        self.logo_drawn = True

    def click_logo_tools(self, pos):
        if self.patch_rect.collidepoint(pos):
            self.drawing, self.last_pt = True, None
            self.stroke(pos)
            return
        for i, (cx, cy) in enumerate(self.pen_pos):
            if math.hypot(pos[0] - cx, pos[1] - cy) <= 13:
                self.pen = i
        if self.clear_rect.collidepoint(pos):
            self.logo.fill((0, 0, 0, 0))
            self.logo_drawn = False

    def logo_for_game(self):
        """The finished logo for the game (and saves your drawing so it is here next time)."""
        if self.logo_drawn:
            try:
                pygame.image.save(self.logo, LOGO_FILE)
            except pygame.error:
                pass
            return compose_logo(self.logo, self.team_color)
        return build_default_logo(self.team_name, self.team_color)

    def draw_logo_tools(self, surf):
        draw_text(surf, "DRAW YOUR LOGO", 930, 318, 16, GOLD)
        outer, inner = self.patch_rect.inflate(16, 16), self.patch_rect
        pygame.draw.rect(surf, WHITE, outer, border_radius=20)
        pygame.draw.rect(surf, self.team_color, inner, border_radius=14)
        if self.logo_drawn:
            surf.blit(pygame.transform.scale(self.logo, inner.size), inner.topleft)
        else:
            preview = build_default_logo(self.name, self.team_color)       # a faint preview of the default badge
            preview.set_alpha(100)
            surf.blit(pygame.transform.scale(preview, inner.size), inner.topleft)
            draw_text(surf, "click + drag to draw", 930, inner.bottom - 8, 12, WHITE)
        pygame.draw.rect(surf, (255, 255, 255), inner.inflate(-8, -8), 1, border_radius=11)       # stitching
        for i, (cx, cy) in enumerate(self.pen_pos):
            selected = i == self.pen
            if i == len(PEN_COLORS):                                          # eraser
                pygame.draw.circle(surf, (90, 92, 104), (cx, cy), 10)
                pygame.draw.line(surf, WHITE, (cx - 4, cy - 4), (cx + 4, cy + 4), 2)
                pygame.draw.line(surf, WHITE, (cx - 4, cy + 4), (cx + 4, cy - 4), 2)
            else:
                pygame.draw.circle(surf, PEN_COLORS[i], (cx, cy), 10)
                pygame.draw.circle(surf, (120, 125, 145), (cx, cy), 11, 1)
            if selected:
                pygame.draw.circle(surf, GOLD, (cx, cy), 14, 3)
        hover = self.clear_rect.collidepoint(self.mouse)
        pygame.draw.rect(surf, (60, 70, 110) if hover else (34, 42, 80), self.clear_rect, border_radius=8)
        pygame.draw.rect(surf, (110, 120, 160), self.clear_rect, 2, border_radius=8)
        draw_text(surf, "CLEAR", self.clear_rect.centerx, self.clear_rect.centery + 5, 11)

    @property
    def team_name(self):
        return self.name.strip() or "HOME"

    @property
    def team_color(self):
        return TEAM_COLORS[self.color_index][1]

    def handle_event(self, event, to_canvas):
        """Returns True when the player chooses to start the game."""
        if event.type == pygame.MOUSEMOTION:
            self.mouse = to_canvas(event.pos)
            if self.drawing and event.buttons[0]:
                self.stroke(self.mouse)
        elif event.type == pygame.MOUSEBUTTONUP:
            self.drawing, self.last_pt = False, None
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self.mouse = to_canvas(event.pos)
            self.click_logo_tools(pos)
            for i, (cx, cy) in enumerate(self.swatches):
                if math.hypot(pos[0] - cx, pos[1] - cy) <= 26:
                    self.color_index = i
            for name, rect in self.diff_rects.items():
                if rect.collidepoint(pos):
                    self.difficulty = name
            for n, rect in self.inning_rects.items():
                if rect.collidepoint(pos):
                    self.innings = n
            if self.start_rect.collidepoint(pos):
                return True
        elif event.type == pygame.KEYDOWN:
            names = list(DIFFICULTIES)
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return True
            elif event.key == pygame.K_BACKSPACE:
                self.name = self.name[:-1]
            elif event.key == pygame.K_LEFT:
                self.color_index = (self.color_index - 1) % len(TEAM_COLORS)
            elif event.key == pygame.K_RIGHT:
                self.color_index = (self.color_index + 1) % len(TEAM_COLORS)
            elif event.key == pygame.K_UP:
                self.difficulty = names[(names.index(self.difficulty) - 1) % len(names)]
            elif event.key == pygame.K_DOWN:
                self.difficulty = names[(names.index(self.difficulty) + 1) % len(names)]
            elif event.key == pygame.K_TAB:
                self.innings = INNING_OPTIONS[(INNING_OPTIONS.index(self.innings) + 1) % len(INNING_OPTIONS)]
            elif event.unicode and len(self.name) < MAX_NAME_LENGTH and (event.unicode.isalnum() or event.unicode in " -'.!&"):
                self.name += event.unicode.upper()
        return False

    def update(self, dt):
        self.t += dt
        if random.random() < dt * 8:
            self.flashes.append(dict(x=random.uniform(20, LOGICAL_W - 20), y=random.uniform(176, 300), life=0.4, max=0.4))
        for f in self.flashes:
            f["life"] -= dt
        self.flashes = [f for f in self.flashes if f["life"] > 0]

    def draw(self, surf):
        surf.blit(self.background, (0, 0))
        for f in self.flashes:                               # camera flashes popping in the stands
            b = f["life"] / f["max"]
            color, r = (int(255 * b),) * 3, int(3 + 7 * b)
            pygame.draw.circle(surf, color, (f["x"], f["y"]), r)
            pygame.draw.line(surf, color, (f["x"] - 2 * r, f["y"]), (f["x"] + 2 * r, f["y"]), 2)
            pygame.draw.line(surf, color, (f["x"], f["y"] - 2 * r), (f["x"], f["y"] + 2 * r), 2)
        draw_bolt(surf, 120, 150, 190, False, self.t)
        draw_bolt(surf, 1160, 150, 190, True, self.t)
        draw_title(surf, self.title, 640, 150 + 4 * math.sin(self.t * 2), self.t)

        panel = pygame.Surface((840, 424), pygame.SRCALPHA)
        pygame.draw.rect(panel, (10, 14, 34, 205), panel.get_rect(), border_radius=18)
        pygame.draw.rect(panel, (255, 255, 255, 60), panel.get_rect(), 2, border_radius=18)
        surf.blit(panel, (220, 272))

        # team name
        draw_text(surf, "TEAM NAME", 540, 318, 16, GOLD)
        pygame.draw.rect(surf, (22, 28, 60), self.name_rect, border_radius=8)
        pygame.draw.rect(surf, GOLD, self.name_rect, 2, border_radius=8)
        if self.name:
            draw_text(surf, self.name, 540, 362, 26)
        else:
            draw_text(surf, "type a name", 540, 360, 20, (140, 150, 180), outline=False)
        if int(self.t * 2) % 2 == 0:
            width = get_font(26).size(self.name)[0] if self.name else 0
            pygame.draw.rect(surf, GOLD, (540 + width / 2 + 4, 337, 3, 30))

        # home color
        draw_text(surf, f"HOME COLOR: {TEAM_COLORS[self.color_index][0].upper()}", 540, 412, 16, GOLD)
        for i, ((cx, cy), (_, color)) in enumerate(zip(self.swatches, TEAM_COLORS)):
            selected = i == self.color_index
            hover = math.hypot(self.mouse[0] - cx, self.mouse[1] - cy) <= 26
            r = 22 if selected or hover else 20
            pygame.draw.circle(surf, BLACK, (cx, cy + 3), r + 2)
            pygame.draw.circle(surf, color, (cx, cy), r)
            if selected:
                pygame.draw.circle(surf, WHITE, (cx, cy), r + 5, 3)
            else:
                pygame.draw.circle(surf, (120, 125, 145), (cx, cy), r + 1, 2)

        # difficulty
        draw_text(surf, "DIFFICULTY", 540, 500, 16, GOLD)
        for name, rect in self.diff_rects.items():
            selected, hover = name == self.difficulty, rect.collidepoint(self.mouse)
            pygame.draw.rect(surf, TEAL if selected else (60, 70, 110) if hover else (34, 42, 80), rect, border_radius=10)
            pygame.draw.rect(surf, WHITE if selected else (110, 120, 160), rect, 2, border_radius=10)
            draw_text(surf, name.upper(), rect.centerx, rect.centery + 8, 20)
        for i, line in enumerate(DIFFICULTIES[self.difficulty]["blurb"]):
            draw_text(surf, line, 540, 585 + i * 20, 14, (220, 225, 240))

        # play button
        hover = self.start_rect.collidepoint(self.mouse)
        rect = self.start_rect.inflate(int(6 * math.sin(self.t * 5)) + 6, int(3 * math.sin(self.t * 5)) + 3)
        pygame.draw.rect(surf, (255, 220, 110) if hover else GOLD, rect, border_radius=14)
        pygame.draw.rect(surf, WHITE, rect, 3, border_radius=14)
        draw_text(surf, "PLAY BALL!", rect.centerx, rect.centery + 11, 30, (60, 35, 0), outline=False)

        # team preview + game length
        self.draw_logo_tools(surf)
        draw_text(surf, "INNINGS", 930, 596, 16, GOLD)
        for n, rect in self.inning_rects.items():
            selected, hover = n == self.innings, rect.collidepoint(self.mouse)
            pygame.draw.rect(surf, TEAL if selected else (60, 70, 110) if hover else (34, 42, 80), rect, border_radius=8)
            pygame.draw.rect(surf, WHITE if selected else (110, 120, 160), rect, 2, border_radius=8)
            draw_text(surf, str(n), rect.centerx, rect.centery + 8, 20)

        draw_text(surf, "Type to name your team  |  LEFT/RIGHT: color  |  UP/DOWN: difficulty  |  TAB: innings  |  ENTER: play  |  F11: fullscreen",
                  640, 714, 12, (190, 195, 215))


# =============================================================================
# 6. MAIN LOOP
# =============================================================================

def make_window(fullscreen):
    if fullscreen:
        return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    return pygame.display.set_mode((int(LOGICAL_W * WINDOW_SCALE), int(LOGICAL_H * WINDOW_SCALE)), pygame.RESIZABLE)


def main():
    pygame.init()
    pygame.display.set_caption("Flash Baseball")
    fullscreen = FULLSCREEN
    window = make_window(fullscreen)
    canvas = pygame.Surface((LOGICAL_W, LOGICAL_H))
    clock = pygame.time.Clock()
    game = Game()
    menu = Menu()
    mode = "menu"                                            # "menu" (start screen) or "game"

    def to_canvas(pos):
        """Convert a mouse position in the window to canvas coordinates."""
        w, h = window.get_size()
        scale = min(w / LOGICAL_W, h / LOGICAL_H)
        return (pos[0] - (w - LOGICAL_W * scale) / 2) / scale, (pos[1] - (h - LOGICAL_H * scale) / 2) / scale

    while True:
        dt = min(0.05, clock.tick(FPS) / 1000)
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                fullscreen = not fullscreen
                window = make_window(fullscreen)
                continue
            if mode == "menu":
                if menu.handle_event(event, to_canvas):
                    menu.save_settings()
                    game.configure(menu.team_name, menu.team_color, menu.difficulty, menu.innings, menu.logo_for_game())
                    mode = "game"
            elif event.type == pygame.MOUSEMOTION:
                game.mouse = to_canvas(event.pos)
                if game.paused:
                    game.pause_hover(game.mouse)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                game.press_click(to_canvas(event.pos))
            elif event.type == pygame.KEYDOWN:
                if game.paused:
                    game.pause_key(event.key)                # P, arrows, ENTER, BACKSPACE all go to the pause menu
                elif event.key == pygame.K_p:
                    game.toggle_pause()
                elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    game.press_swing()
                elif event.key == pygame.K_r:
                    game.press_run_key()
                elif event.key == pygame.K_s:
                    game.press_slide_key()
        if mode == "menu":
            menu.update(dt)
            menu.draw(canvas)
        else:
            game.update(dt)
            game.draw(canvas)
            if game.quit_to_menu:
                mode = "menu"
        w, h = window.get_size()
        scale = min(w / LOGICAL_W, h / LOGICAL_H)
        size = (int(LOGICAL_W * scale), int(LOGICAL_H * scale))
        window.fill(BLACK)
        window.blit(pygame.transform.smoothscale(canvas, size), ((w - size[0]) // 2, (h - size[1]) // 2))
        pygame.display.flip()


if __name__ == "__main__":
    main()