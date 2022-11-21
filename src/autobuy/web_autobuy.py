from time import sleep, time
import mss.tools
import numpy as np
from pynput import keyboard
import mouse

from capture import capture

# Used to pause the program when the user tries to move the mouse while autobuy is in progress 
last_mouse_pos = (0,0)

# Simple global state variables to keep track of pausing and exiting
stop_program = False
pause_program = False

# Size of the capture region for 1920x1080 game window with 100% UI scaling
WEB_SIZE = (798,788)
# This is in capture region coordinates for 1920x1080
WEB_CENTER = (int(WEB_SIZE[0]/2), int(WEB_SIZE[1]/2))

# These are in absolute coordinates
CAPTURE_CENTER = (678, 583)

# Top left corner of the capture region
CAPTURE_POS = (CAPTURE_CENTER[0] - int(WEB_SIZE[0] / 2), CAPTURE_CENTER[1] - int(WEB_SIZE[1] / 2))

# These colors are in RGB
# Color of an available bloodweb node edge
COLOR_NODE_AVAILABLE = (156, 149, 117)
# Color of a purchased bloodweb node edge
COLOR_NODE_PURCHASED = (177, 4, 24)


# Prestige node color table, used with PRESTIGE_SAMPLE_PTS_SMALL
COLOR_PRESTIGE_SMALL = np.array([(210, 0, 1), (251, 248, 248), (205, 0, 0), (35, 1, 2)], np.int32)

# Sampling positions to detect prestige node
PRESTIGE_SAMPLE_PTS_SMALL = np.array([(677,625), (662,592), (678,540), (715, 582)], np.int32)

COLOR_PRESTIGE_LARGE = np.array([(201, 6, 6),(254, 252, 252),(139, 130, 132)], np.int32)

PRESTIGE_SAMPLE_PTS_LARGE = np.array([(677,651),(650, 598),(618, 581)], np.int32)


