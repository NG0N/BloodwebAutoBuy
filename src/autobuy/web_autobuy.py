from enum import Enum
from copy import deepcopy
from time import sleep, time
import mss.tools
import numpy as np
import keyboard
import mouse


# Size of the capture region for 1920x1080 game window with 100% UI scaling
WEB_SIZE = (798,788)

# This is in capture region coordinates for 1920x1080
WEB_CENTER = (int(WEB_SIZE[0]/2), int(WEB_SIZE[1]/2))

# These are in absolute coordinates
CAPTURE_CENTER = (678, 583)

# Top left corner of the capture region
CAPTURE_POS = (CAPTURE_CENTER[0] - int(WEB_SIZE[0] / 2), CAPTURE_CENTER[1] - int(WEB_SIZE[1] / 2))

## These colors are in RGB, but will be converted to BGR ##
# Color of an available bloodweb node edge
COLOR_NODE_AVAILABLE = (156, 149, 117)
# Color of a purchased bloodweb node edge
COLOR_NODE_PURCHASED = (177, 4, 24)

# Template colors for the smaller prestige node (before mouse hover)
COLOR_PRESTIGE_SMALL = np.array([(210, 0, 1), (251, 248, 248), (205, 0, 0), (35, 1, 2)], np.int32)

# Sampling positions to detect the smaller prestige node
PRESTIGE_SAMPLE_PTS_SMALL = np.array([(677, 625), (662, 592), (678, 540), (715, 582)], np.int32)

# Template colors for the larger prestige node (after mouse hover)
COLOR_PRESTIGE_LARGE = np.array([(201, 6, 6),(254, 252, 252),(139, 130, 132)], np.int32)

# Sampling positions to detect the larger prestige node
PRESTIGE_SAMPLE_PTS_LARGE = np.array([(677, 651),(650, 598),(618, 581)], np.int32)

# Position to move the mouse while waiting
IDLE_MOUSE_POS = (255, 124)


# Hard-coded positions for all sample points in absolute coordinates on a 1920x1080 monitor, 100% in-game GUI scale
# One array for each ring
# Counter-clockwise, starting from the top, (top-left for the second ring)
NODE_SAMPLE_PTS : list = [
    np.array([
            (639, 460),
            (535, 521),
            (535, 644),
            (640, 705),
            (745, 644),
            (745, 520)
    ], np.int32),
    np.array([
            (579, 349),
            (463, 411),
            (400, 520),
            (399, 640),
            (463, 754),
            (578, 814),
            (703, 817),
            (819, 755),
            (882, 643),
            (882, 520),
            (819, 410),
            (703, 348)
    ], np.int32),
    np.array([
            (641, 229),
            (461, 278),
            (329, 407),
            (281, 583),
            (330, 756),
            (459, 886),
            (641, 934),
            (820, 883),
            (952, 756),
            (1008, 581),
            (953, 408),
            (821, 276)
    ], np.int32)
]

# Convert all positions to capture region coordinates
for i in range(len(NODE_SAMPLE_PTS)):
    NODE_SAMPLE_PTS[i] = NODE_SAMPLE_PTS[i] - CAPTURE_POS

for i in range(len(PRESTIGE_SAMPLE_PTS_SMALL)):
    PRESTIGE_SAMPLE_PTS_SMALL[i] = PRESTIGE_SAMPLE_PTS_SMALL[i] - CAPTURE_POS

for i in range(len(PRESTIGE_SAMPLE_PTS_LARGE)):
    PRESTIGE_SAMPLE_PTS_LARGE[i] = PRESTIGE_SAMPLE_PTS_LARGE[i] - CAPTURE_POS

# Convert all colors to BGR
for i in range(len(COLOR_PRESTIGE_SMALL)):
    rgb = COLOR_PRESTIGE_SMALL[i]
    COLOR_PRESTIGE_SMALL[i] = (rgb[2],rgb[1],rgb[0])

