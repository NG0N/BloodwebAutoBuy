# Bloodweb AutoBuy
Automates spending bloodpoints in Dead by Daylight.

**Support added for common resolutions!**

* Choose whether you want to buy rare or common nodes first
* Set a time limit to stop progressing the Bloodweb
* Optionally prestige automatically, or stop when completing level 50

Works by sampling pixels at predefined positions in the Bloodweb GUI and detecting which nodes are available to buy according to the pixel color.

## Installation
Download the [latest release](https://github.com/NG0N/BloodwebAutoBuy/releases/latest/download/BloodwebAutoBuy.zip) and run `Bloodweb AutoBuy.exe`

## Usage Guide
Before running the program you should disable any filters that may affect the color of the game.
The game should be in fullscreen and the **UI Scale** in the in-game **Graphics settings**  should be set to the default 100%.

Pressing start will bring up the game window and the program will start buying the currently open Bloodweb, from the cheapest available nodes to the rarest by default.


### Hotkeys
- **F3**: Pause/Resume
- **F2 / ESC**: Quit

Moving your mouse will also pause the program

Note: The buying timings are designed for a brand new Bloodweb level, meaning that for the first level (the first few seconds) the program might mistime some of the mouse presses. The timings will align as soons as the program progresses to the next level.

### Supported resolutions
|w × h       |  
| -----------|
|3840 × 2160 |
|2560 × 1600 |
|2560 × 1440 |
|1920 × 1080 |
|1680 × 1050 |
|1366 × 768  |
|1360 × 768  |

## Options

#### Modes
##### Cheap Mode
The most common available nodes will be bought first, determined by their color.
##### Expensive Mode
The rarest available nodes will be bought first.
##### Random Mode
The nodes will be bought in a random order
#### Auto-Prestige
Automatically buys the prestige node that appears after level 50.
Disabling this option will pause the program when a prestige node is detected.
#### Bring window to foreground
When on, the game window will be brought into the foreground to make sure no other windows are blocking the capture.
#### Start Paused
Running the program with this setting enabled will cause the program to begin in a paused state. Pressing F3 will unpause.
#### Time limit
Can be used to run the program for a set amount of time in minutes. Set to 0 to never stop automatically.
#### Monitor Index
Only needed if the game window cannot be detected automatically. Determines which monitor the game is captured from, 1 being the primary monitor. Set to 0 to let the program try to find the window automatically.


## Manual Installation
If you prefer to setup the program manually, follow the steps below
### Required:
* Python 3.9
 
Clone or [download](https://github.com/NG0N/BloodwebAutoBuy/archive/refs/heads/main.zip) the repo:

```
git clone https://github.com/NG0N/BloodwebAutoBuy.git
```
Setup the environment and install requirements:
```
cd BloodwebAutoBuy

python -m venv .venv

.\.venv\Scripts\activate

pip install -r requirements.txt
```

You can now run the program with:

```
python src/autobuy
```

### Building the executable
An executable binary can be built with:
```
pip install pyinstaller
pyinstaller .\build.spec
```

The resulting executable will be in the `dist/` directory

## Libraries Used
* [python-mss](https://github.com/BoboTiG/python-mss): Screen capture
* [Gooey](https://github.com/chriskiehl/Gooey): GUI library
* [mouse](https://github.com/boppreh/mouse): Mouse event simulation
* [keyboard](https://github.com/boppreh/keyboard): Hotkey events
* [NumPy](https://numpy.org): Image data arrays
* [pywin32](https://github.com/mhammond/pywin32): Automatic game window hooking
* [Pillow](https://python-pillow.org/): Debug image manipulation 
