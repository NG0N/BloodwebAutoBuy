import numpy as np
import mss, mss.tools
import win32gui
from time import sleep
from enum import IntEnum
from PIL import Image, ImageDraw
from pathlib import Path
import sys
from os import getcwd
from argparse import ArgumentParser


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
REF_ASPECT_CUTOFF = 16/9

### These values are only valid for 2560x1440 and are scaled during runtime
# Width of the square of pixels that is used to determine the node rarity
# Scaled by resolution
RARITY_CROP_SIZE = 30

# Offset to the node edge where the color is sampled to determine if the node can be bought
NODE_EDGE_OFFSET = np.array([-46,20], float)
# Not implemented, offset to the white perk icon stripe
#PERK_SAMPLE_OFFSET = np.array([24,-38], int)

# Diameter of node rings
NODE_SIZE = 106


# Used to parse the sample point file
NODE_COUNT = 30
SAMPLE_COUNT_SMALL_PRESTIGE = 4
SAMPLE_COUNT_LARGE_PRESTIGE = 3

COLOR_PRESTIGE_SMALL = np.array([[1, 0, 210], [248, 248, 251], [0, 0, 205], [53, 47, 40]], int)
COLOR_PRESTIGE_LARGE = np.array([[6, 6, 201], [250, 250, 250], [55, 55, 50]], int)


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




PRESTIGE_ONLY = np.array([-1],int)

