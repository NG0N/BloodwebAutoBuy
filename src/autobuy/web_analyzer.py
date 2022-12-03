import numpy as np
import mss, mss.tools
import win32gui
from time import sleep
from enum import IntEnum
from PIL import Image, ImageDraw
from pathlib import Path

class GameWindow:
    handle : int
    position : np.ndarray[int]
    size : np.ndarray[int]
    
    def __init__(self, handle, position, size) -> None:
        self.handle = handle
        self.position = position
        self.size = size

# Reference resolution is used in sample point coordinates
# The points are scaled from this resolution to whatever the game window size is
REF_RESOLUTION = (2560,1440)
### These values are only valid for 2560x1440 and are scaled during runtime
# Diameter of node rings
NODE_SIZE = 100
# Width of the square of pixels that is used to determine the node rarity
# Scaled by resolution
RARITY_CROP_SIZE = 30
# Offset to the node edge where the color is sampled to determine if the node can be bought
NODE_EDGE_OFFSET = np.array([-46,20], int)
# Not implemented, offset to the white perk icon stripe
#PERK_SAMPLE_OFFSET = np.array([24,-38], int)

# Used to parse the sample point file
NODE_COUNT = 30
SAMPLE_COUNT_SMALL_PRESTIGE = 4
SAMPLE_COUNT_LARGE_PRESTIGE = 3

COLOR_PRESTIGE_SMALL = np.array([[1, 0, 210], [248, 248, 251], [0, 0, 205], [53, 47, 40]], int)
COLOR_PRESTIGE_LARGE = np.array([[6, 6, 201], [252, 252, 254], [55, 55, 50]], int)


class Rarity(IntEnum):
    COMMON, UNCOMMON, RARE, VERY_RARE, ULTRA_RARE, EVENT = range(6)
    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented

# Unused, hue is used instead
RARITIES_BGR = {
    Rarity.COMMON     : [39, 52,70],
    Rarity.UNCOMMON   : [43,157,194],
    Rarity.RARE       : [17, 66, 10],
    Rarity.VERY_RARE  : [98, 36, 81],
    Rarity.ULTRA_RARE : [52, 11, 150],
    #[205, 157, 35]
}


RARITIES_HUE = np.array([
    25,
    45,
    128,
    284,
    342,
    # 42 Event is too similiar to uncommon yellow for the current detection method
], int)