for i in range(len(COLOR_PRESTIGE_LARGE)):
    rgb = COLOR_PRESTIGE_LARGE[i]
    COLOR_PRESTIGE_LARGE[i] = (rgb[2],rgb[1],rgb[0])


# Calculates the chebyshev distance between two vectors, used for color comparison and mouse movement detection
def chebyshev(a,b):
    return max(abs(a-b))

# Logs with flushing enabled to make Gooey log window work
def log(msg):
    print(msg, flush=True)

class Autobuy:
    class Ordering(Enum):
        DEFAULT = 0
        REVERSE = 1
        SHUFFLE = 2
    
    ## Options ##
    _start_paused : bool = False
    _verbose : bool = False
    _time_limit : float = 0
    _auto_prestige : bool = True
    _ordering : Ordering = Ordering.DEFAULT
    _node_tolerance : int = 50
    _prestige_tolerance : int = 50
    
    _monitor_index : int
    _color_available : tuple
    _color_purchased : tuple
    
    ## Runtime attributes ##
    
    # Used to pause the program when the user tries to move the mouse while autobuy is in progress 
    _last_mouse_pos = (0,0)

    # Used to keep track of pausing and exiting
    _stop_program = False
    _pause_program = False
    
    # Monitor offset
    _monitor_pos = (0,0)
    
    # Capture coordinates in absolute coordinates, taking monitor position into account
    _capture_pos = (0,0)
    
    # Position where to move the mouse while idle, taking monitor position into account 
    _idle_mouse_pos = IDLE_MOUSE_POS

    def __init__(self) -> None:
        # Initialize mss library
        self._sct = mss.mss()
        self.set_monitor_index(1)
        self.set_color_available(COLOR_NODE_AVAILABLE)
        self.set_color_purchased(COLOR_NODE_PURCHASED)
    
    def __del__(self):
        self._sct.close()

    ## Setters ##
    
    def set_color_available(self, rgb : tuple) -> None:
        self._color_available = np.array([rgb[2],rgb[1],rgb[0]], np.int16)

    def set_color_purchased(self, rgb : tuple) -> None:
        self._color_purchased = np.array([rgb[2],rgb[1],rgb[0]], np.int16)
    
    def set_monitor_index(self, monitor_index: int) -> None:
        self._monitor_index = monitor_index
        monitor = self._sct.monitors[self._monitor_index]
        self._monitor_pos = (monitor["left"], monitor["top"])
        self._capture_pos = (self._monitor_pos[0] + CAPTURE_POS[0], self._monitor_pos[1] + CAPTURE_POS[1])
        self._idle_mouse_pos = (self._monitor_pos[0] + IDLE_MOUSE_POS[0], self._monitor_pos[1] + IDLE_MOUSE_POS[1])
    
    def set_time_limit(self, time_limit: float) -> None:
        self._time_limit = time_limit
        
    def set_node_tolerance(self, node_tolerance: int) -> None:
        self._node_tolerance = node_tolerance

    def set_prestige_tolerance(self, prestige_tolerance: int) -> None:
        self._prestige_tolerance = prestige_tolerance

    def set_auto_prestige(self, auto_prestige: bool) -> None:
        self._auto_prestige = auto_prestige
            
    def set_ordering(self, ordering: int) -> None:
        self._ordering = ordering
    
    def set_verbose(self, verbose: bool) -> None:
        self._verbose = verbose
        
    def set_start_paused(self, start_paused: bool) -> None:
        self._start_paused = start_paused


    # Capture the given region on the given monitor, return the image as a numpy array (BGR, uint8)
    def capture(self, pos: tuple, size: tuple) -> np.ndarray:
        left = pos[0]
        top = pos[1]
        right = left + size[0]
        lower = top + size[1]
        bbox = (left, top, right, lower)
        img = np.array(self._sct.grab(bbox)) # Capture
        img = img[:,:,:3] # Discard alpha
        return img
    
    # Gets the pixel color from the img numpy array at the given pixel coordinates
    # Return value is cast from uint8 to int16 to make comparisons easier while avoiding overflow
    def get_pixel_color(self, img: np.ndarray, pos) -> np.ndarray:
        return img[pos[1], pos[0]].astype(np.int16)

    # Click and hold at absolute screen position for duration
    def click(self, pos, duration: float) -> None:
        if self.check_for_mouse_pause():
            return
        mouse.move(pos[0], pos[1])
        self._last_mouse_pos = (pos[0], pos[1])
        sleep(0.08) # This small delay seems to be needed
        mouse.press()
        sleep(duration)
        mouse.release()

    # Automatically click at the prestige icon for the right duration
    def prestige(self) -> None:
        pos = (self._monitor_pos[0] + CAPTURE_CENTER[0], self._monitor_pos[1] + CAPTURE_CENTER[1])
        self.click(pos, 2.0)
        sleep(5.0)
        self.click(pos, 0.1)

    # Moves the mouse out of way so no extra GUI elements are potentially drawn on top of the nodes
    def reset(self) -> None:
        if self.check_for_mouse_pause():
            return
        mouse.move(self._idle_mouse_pos[0], self._idle_mouse_pos[1])
        self._last_mouse_pos = self._idle_mouse_pos
        sleep(0.05)
        
    # Check if user has moved the mouse and pause automatically
    def check_for_mouse_pause(self) -> bool:
        moved_dist = chebyshev(
                    np.asarray(self._last_mouse_pos, np.int32),
                    np.asarray(mouse.get_position(), np.int32))
        if not self._pause_program and moved_dist > 3:
            log("Paused on mouse move, press F3 to resume")
            self._pause_program = True
            return True
        return False


    def _stop(self):
        self._stop_program = True

    def _stop_if_paused(self):
        if not self._pause_program:
            self._stop_program = True


    def _toggle_pause(self):
        self._pause_program = not self._pause_program
        if self._pause_program:
            log("Paused, press F3 to resume")
        else:
            log("Resumed")
            self._last_mouse_pos = mouse.get_position()
    
    # Checks for two sets of prestige node templates.
    # Smaller is used when the player hasn't hovered over the prestige node yet
    def detect_prestige(self, img: np.ndarray, _prestige_tolerance: float) -> bool:
        prestige_detected = True
        # Check for smaller prestige node
        for i in range(len(PRESTIGE_SAMPLE_PTS_SMALL)):
            pos = PRESTIGE_SAMPLE_PTS_SMALL[i]
            template_col = COLOR_PRESTIGE_SMALL[i]
            pixel_col = self.get_pixel_color(img, pos)
            if chebyshev(pixel_col, template_col) > _prestige_tolerance:
                prestige_detected = False
                break
        if prestige_detected:
            return True
        
        # Check for larger prestige node
        for i in range(len(PRESTIGE_SAMPLE_PTS_LARGE)):
            pos = PRESTIGE_SAMPLE_PTS_LARGE[i]
            template_col = COLOR_PRESTIGE_LARGE[i]
            pixel_col = self.get_pixel_color(img, pos)
            if chebyshev(pixel_col, template_col) > _prestige_tolerance:
                return False
        return True
    
    # Returns the time since _start_time in hh, mm, ss format
    def _get_run_duration_string(self) -> str:
        seconds = int(time() - self._start_time)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        periods = [('hours', hours), ('minutes', minutes), ('seconds', seconds)]
        time_string = ', '.join('{} {}'.format(value, name)
                                for name, value in periods
                                if value)
        return time_string
    
    # Loop through sample points, compare colors, buy the first node available node that was found
    # Returns True if a node was found, False otherwise
    def _try_buy_nodes(self, nodes: np.ndarray) -> bool:
        for pos in nodes:
            ring_color_sample = self.get_pixel_color(self._capture_img, pos)
            inner_ring_color_sample = self.get_pixel_color(self._capture_img, (pos[0] + 11, pos[1]))
            if (chebyshev(ring_color_sample, self._color_available) <= self._node_tolerance 
                    and not chebyshev(inner_ring_color_sample, self._color_purchased) <= self._node_tolerance):
                # Convert position to absolute coordinates
                # Click 35px to the right of the sample point to hit the node
                clickpos = (pos[0] + 35 + self._capture_pos[0], pos[1] + self._capture_pos[1])
                if self._verbose:
                    log(f"Buying: {clickpos}")
                self.click(clickpos, 0.5)
                self.reset()
                if self._verbose and self._level_bought_nodes == 4:
                    log("5th node bought, switching to longer delay mode")
                sleep(0.305 if self._level_bought_nodes >= 5 else 0.001) # Longer delay is needed after 5th node of a level is bought
                self._level_bought_nodes += 1
                return True
        return False
            
    # Main buy loop
    def _buy_loop(self, nodes: np.ndarray) -> None:
        self._last_mouse_pos = mouse.get_position()
        self._start_time = time()
        
        # Tracks the amount of nodes successfully bought in a row, needed to add longer delay between loops after 5 nodes
        self._level_bought_nodes = 0
        
        while self._stop_program == False:    
            # Pause loop
            if self._pause_program:
                sleep(0.1)
                continue
            # First check if we should pause from mouse movement
            if self.check_for_mouse_pause():
                continue
            # Time limit tracking
            elapsed_time = time() - self._start_time
            if self._time_limit > 0.0 and elapsed_time > self._time_limit:
                self._stop_program = True
            
            # If shuffle enabled, randomize the node order during each buy loop
            if self._ordering == self.Ordering.SHUFFLE:
                np.random.shuffle(nodes)
                
            # Move mouse out of the way
            self.reset() 
            
            # Do the capture
            self._capture_img = self.capture(self._capture_pos, WEB_SIZE)

            # Flag to keep track if an available node was found
            buy_success = self._try_buy_nodes(nodes)
            
            if not buy_success:
                # No available nodes found, check if prestige possible
                self._level_bought_nodes = 0
                prestige_detected = self.detect_prestige(self._capture_img, self._prestige_tolerance)
                if prestige_detected:
                    log("Prestige detected")
                    if not self._auto_prestige:
                        log("Paused on prestige")
                        self._pause_program = True
                        continue
                    self.prestige()
                else: # If the prestige node wasn't detected, continue the loop normally
                    if self._verbose:
                        log("Nothing detected")
                    # Add a small delay between loops to allow for the level up animation to play
                    sleep(0.5)


    
    # Start buying the bloodweb nodes
    def run(self) -> None:
        # Create the list of node sample points
        ring_arrays = deepcopy(NODE_SAMPLE_PTS)
        if self._ordering != self.Ordering.REVERSE:
            # Flip if not reversed so that inner rings come first
            ring_arrays.reverse()
            
        # Merge the 3 arrays for iteration
        nodes = np.concatenate(ring_arrays,axis=0)
        
        if self._start_paused:
            log("Paused, press F3 to begin, F2 to stop")
            self._pause_program = True
        else:
            log("Running, press F2 to stop, F3 to pause/resume")
            
        keyboard.add_hotkey('f3', lambda: self._toggle_pause())
        keyboard.add_hotkey('f2', lambda: self._stop())
        keyboard.add_hotkey('esc', lambda: self._stop_if_paused())
        
        
        # Wrap in try/finally to make sure kb_listener thread is always stopped
        try:
            self._buy_loop(nodes)
        finally:
             # Main loop ended, print out the time stats
            log(f"Stopping, ran for {self._get_run_duration_string()}")

            



if __name__ == "__main__":
    autobuy = Autobuy()
    autobuy.run()
    
