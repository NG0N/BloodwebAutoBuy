import mss.tools
import numpy as np

# Capture the given region on the given monitor, return the image as a numpy array (BGR, uint8)
def capture(monitor_index: int, pos : tuple, size: tuple):
    with mss.mss() as sct:
        monitor = sct.monitors[monitor_index]
        # Create a bounding box
        left = monitor["left"] + pos[0]
        top = monitor["top"] + pos[1]
        right = left + size[0]
        lower = top + size[1]
        bbox = (left, top, right, lower)
        img = np.array(sct.grab(bbox)) # Capture
        img = img[:,:,:3] # Discard alpha
    return img