class WebAnalyzer:
     # Default node edge color
    _color_node_available = np.array([117, 149, 156], int)
    _color_tolerance = 20
    
    _sct : mss.base.MSSBase
    
    _bring_to_front = True
    
    _game_window: GameWindow
    
    _override_monitor_index = 0
    _custom_midpoint = None
    
    # Sampling points in game window space
    _sample_points: np.ndarray[np.ndarray[int]]
    # Views into _sample_points:
    ## Coordinates of node edges
    _web_points = None
    ## Coordinates of the node centers
    _web_nodes = None
    # Coordinates for small and large prestige icons
    _small_prestige_points = None
    _large_prestige_points = None
    
   
    # Bounding box of _sample_points, in game window space
    # (startpos, endpos)
    _web_bbox: tuple = None

    # Scaling factor, determined by <game window width> / <ref window width>
    # Used to scale sample points
    _scaling = 1.0
    
    # Center position for current resolution, in game window space
    _center_pos : np.ndarray[int]
    
    class GameResolutionError(Exception):
        resolution: str
    class WindowNotFoundError(Exception):
        pass
    
    def __del__(self):
        self._sct.close()
        
    def __init__(self) -> None:
        self._sct = mss.mss()
    
    # Manual initialization is needed for monitor override
    def initialize(self):
        self._update_game_window_info()        
        points_file = "data/2560x1440.csv"
        try:
            self._import_points(points_file, tuple(self._game_window.size))
        except self.GameResolutionError as err:
            print(f"Unsupported resolution: {err.resolution}, You can manually calibrate in the program settings", flush=True)
            raise err
        except IOError as err:
            print(f"Failed to import sample points in file {points_file}", flush=True)
            raise err
                    
        self._calculate_bounds()
        
    def set_color_available(self, rgb : tuple) -> None:
        self._color_node_available = np.array([rgb[2],rgb[1],rgb[0]], np.int16)

    def set_node_tolerance(self, node_tolerance: int) -> None:
        self._color_tolerance = node_tolerance

    def set_override_monitor_index(self, index: int) -> None:
        self._override_monitor_index = index
    
    def set_custom_midpoint(self, x: int, y: int):
        self._custom_midpoint = np.array([x,y],int)
    
    def set_bring_to_front(self, bring_to_front : bool):
        self._bring_to_front = bring_to_front
        
    # Captures a screenshot
    # bbox is start and end positions. Game window position offset is added here
    # Returns in BGR format 
    def capture(self, bbox: tuple[int, int, int, int]) -> np.ndarray:
        absolute_bbox = (self._game_window.position[0].item() + bbox[0],
                         self._game_window.position[1].item() + bbox[1],
                        self._game_window.position[0].item() + bbox[2],
                        self._game_window.position[1].item() + bbox[3])
        img = np.array(self._sct.grab(absolute_bbox)) # Capture
        img = img[:,:,:3] # Discard alpha
        return img


    # Returns the node position in absolute coordinates
    def get_node_position(self, node: int) -> tuple:
        if node < 0:
            return self._center_pos + self._game_window.position
        return self._web_nodes[node] + self._game_window.position
    
    # Takes a screen capture, samples the node positions, sorts by rarity, most common first
    # 0-29 are normal nodes, -1 is prestige node
    # Returns None if no nodes detected
    def find_buyable_nodes(self):
        bbox = self._web_bbox
        
        # Convert to python int tuple for MSS
        capture_bbox = (bbox[0][0].item(), bbox[0][1].item(), bbox[1][0].item(), bbox[1][1].item())
        image = self.capture(capture_bbox)

        rim_positions = self._web_points - bbox[0]
        samples = image[rim_positions[:,1],rim_positions[:,0]]
        dists = np.linalg.norm(np.subtract(samples, self._color_node_available), axis=1)
        buyable = np.asarray(dists < self._color_tolerance).nonzero()[0]
        
        
        # Extract node images
        node_positions = self._web_nodes[buyable] - bbox[0]
        
        start1 = node_positions[:,1] - self._rarity_sample_width
        end1 = node_positions[:,1] + self._rarity_sample_width

        start2 = node_positions[:,0] - self._rarity_sample_width
        end2 = node_positions[:,0] + self._rarity_sample_width
        
        node_images = np.zeros((len(start1),2*self._rarity_sample_width,2*self._rarity_sample_width,3),int)
        for i in range(len(start1)):
            s1 = start1[i]
            e1 = end1[i]
            s2 = start2[i]
            e2 = end2[i]
            
            node_images[i] = image[s1:e1,s2:e2,:]
            
        # Calculate mean colors
        means = np.mean(node_images,
                        axis=(1,2))
        
        # Calculate hues
        r = means[:,2]
        g = means[:,1]
        b = means[:,0]
        max = np.max([r,g,b],axis=0)
        min = np.min([r,g,b],axis=0)
                
        hue = np.array([(g-b)/(max-min),
            2.0 + ((b-r) / (max-min)),
            4.0 + ((r-g) / (max-min))])
        indices = np.argmax([r,g,b],axis=0)
        hue = np.choose(indices,hue)
        hue *= 60
        hue[hue < 0] += 360
        
        rarities = np.array([self._find_closest_rarity(a) for a in hue],int)
        
        # Sort by rarity and return            
        if len(buyable) > 0: 
            p = rarities.argsort()
            #rarities = np.array([*Rarity],object)[rarities[p]]
            return buyable[p]
        
        # Check for small prestige node
        sample_positions = self._small_prestige_points - bbox[0]
        samples = image[sample_positions[:,1],sample_positions[:,0]]
        diffs = np.subtract(samples, COLOR_PRESTIGE_SMALL)
        dists = np.linalg.norm(diffs, axis=1)
        if np.max(dists, axis=0) < self._color_tolerance * 1.2:
            return [-1]

        # Check for large prestige node
        sample_positions = self._large_prestige_points - bbox[0]
        samples = image[sample_positions[:,1],sample_positions[:,0]]
        diffs = np.subtract(samples, COLOR_PRESTIGE_LARGE)
        dists = np.linalg.norm(diffs, axis=0)
        if np.max(dists, axis=0) < self._color_tolerance * 1.3:
            return [-1]
        
    # Find minimum angle difference in hue    
    def _find_closest_rarity(self, hue):
        return np.argmin([180 - abs(abs(hue - b) - 180) for b in RARITIES_HUE])
        

    # Reads the resolution file and stores the center points found
    def _parse_resolution_info(self, filename) -> dict:
        center_points = {}
        with open(filename, "r") as f:
            for line in f.readlines():
                line = line.rstrip('\n')
                pair = line.split(":", 1)
                res_pair = pair[0].split("x", 1)
                pos_pair = pair[1].split(",", 1)
                resolution = (int(res_pair[0]), int(res_pair[1]))
                center_pos = np.array([int(pos_pair[0]), int(pos_pair[1])], int)
                center_points[resolution] = center_pos
        return center_points

    # Draws and saves an image file for debugging the currently loaded sample points
    def debug_draw_points(self, out_file: str, groups_to_show: list):
        # Add padding for drawing
        bbox = (self._web_bbox[0] - int(NODE_SIZE * 0.5),
                self._web_bbox[1] + int(NODE_SIZE * 0.5))
        
        bbox_size = bbox[1] - bbox[0]

        # Size of the area that is cropped from the original capture
        zoom_crop_size: int = int(bbox_size[0] / 50)
        zoom_crop_radius: int = int(zoom_crop_size / 2)
        
        # Size the cropped area is upscaled to and displayed in
        zoom_paste_size: int = zoom_crop_size * 3
        zoom_paste_radius: int = int(zoom_crop_size * 3 * 0.5)
        
        node_size = int(106 * self._scaling)
        node_radius = int(106 * self._scaling * 0.5)
        # Create a circle mask
        mask = Image.new('1', (zoom_paste_size,zoom_paste_size),0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0,0,zoom_paste_size,zoom_paste_size),1)
        
        
        # Color for the single pixel representing the sample point
        sample_pos_color = (255,0,0)

        
        # Convert to python int tuple for MSS
        capture_bbox = (bbox[0][0].item(),
                        bbox[0][1].item(),
                        bbox[1][0].item(),
                        bbox[1][1].item())
        image = self.capture(capture_bbox)
        
        # BGR to RGB
        rgb = image[:,:,::-1]
        
        im = Image.fromarray(rgb)
        
        pts_groups = {
            "edges" : self._web_points,
            "nodes" : self._web_nodes,
            "prestige_small" : self._small_prestige_points,
            "prestige_large" : self._large_prestige_points,
        }
        
        # Color of the mask outline
        group_colors = {
            "edges" : (128,128,128),
            "nodes": (255,0,0,90),
            "prestige_small" : (0,255,0),
            "prestige_large" : (0,255,255),
        }
        
        draw = ImageDraw.Draw(im, "RGBA")
        for pt_group in groups_to_show:
            pts = pts_groups[pt_group]
            for i in range(pts.shape[0]):
                pos = pts[i] - (self._web_bbox[0] - int(NODE_SIZE * 0.5)) #+ [39,1]
                if pt_group == "nodes":
                    node_draw_pos = (pos[0] - node_radius, pos[1] - node_radius)
                    draw.ellipse((node_draw_pos, (node_draw_pos[0] + node_size, node_draw_pos[1] + node_size)), fill=group_colors[pt_group])
                else:
                    # Draw sample point
                    im.putpixel(pos, sample_pos_color)
                    
                    # Crop out the area around the sample point
                    crop_bbox = (pos[0] - zoom_crop_radius, pos[1] - zoom_crop_radius, pos[0] + zoom_crop_radius, pos[1] + zoom_crop_radius)
                    zoomed = im.resize((zoom_paste_size, zoom_paste_size), Image.Resampling.NEAREST, crop_bbox)
                    
                    # Paste onto the original capture and draw an outline
                    paste_pos = (pos[0] - zoom_paste_radius, pos[1] - zoom_paste_radius)
                    im.paste(zoomed, paste_pos, mask)
                    draw.ellipse((paste_pos, (paste_pos[0] + zoom_paste_size, paste_pos[1] + zoom_paste_size)), outline=group_colors[pt_group], width=2)

        im.save(out_file)



    # Imports points from a file, transforming them to the correct scaling according to the _center_points table
    def _import_points(self, filename: str, resolution: tuple[int,int] = None) -> np.ndarray:
        self._sample_points = np.loadtxt(filename, dtype=int, delimiter=",", comments="#")
        
        # Transform points if needed
        if resolution != REF_RESOLUTION:
            # Read web center points for different resolutions from a file
            resolution_file = "data/resolutions.txt"
            try:
                center_points = self._parse_resolution_info(resolution_file)
            except Exception as err:
                print(f"Failed to read resolution file {resolution_file}", flush=True)
                raise err
            
            has_custom_midpoint = self._custom_midpoint is not None
            
            ref_center = center_points[REF_RESOLUTION]
            if not resolution in center_points and not has_custom_midpoint:
                raise self.GameResolutionError(resolution.tostring())
            # This is stored for prestiging
            self._center_pos = center_points[resolution] 
            if has_custom_midpoint:
                self._center_pos = self._custom_midpoint
                print(f"Using custom midpoint {self._custom_midpoint}", flush=True)
            # Remove web position from the points so they are centered around [0,0]
            local_pts = (self._sample_points - ref_center).astype(np.float64)
            # Scale according to game window width
            self._scaling = resolution[0] / REF_RESOLUTION[0]
            local_pts *= self._scaling
            # Add the web offset back
            self._sample_points = (local_pts + self._center_pos).astype(int)

        # Precalculate scaling dependent values  
        self._rarity_sample_width = int(RARITY_CROP_SIZE * self._scaling)
        # Create array views for iterating
        self._web_nodes = self._sample_points[:NODE_COUNT]
        self._web_points = self._sample_points[:NODE_COUNT] + (NODE_EDGE_OFFSET * self._scaling).astype(int)
        self._small_prestige_points = self._sample_points[NODE_COUNT:
            NODE_COUNT + SAMPLE_COUNT_SMALL_PRESTIGE]
        self._large_prestige_points = self._sample_points[NODE_COUNT + SAMPLE_COUNT_SMALL_PRESTIGE:
            NODE_COUNT + SAMPLE_COUNT_SMALL_PRESTIGE + SAMPLE_COUNT_LARGE_PRESTIGE]

    def _calculate_bounds(self):
        padding = int(NODE_SIZE * 0.5 * self._scaling)
        min, max = np.min(self._sample_points, axis=0), np.max(self._sample_points, axis=0)
        min -= padding
        max += padding
        self._web_bbox = (min.astype(int), max.astype(int) + 1)


    def get_mouse_idle_pos(self) -> np.ndarray[int]:
        return self._game_window.position + self._web_bbox[0]
    
    def _update_game_window_info(self):
        self._game_window = None
        # If set, override the window with the given monitor index
        if self._override_monitor_index > 0:
            monitor = self._sct.monitors[self._override_monitor_index]
            self._game_window = GameWindow(None,
                                           np.array([monitor["left"], monitor["top"]], int),
                                           np.array([monitor["width"], monitor["height"]], int))
            return

        
        win32gui.EnumWindows(self._enum_windows_callback, None)
        sleep(0.5)
        if not self._game_window:
            print("Failed to find game window, if the game is actually running, set the monitor index manually", flush=True)
            raise self.WindowNotFoundError
    
    # Used by pywin32 to return window handles
    # If DBD window is found it's info is stored in _game_window and the window is brought to the foreground
    def _enum_windows_callback(self, hwnd, *_):
        rect = win32gui.GetWindowRect(hwnd)
        x = rect[0]
        y = rect[1]
        w = rect[2] - x
        h = rect[3] - y
        name = win32gui.GetWindowText(hwnd).strip()
        if name != "DeadByDaylighst":
            return
        self._game_window = GameWindow(hwnd, np.array([x,y], int), np.array([w,h], int))
        print("Game window found automatically", flush=True)
        if not self._bring_to_front:
            return
        try:
            win32gui.SetForegroundWindow(hwnd)
            pass
        except Exception as err:
            #SetForegroundWindow seems to fail randomly
            pass
    
    def save_debug_images(self):
        x = self._custom_midpoint[0]
        y = self._custom_midpoint[1]
        
        edges_filename = f"BAB_{x}_{y}_edges.png"
        nodes_filename = f"BAB_{x}_{y}_nodes.png"
        
        desktop = Path.home() / "Desktop"
        print("Saving preview images for custom midpoint...", flush=True)
        self.debug_draw_points(desktop / edges_filename, ["edges"])
        self.debug_draw_points(desktop / nodes_filename, ["nodes"])
        print(f"Done! Files created:\n{desktop / edges_filename}\n{desktop / nodes_filename}",flush=True)
    
    
if __name__ == "__main__":
    analyzer = WebAnalyzer()
    analyzer.initialize()
    #analyzer.debug_draw_points(f"out_{analyzer._game_window.size}.png", ["edges"])
    print(f"Valid nodes: {analyzer.find_buyable_nodes()}")