class WebAnalyzer:
    # Default node edge color
    _color_node_available = np.array([ 106, 139, 145 ], int)
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
    
    _test_image : Image.Image = None
    
    class GameResolutionError(Exception):
        resolution: str = ""
    class WindowNotFoundError(Exception):
        pass
    
    def __del__(self):
        self._sct.close()
        
    def __init__(self) -> None:
        self._sct = mss.mss()
    
    # Manual initialization is needed for monitor override
    def initialize(self):
        print("\n---- Initializing ----")
        
        self._update_game_window_info()
        
        try:
            wd = sys._MEIPASS
        except AttributeError:
            wd = getcwd()
        
        points_file = Path(wd) / "data" / "2560x1440.csv"
        try:
            self._import_points(points_file, tuple(self._game_window.size))
        except WebAnalyzer.GameResolutionError as err:
            print(f"Unsupported resolution: {err.resolution}, You can manually calibrate the web midpoint in the advanced settings", flush=True)
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
    
    def set_custom_midpoint(self, x: float, y: float):
        self._custom_midpoint = np.array([x,y], float)

    def set_bring_to_front(self, bring_to_front : bool):
        self._bring_to_front = bring_to_front
    
    def set_test_image(self, image: Image.Image):
        self._test_image = image


              
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
    
    # Checks a horizontal line of around each of the positions
    # Returns the indices that had pixels close to the given color
    def _get_positions_approx_color(self, image, positions, color, tolerance, sampling_radius):
        start1 = positions[:,1] - sampling_radius
        end1 = positions[:,1] + sampling_radius
        
        # Extract lines around each of the positions
        rim_imgs = np.zeros((len(start1),2 * sampling_radius, 3),int)
        for i in range(len(start1)):
            s1 = start1[i]
            e1 = end1[i]
            rim_imgs[i] = image[s1:e1,positions[i,0],:]
            
        diffs = rim_imgs - color
        dists = np.linalg.norm(diffs, axis=(2))
        min_dists = np.min(np.abs(dists),axis=1)
        
        return (min_dists < tolerance).nonzero()[0]
    
    # Takes a screen capture, samples the node positions, sorts by rarity, most common first
    # 0-29 are normal nodes, -1 is prestige node
    # Returns None if no nodes detected
    def find_buyable_nodes(self) -> np.ndarray:
        bbox = self._web_bbox
           
        # Convert to python int tuple for MSS
        capture_bbox = (bbox[0][0].item(), bbox[0][1].item(), bbox[1][0].item(), bbox[1][1].item())
        
        if not self._test_image:
            image = self.capture(capture_bbox)
        else:
            cropped = self._test_image.crop(capture_bbox)
            image = np.asarray(cropped)[:,:,::-1] # RGB to BGR
        
        edge_positions = self._web_points - bbox[0]
        # Get indices of the positions that are close to the color of a buyable node
        buyable = self._get_positions_approx_color(image, edge_positions, self._color_node_available, self._color_tolerance, 2)
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
        max_c = np.max([r,g,b],axis=0)
        min_c = np.min([r,g,b],axis=0)
                
        hue = np.array([(g-b)/(max_c-min_c),
            2.0 + ((b-r) / (max_c-min_c)),
            4.0 + ((r-g) / (max_c-min_c))])
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
            return PRESTIGE_ONLY

        # Check for large prestige node
        sample_positions = self._large_prestige_points - bbox[0]
        samples = image[sample_positions[:,1],sample_positions[:,0]]
        diffs = np.subtract(samples, COLOR_PRESTIGE_LARGE)
        dists = np.linalg.norm(diffs, axis=0)
        if np.max(dists, axis=0) < self._color_tolerance + max(self._color_tolerance * 1.5, 20):
            return PRESTIGE_ONLY
        
        return []
        
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
                center_pos = np.array([float(pos_pair[0]), float(pos_pair[1])], float)
                center_points[resolution] = center_pos
        return center_points

    # Draws and saves an image file for debugging the currently loaded sample points
    def debug_draw_points(self, groups_to_show: list) -> Image.Image:
        # Add padding for drawing
        bbox = (self._web_bbox[0] - int(NODE_SIZE * 0.5 * self._scaling),
                self._web_bbox[1] + int(NODE_SIZE * 0.5 * self._scaling))
        draw_origin = bbox[0]
        bbox_size = bbox[1] - bbox[0]

        # Size of the area that is cropped from the original capture
        zoom_crop_size: int = int(bbox_size[0] / 50)
        zoom_crop_radius: int = int(zoom_crop_size / 2)
        
        # Size the cropped area is upscaled to and displayed in
        zoom_paste_size: int = zoom_crop_size * 3
        zoom_paste_radius: int = int(zoom_crop_size * 3 * 0.5)
        
        node_size = int(NODE_SIZE * self._scaling)
        node_radius = int(NODE_SIZE * self._scaling * 0.5)
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
        
        if not self._test_image:
            image = self.capture(capture_bbox)
            # BGR to RGB
            image = image[:,:,::-1]
        else:
            cropped = self._test_image.crop(capture_bbox)
            image = np.asarray(cropped)

        im = Image.fromarray(image)
        
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
        
        if groups_to_show.count("edges") > 0:
            buyable = self.find_buyable_nodes()

        draw = ImageDraw.Draw(im, "RGBA")
        for pt_group in groups_to_show:
            pts = pts_groups[pt_group]
            for i in range(pts.shape[0]):
                pos = pts[i] - draw_origin #+ [39,1]
                if pt_group == "nodes":
                    node_draw_pos = (pos[0] - node_radius, pos[1] - node_radius)
                    draw.ellipse((node_draw_pos, (node_draw_pos[0] + node_size, node_draw_pos[1] + node_size)), fill=group_colors[pt_group])
                else:
                    # Draw sample point
                    pixel_col = sample_pos_color
                    outline_col = group_colors[pt_group]
                    
                    if pt_group == "edges" and i in buyable:
                        pixel_col = (0,255,0)
                        outline_col = (0,255,0)
                        
                    im.putpixel(pos, pixel_col)
                    
                    # Crop out the area around the sample point
                    crop_bbox = (pos[0] - zoom_crop_radius, pos[1] - zoom_crop_radius, pos[0] + zoom_crop_radius, pos[1] + zoom_crop_radius)
                    zoomed = im.resize((zoom_paste_size, zoom_paste_size), Image.Resampling.NEAREST, crop_bbox)
                    
                    # Paste onto the original capture and draw an outline
                    paste_pos = (pos[0] - zoom_paste_radius, pos[1] - zoom_paste_radius)
                    im.paste(zoomed, paste_pos, mask)
                    draw.ellipse((paste_pos, (paste_pos[0] + zoom_paste_size, paste_pos[1] + zoom_paste_size)), outline=outline_col, width=2)

        return im



    # Imports points from a file, transforming them to the correct scaling according to the _center_points table
    def _import_points(self, filename: str, resolution: tuple[int,int] = None) -> np.ndarray:
        self._sample_points = np.loadtxt(filename, dtype=int, delimiter=",", comments="#")
        # Transform points if needed
        if True:#resolution != REF_RESOLUTION:
            # Read web center points for different resolutions from a file
            try:
                wd = sys._MEIPASS
            except AttributeError:
                wd = getcwd()
            resolution_file =  Path(wd) / "data" / "resolutions.txt"   
            try:
                center_points = self._parse_resolution_info(resolution_file)
            except Exception as err:
                print(f"Failed to read resolution file {resolution_file}", flush=True)
                raise err
            
            has_custom_midpoint = self._custom_midpoint is not None
            ref_center = center_points[REF_RESOLUTION]
            if not resolution in center_points and not has_custom_midpoint:
                err = WebAnalyzer.GameResolutionError("Unsupported resolution")
                try:
                    err.resolution = (str(resolution[0]),str(resolution[1]))
                except:
                    err.resolution = ""
                raise err
            # Center pos is stored for prestiging
            if has_custom_midpoint:
                self._center_pos = self._custom_midpoint
                print(f"Using custom midpoint {self._custom_midpoint}", flush=True)
            else:
                self._center_pos = center_points[resolution]
            
            aspect = resolution[0] / resolution[1]
            # Remove web position from the points so they are centered around [0,0]
            local_pts = (self._sample_points - ref_center).astype(float)
            if aspect > REF_ASPECT_CUTOFF: 
                # Scale according to game window height
                self._scaling = resolution[1] / REF_RESOLUTION[1]
            else:
                # Scale according to game window width
                self._scaling = resolution[0] / REF_RESOLUTION[0]
                
            local_pts *= self._scaling
            # Add the web offset back
            self._sample_points = np.round(local_pts + self._center_pos).astype(int)

        # Precalculate scaling dependent values  
        self._rarity_sample_width = int(RARITY_CROP_SIZE * self._scaling)
        # Create array views for iterating
        self._web_nodes = self._sample_points[:NODE_COUNT]
        self._web_points = self._sample_points[:NODE_COUNT] + np.round(NODE_EDGE_OFFSET * self._scaling).astype(int)
        self._small_prestige_points = self._sample_points[NODE_COUNT:
            NODE_COUNT + SAMPLE_COUNT_SMALL_PRESTIGE]
        self._large_prestige_points = self._sample_points[NODE_COUNT + SAMPLE_COUNT_SMALL_PRESTIGE:
            NODE_COUNT + SAMPLE_COUNT_SMALL_PRESTIGE + SAMPLE_COUNT_LARGE_PRESTIGE]

    def _calculate_bounds(self):
        dist_to_sample_pos = np.ceil(np.linalg.norm(NODE_EDGE_OFFSET))
        padding = int(dist_to_sample_pos * self._scaling)
        min, max = np.min(self._sample_points, axis=0), np.max(self._sample_points, axis=0)
        min -= padding
        max += padding
        self._web_bbox = (min.astype(int), max.astype(int) + 1)


    def get_mouse_idle_pos(self) -> np.ndarray[int]:
        return self._game_window.position + self._web_bbox[0]
    
    def _update_game_window_info(self):
        if self._test_image:
            self._game_window = GameWindow(None,
                    np.array([0, 0], int),
                    np.array([self._test_image.width, self._test_image.height], int))
            return
        
        self._game_window = None
        # If set, override the window with the given monitor index
        if self._override_monitor_index > 0:
            index = min(self._override_monitor_index, len(self._sct.monitors) - 1)
            monitor = self._sct.monitors[index]
            self._game_window = GameWindow(None,
                                           np.array([monitor["left"], monitor["top"]], int),
                                           np.array([monitor["width"], monitor["height"]], int))
            return

        
        win32gui.EnumWindows(self._enum_windows_callback, None)
        sleep(0.5)
        if not self._game_window:
            print("Failed to find game window, if the game is actually running, set the monitor index manually", flush=True)
            raise WebAnalyzer.WindowNotFoundError
    
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
        print("\n---- Starting custom resolution tester ----")
        x = self._center_pos[0]
        y = self._center_pos[1]
        
        edges_filename = f"BAB_{'{:.1f}'.format(x)}_{'{:.1f}'.format(y)}_edges.png"
        nodes_filename = f"BAB_{'{:.1f}'.format(x)}_{'{:.1f}'.format(y)}_nodes.png"
        
        desktop = Path.home() / "Desktop"
        edges_image_path = desktop / edges_filename
        nodes_image_path = desktop / nodes_filename
        print("Creating preview images for custom midpoint...", flush=True)
        edge_im = self.debug_draw_points(["edges"])
        nodes_im = self.debug_draw_points(["nodes"])
        try:
            edge_im.save(edges_image_path)
            nodes_im.save(nodes_image_path)
            print(f"Done! Files created:\n  {edges_image_path}\n  {nodes_image_path}",flush=True)
        except PermissionError:
            print(f"Could not save images: Access to output directory '{desktop}' was denied")
        except:
            print("Could not save images: Failed to save file")
            


