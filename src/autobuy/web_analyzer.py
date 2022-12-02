import numpy as np
import os.path as path
import mss, mss.tools
import win32gui
from time import sleep
from PIL import Image, ImageDraw
from dataclasses import dataclass
from enum import Enum

@dataclass
class GameWindow:
    handle : int
    position : np.ndarray[int]
    size : np.ndarray[int]


REF_RESOLUTION = (2560,1440)
### These values are only valid for 2560x1440 and are scaled during runtime
# Diameter of node rings
NODE_SIZE = 100
# 
COLOR_CROP_SIZE = 30

SAMPLE_OFFSET = np.array([-46,20],int)

NODE_COUNT = 30
SAMPLE_COUNT_SMALL_PRESTIGE = 4
SAMPLE_COUNT_LARGE_PRESTIGE = 3

COLOR_DETECT_TOLERANCE = 20
COLOR_NODE_AVAILABLE = np.array([117, 149, 156], int)
COLOR_PRESTIGE_SMALL = np.array([[1, 0, 210], [248, 248, 251], [0, 0, 205], [53, 47, 40]], int)
COLOR_PRESTIGE_LARGE = np.array([[6, 6, 201], [252, 252, 254], [56, 54, 53]], int)



class Rarity(Enum):
    COMMON = 0
    UNCOMMON = 1
    RARE = 2
    VERY_RARE = 3
    ULTRA_RARE = 4
    EVENT = 5
    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented

RARITIES_BGR = {
    Rarity.COMMON     : [39, 52,70],
    Rarity.UNCOMMON   : [43,157,194],
    Rarity.RARE       : [17, 66, 10],
    Rarity.VERY_RARE  : [98, 36, 81],
    Rarity.ULTRA_RARE : [52, 11, 150],
    #[205, 157, 35]
}


RARITIES_HUE = {
    25,
    45,
    128,
    284,
    342,
    # 42 Event is too similiar to yellow for the current detection
}


RARITY_NAMES = {
    Rarity.COMMON     : "brown",
    Rarity.UNCOMMON   : "yellow",
    Rarity.RARE       : "green",
    Rarity.VERY_RARE  : "purple",
    Rarity.ULTRA_RARE : "iridescent",
}






