from enum import Enum
from time import sleep, time, perf_counter
import numpy as np
import keyboard
import mouse
from web_analyzer import WebAnalyzer
from random import randrange

# Position to move the mouse while waiting
IDLE_MOUSE_POS = (255, 124)

# Logs with flushing enabled to make Gooey log window work
def log(msg):
    print(msg, flush=True)

class Autobuy:
    class Ordering(Enum):
        CHEAP = 0
        EXPENSIVE = 1
        SHUFFLE = 2
    
    ## Options ##
    _start_paused : bool = False
    _verbose : bool = False
    _time_limit : float = 0
    _auto_prestige : bool = True
    _ordering : Ordering = Ordering.SHUFFLE
    _node_tolerance : int = 50
    _prestige_tolerance : int = 50
    
    _monitor_index : int
    _color_available : tuple
    _color_purchased : tuple
    
    _found_none_prev = True
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
    
    _time_last_bought = perf_counter()-1


    def __init__(self) -> None:
        self.web_analyzer = WebAnalyzer()
  

    ## Setters ##

    def set_time_limit(self, time_limit: float) -> None:
        self._time_limit = time_limit
    
    def set_ordering(self, ordering: int) -> None:
        self._ordering = ordering
    
    def set_auto_prestige(self, auto_prestige: bool) -> None:
        self._auto_prestige = auto_prestige
            
    def set_verbose(self, verbose: bool) -> None:
        self._verbose = verbose
        
    def set_start_paused(self, start_paused: bool) -> None:
        self._start_paused = start_paused
    

    # Click and hold at absolute screen position for duration
    def click(self, pos, duration: float) -> None:
        if self.check_for_mouse_pause():
            return
        mouse.move(pos[0], pos[1])
        self._last_mouse_pos = (pos[0], pos[1])
        sleep(0.05) # This small delay seems to be needed
        mouse.press()
        sleep(duration)
        mouse.release()

    # Automatically click at the prestige icon for the right duration
    def prestige(self) -> None:
        pos = self.web_analyzer.get_node_position(-1)
        self.click(pos, 1.0)
        sleep(5.0)
        self.click(pos, 0.1)

    # Moves the mouse out of way so no extra GUI elements are potentially drawn on top of the nodes
    def _reset(self) -> None:
        if self.check_for_mouse_pause():
            return
        mouse.move(self._idle_mouse_pos[0], self._idle_mouse_pos[1])
        self._last_mouse_pos = self._idle_mouse_pos
        
    # Check if user has moved the mouse and pause automatically
    def check_for_mouse_pause(self) -> bool:
        mouse_pos = mouse.get_position()
        moved_dist = max(abs(self._last_mouse_pos[0] - mouse_pos[0]),abs(self._last_mouse_pos[1] - mouse_pos[1]))
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
    
    def _buy_node(self, node: int) -> bool:
        if node == -1:
            self.prestige()
        clickpos = self.web_analyzer.get_node_position(node)
        if self._verbose:
            log(f"Buying node {node}")

        required_delay = 0.36 if self._level_bought_nodes >= 4 else 0.0166666667
        diff = (perf_counter() - self._time_last_bought)
        if diff < required_delay:
            sleep(required_delay - diff)
        
        self.click(clickpos, 0.5)
        
        self._time_last_bought = perf_counter()
        self._reset()

    # Main buy loop
    def _buy_loop(self) -> None:
        self._last_mouse_pos = mouse.get_position()
        self._start_time = time()
        
        # Tracks the amount of nodes successfully bought in a row, needed to add longer delay between loops after 5 nodes
        self._level_bought_nodes = 0
        
        while self._stop_program == False:    
            # Pause loop
            if self._pause_program:
                sleep(0.2)
                continue
            # First check if we should pause from mouse movement
            if self.check_for_mouse_pause():
                continue
            # Time limit tracking
            elapsed_time = time() - self._start_time
            if self._time_limit > 0.0 and elapsed_time > self._time_limit:
                self._stop_program = True
            
            # If shuffle enabled, randomize the node order during each buy loop
            #if self._ordering == self.Ordering.SHUFFLE:
            #    np.random.shuffle(nodes)
                
            # Move mouse out of the way
            self._reset() 
            self._try_buy()
            


    def _try_buy(self):
        

        nodes = self.web_analyzer.find_buyable_nodes()
        if nodes is None:
            
            self._level_bought_nodes = 0
            # Prevent repeating
            if self._verbose and not self._found_none_prev:
                log("Nothing detected")
            self._found_none_prev = True
            # Add a small delay between loops to allow for the level up animation to play
            sleep(0.5)
            return
        
        self._found_none_prev = False
        
        index = 0 if self._ordering != self.Ordering.EXPENSIVE else -1
        if self._ordering == self.Ordering.SHUFFLE:
            index = randrange(0,len(nodes))

        node = nodes[index]
        
        # Normal node
        if node != -1:
            self._buy_node(node)
            self._level_bought_nodes += 1
            return
        # Prestige node
        self._level_bought_nodes = 0
        log("Prestige detected")
        if node == -1 and not self._auto_prestige:
            log("Paused on prestige")
            self._pause_program = True
            return
        self._buy_node(node)

    
    # Start buying the bloodweb nodes
    def run(self) -> None:

        
        
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
            self._buy_loop()
        finally:
             # Main loop ended, print out the time stats
            log(f"Stopping, ran for {self._get_run_duration_string()}")

# preallocate empty array and assign slice by chrisaycock
def shift(arr, num, fill_value=np.nan):
    result = np.empty_like(arr)
    if num > 0:
        result[:num] = fill_value
        result[num:] = arr[:-num]
    elif num < 0:
        result[num:] = fill_value
        result[:num] = arr[-num:]
    else:
        result[:] = arr
    return result



if __name__ == "__main__":
    autobuy = Autobuy()
    autobuy.run()
    