# Hard-coded positions for all sample points in absolute coordinates on a 1920x1080 monitor, 100% in-game GUI scale
# One array for each ring
# Counter-clockwise, starting from the top, (top-left for 2 ring)
NODE_SAMPLE_PTS = [
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

for i in range(len(COLOR_PRESTIGE_SMALL)):
    rgb = COLOR_PRESTIGE_SMALL[i]
    COLOR_PRESTIGE_SMALL[i] = (rgb[2],rgb[1],rgb[0])

for i in range(len(PRESTIGE_SAMPLE_PTS_LARGE)):
    PRESTIGE_SAMPLE_PTS_LARGE[i] = PRESTIGE_SAMPLE_PTS_LARGE[i] - CAPTURE_POS

for i in range(len(COLOR_PRESTIGE_LARGE)):
    rgb = COLOR_PRESTIGE_LARGE[i]
    COLOR_PRESTIGE_LARGE[i] = (rgb[2],rgb[1],rgb[0])

# Calculates the chebyshev distance between two vectors, used for color comparison and mouse movement detection
def chebyshev(a,b):
    return max(abs(a-b))

# Gets the pixel color from the img numpy array at the given pixel coordinates
# Return value is cast from uint8 to int16 to make comparisons easier while avoiding overflow
def get_pixel_color(img: np.ndarray, pos: tuple):
    return img[pos[1], pos[0]].astype(np.int16)

# Click and hold at absolute screen position for duration
def click(pos: tuple, duration: float):
    if check_for_mouse_pause():
        return
    global last_mouse_pos
    mouse.move(pos[0], pos[1])
    last_mouse_pos = (pos[0], pos[1])
    sleep(0.08) # This small delay seems to be needed
    mouse.press()
    sleep(duration)
    mouse.release()

# Automatically click at the prestige icon for the right duration
def prestige():
    pos = CAPTURE_CENTER
    click(pos, 2.0)
    sleep(5.0)
    click(pos, 0.1)
    


# Moves the mouse out of way so no extra GUI elements are potentially drawn on top of the nodes
def reset():
    if check_for_mouse_pause():
        return
    global last_mouse_pos
    mouse.move(255,124)
    last_mouse_pos = (255,124)
    sleep(0.05)

# Check if user has moved the mouse and pause automatically
def check_for_mouse_pause():
    global pause_program
    moved_dist = chebyshev(
                np.asarray(last_mouse_pos, np.int32),
                np.asarray(mouse.get_position(), np.int32))
    if not pause_program and moved_dist > 3:
        print("Paused on mouse move, press F3 to resume", flush=True)
        pause_program = True
        return True


# Keyboard callback
def on_press(key):
    global stop_program
    global pause_program
    global last_mouse_pos
    # Only stop with ESC if not paused
    if key == keyboard.Key.f2 or (key == keyboard.Key.esc and not pause_program):
        stop_program = True
        return False
    elif key in [keyboard.Key.f3]:
        pause_program = not pause_program
        if pause_program:
            print("Paused, press F3 to resume", flush=True)
        else:
            print("Resumed", flush=True)
            last_mouse_pos = mouse.get_position()

# Checks for two sets of prestige node templates.
# Smaller is used when the player hasn't hovered over the prestige node yet
def detect_prestige(img: np.ndarray, prestige_tolerance: float):
    prestige_detected = True
    # Check for smaller prestige node
    for i in range(len(PRESTIGE_SAMPLE_PTS_SMALL)):
        pos = PRESTIGE_SAMPLE_PTS_SMALL[i]
        template_col = COLOR_PRESTIGE_SMALL[i]
        pixel_col = get_pixel_color(img, pos)
        if chebyshev(pixel_col, template_col) > prestige_tolerance:
            prestige_detected = False
            break
            
    if prestige_detected:
        return True
    
    # Check for larger prestige node
    for i in range(len(PRESTIGE_SAMPLE_PTS_LARGE)):
        pos = PRESTIGE_SAMPLE_PTS_LARGE[i]
        template_col = COLOR_PRESTIGE_LARGE[i]
        pixel_col = get_pixel_color(img, pos)
        if chebyshev(pixel_col, template_col) > prestige_tolerance:
            return False
    return True

# Main program loop
def autobuy(
        start_paused : bool = False,
        verbose : bool = False,
        monitor_index : int = 1,
        time_limit : float = 0,
        should_prestige : bool = True,
        ordering : str = "reverse",
        node_tolerance : int = 50,
        prestige_tolerance : int = 50,
        color_available : tuple = COLOR_NODE_AVAILABLE,
        color_purchased : tuple = COLOR_NODE_PURCHASED):
    global stop_program
    global pause_program
    global last_mouse_pos
    
    
    time_limit_enabled = time_limit > 0.0
    reverse = ordering == "reverse"
    shuffle = ordering == "shuffle"
    
    color_available = np.array([color_available[2],color_available[1],color_available[0]], np.int16)
    color_purchased = np.array([color_purchased[2],color_purchased[1],color_purchased[0]], np.int16)
    #color_prestige = np.array([color_prestige[2],color_prestige[1],color_prestige[0]], np.int16)


    # Create the list of node sample points
    ring_arrays = NODE_SAMPLE_PTS
    if not reverse:
        # Flip if not reversed so that inner rings come first
        ring_arrays.reverse()
    nodes = np.concatenate(ring_arrays,axis=0)
    
    # Start listening for pause and stop commands
    with keyboard.Listener(on_press=on_press) as listener:
        
        if start_paused:
            print("Paused, press F3 to begin, F2 to stop,", flush=True)
            pause_program = True
        else:
            print("Running, press F2 to stop, F3 to pause/resume", flush=True)
        
        start_time = time()
        last_mouse_pos = mouse.get_position()
        
        level_bought_nodes = 0
        # Main loop
        while stop_program == False:    
            # Pause loop
            if pause_program:
                sleep(0.1)
                continue
            # First check if we should pause from mouse movement
            if check_for_mouse_pause():
                continue
            # Time limit tracking
            elapsed_time = time() - start_time
            if time_limit_enabled and elapsed_time > time_limit:
                stop_program = True
            
            # If shuffle enabled, randomize the node order during each buy loop
            if shuffle:
                np.random.shuffle(nodes)
                
            # Move mouse out of the way
            reset() 
            
            # Do the capture
            img = capture(monitor_index, CAPTURE_POS, WEB_SIZE)

            # Flag to keep track if an available node was found
            buy_success = False
            # Loop through sample points, compare colors, buy the first node available node that was found
            for pos in nodes:
                ring_color = get_pixel_color(img, pos)
                inner_ring_color = get_pixel_color(img, (pos[0] + 11, pos[1]))
                if chebyshev(ring_color, color_available) <= node_tolerance and not chebyshev(inner_ring_color, color_purchased) <= node_tolerance:
                    # Convert position to absolute coordinates
                    # Click 35px to the right of the sample point to hit the node
                    clickpos = (pos[0] + 35 + CAPTURE_POS[0], pos[1] + CAPTURE_POS[1])
                    if verbose:
                        print("Buying: ", clickpos, flush=True)
                    click(clickpos, 0.5)
                    reset()
                    if verbose and level_bought_nodes == 4:
                        print("5th node bought, switching to longer delay mode")
                    sleep(0.305 if level_bought_nodes >= 4 else 0.001) # This is only needed when the entity starts blocking the nodes
                    buy_success = True
                    level_bought_nodes += 1
                    break
            
            
            if not buy_success:
                level_bought_nodes = 0
                # No available nodes found, check if prestige possible
                prestige_detected = detect_prestige(img, prestige_tolerance)
                if prestige_detected:
                    print("Prestige detected", flush=True)
                    if not should_prestige:
                        print("Paused on prestige", flush=True)
                        pause_program = True
                        continue
                    prestige()
                else: # If the prestige node wasn't detected, continue the loop normally
                    if verbose:
                        print("Nothing detected", flush=True)
                    # Add a small delay between loops to allow for the level up animation to play
                    sleep(0.5)
                    
        # Main loop ended, print out the time stats
        seconds = int(time() - start_time)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        periods = [('hours', hours), ('minutes', minutes), ('seconds', seconds)]
        time_string = ', '.join('{} {}'.format(value, name)
                                for name, value in periods
                                if value)
        print(f'Stopping, ran for {time_string}', flush=True)

if __name__ == "__main__":
    autobuy()