# Testing functionality
def main_test():
    parser = ArgumentParser("Bloodweb Analyzer", description="Test the analyzer")
    parser.add_argument("-t", "--test_images", nargs='+', required=False)
    parser.add_argument("-d", "--draw_tests", action='store_true')
    args = parser.parse_args()
    #args.test_images = ["./2560x1440_test.png", "./3840x2400_test.png", "./1360x768_test.png"]
    #args.draw_tests = False
    if args.test_images:
        # Use image(s)
       run_batch_image_test(args.test_images, args.draw_tests)
    else:
        # Capture from game screen
        run_test(args.draw_tests)


def run_batch_image_test(images: list, draw: bool):
    # Test using images
    paths = []
    for p in images:
        path = Path(p)
        if not path.is_file():
            print(f"Invalid test_image: {path.absolute()}")
            continue
        paths.append(path) 
        
    for path in paths:
        try:
            image = Image.open(path)
        except Exception as err:
            print(f"Failed to open test_image: {path.absolute()}")
            print(err)
            continue
        run_test(draw, image)
    

def run_test(draw: bool, image = None):
    analyzer = WebAnalyzer()
    if image:
        analyzer.set_test_image(image)
    analyzer.initialize()
    if draw:
        im = analyzer.debug_draw_points(["nodes", "edges"])
        outpath = f"test_out_{analyzer._game_window.size[0]}x{analyzer._game_window.size[1]}.png"
        im.save(outpath)
        print(f"Image saved to {outpath}")
    else:
        print(f"Valid nodes: {analyzer.find_buyable_nodes()}")


if __name__ == "__main__":
    main_test()