class WebAnalyzer:
    _verbose : bool = False
    _sct : mss.base.MSSBase
    
    _game_window: GameWindow
    
    # Sampling points in game window space
    _sample_points: np.ndarray[np.ndarray[int]]
    _web_points = None
    _web_nodes = None
    _small_prestige_points = None
    _large_prestige_points = None
    # Bounding box of _sample_points, in game window space
    # (startpos, endpos)
    _web_bbox: tuple = None

    _scaling = 1.0


    _center_points : dict = {}
    
    # Current center position for current resolution
    _center_pos : np.ndarray[int]
    
    class GameResolutionError(Exception):
        pass
    
    def __del__(self):
        self._sct.close()
        
    def __init__(self, verbose: bool = False) -> None:
        self._sct = mss.mss()
        self._verbose = verbose
        
        self._update_game_window_info()
        
        #points_file = "data/1920x1080.csv"
        points_file = "data/2560x1440.csv"
        
        try:
            self._import_points(points_file, tuple(self._game_window.size))
        except self.GameResolutionError as err:
            print("Unsupported resolution")
            raise err
        except IOError as err:
            print(f"Failed to import sample points in file {points_file}", flush=True)
            raise err
                    
        self._calculate_bounds()
        
        #self.debug_draw_points(f"out_{self._game_window.size}.png", ["web"])
        
        
    ## Bbox is start and end positions. Game window position is added
    def capture(self, bbox: tuple[int, int, int, int]) -> np.ndarray:
        absolute_bbox = (self._game_window.position[0].item() + bbox[0],
                         self._game_window.position[1].item() + bbox[1],
                        self._game_window.position[0].item() + bbox[2],
                        self._game_window.position[1].item() + bbox[3])
        img = np.array(self._sct.grab(absolute_bbox)) # Capture
        img = img[:,:,:3] # Discard alpha
        return img


    # Takes a screen capture, samples the node positions, sorts by rarity
    # 0-29 are normal nodes, -1 is prestige node
    # Returns None if no nodes detected
    def find_buyable_nodes(self, cheap_first: bool = True):
        bbox = self._web_bbox
        
        # Convert to python int tuple for MSS
        capture_bbox = (bbox[0][0].item(), bbox[0][1].item(), bbox[1][0].item(), bbox[1][1].item())
        image = self.capture(capture_bbox)
                        
        #buyable = []
        rarities = []
        
            
        
        
        rim_positions = self._web_points - bbox[0]
        samples = image[rim_positions[:,1],rim_positions[:,0]]
        dists = np.linalg.norm(np.subtract(samples, COLOR_NODE_AVAILABLE), axis=1)
        buyable = np.asarray(dists < COLOR_DETECT_TOLERANCE).nonzero()[0]
        
        
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
        
        rarities = [self._find_closest_rarity(a) for a in hue]
        
        # Sort by rarity and return            
        if len(buyable) > 0: 
            buyable = [x for _, x in sorted(zip(rarities, buyable), key=lambda pair: pair[0], reverse=not cheap_first)]
            return buyable
        
        # Check for small prestige node
        sample_positions = self._small_prestige_points - bbox[0]
        samples = image[sample_positions[:,1],sample_positions[:,0]]
        diffs = np.subtract(samples, COLOR_PRESTIGE_SMALL)
        dists = np.linalg.norm(diffs, axis=0)
        if np.max(dists, axis=0) < COLOR_DETECT_TOLERANCE:
            return -1

        # Check for large prestige node
        sample_positions = self._large_prestige_points - bbox[0]
        samples = image[sample_positions[:,1],sample_positions[:,0]]
        diffs = np.subtract(samples, COLOR_PRESTIGE_LARGE)
        dists = np.linalg.norm(diffs, axis=0)
        if np.max(dists, axis=0) < COLOR_DETECT_TOLERANCE:
            return -1
        
    # Find minimum angle difference in hue    
    def _find_closest_rarity(self, hue):
        return Rarity(np.argmin([180 - abs(abs(hue - b) - 180) for b in RARITIES_HUE]))
        

    # Reads the resolution file and stores the center points found
    def _parse_resolution_info(self, filename):
        with open(filename, "r") as f:
            for line in f.readlines():
                line = line.rstrip('\n')
                pair = line.split(":", 1)
                res_pair = pair[0].split("x", 1)
                pos_pair = pair[1].split(",", 1)
                resolution = (int(res_pair[0]), int(res_pair[1]))
                center_pos = np.array([int(pos_pair[0]), int(pos_pair[1])], int)
                self._center_points[resolution] = center_pos


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
            "web" : self._web_points,
            "nodes" : self._web_nodes,
            "prestige_small" : self._small_prestige_points,
            "prestige_large" : self._large_prestige_points,
        }
        
        # Color of the mask outline
        group_colors = {
            "web" : (128,128,128),
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
        data = np.loadtxt(filename, dtype=int, delimiter=",", comments="#")
        
        self._sample_points = data
        
        # Transform points if needed
        if resolution != REF_RESOLUTION:
            # Read web center points for different resolutions from a file
            resolution_file = "data/resolutions.txt"
            
            try:
                self._parse_resolution_info(resolution_file)
            except Exception as err:
                print(f"Failed to read resolution file {resolution_file}", flush=True)
                raise err
            
            ref_center = self._center_points[REF_RESOLUTION]
            if not resolution in self._center_points:
                raise self.GameResolutionError("Unsupported game window resolution: {resolution}")
            self._center_pos = self._center_points[resolution]
            # Remove web position from the points so they are centered around [0,0]
            local_pts = (self._sample_points - ref_center).astype(np.float64)
            # Scale according to game window width
            self._scaling = resolution[0] / REF_RESOLUTION[0]
            local_pts *= self._scaling
            # Add the web offset back
            self._sample_points = (local_pts + self._center_pos).astype(int)

        # Precalculate scaling dependent values  
        self._rarity_sample_width = int(COLOR_CROP_SIZE * self._scaling)
        # Create array views for iterating
        self._web_nodes = self._sample_points[:NODE_COUNT]
        self._web_points = self._sample_points[:NODE_COUNT] + (SAMPLE_OFFSET * self._scaling).astype(int)
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



    def _update_game_window_info(self):
        self._game_window = None
        win32gui.EnumWindows(self._enum_windows_callback, None)
        sleep(0.5)
        if not self._game_window:
            self._game_window = GameWindow(None, np.array([0,0], int), np.array([1920,1080], int))
            print("Failed to find game window", flush=True)
    
    # Used by pywin32 to return window handles
    # If DBD window is found it's info is stored in _game_window and the window is brought to the foreground
    def _enum_windows_callback(self, hwnd, *_):
        rect = win32gui.GetWindowRect(hwnd)
        x = rect[0]
        y = rect[1]
        w = rect[2] - x
        h = rect[3] - y
        name = win32gui.GetWindowText(hwnd).strip()
        if name != "DeadByDaylight":
            return
        self._game_window = GameWindow(hwnd, np.array([x,y], int), np.array([w,h], int))
        
        try:
            pass
            #win32gui.SetForegroundWindow(hwnd)
        except Exception as err:
            # SetForegroundWindow seems to fail randomly
            if self._verbose:
                print(f"win32gui Error:\n{err}")
        
    
if __name__ == "__main__":
    analyzer = WebAnalyzer()
