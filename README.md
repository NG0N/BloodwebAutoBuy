# Bloodweb AutoBuy
Automates spending bloodpoints in Dead by Daylight.

**Currently only works on 1920x1080 fullscreen game window**

* Choose between buying nodes from either inside towards the edges, or vice versa. Random order also supported.
* Set a time limit to stop progressing the Bloodweb
* Optionally prestige automatically, or stop when completing level 50

Works by sampling pixels at predefined positions in the Bloodweb GUI and detecting which nodes are available to buy according to the pixel color.

## Installation
Download the [latest release](https://github.com/NG0N/BloodwebAutoBuy/releases/latest/download/BloodwebAutoBuy.zip) and run `Bloodweb AutoBuy.exe`

## Usage Guide
Before running the program you should disable any filters that may affect the color of the game.
The game should be in fullscreen and in 1920 by 1080 resolution. 
**UI Scale** in the in-game **Graphics settings**  should also be set to the default 100%
### Hotkeys
- **F3**: Pause/Resume
- **F2 / ESC**: Quit

Moving your mouse will also pause the program

### Options
#### Monitor Index
Determines which monitor the game is captured from, 1 being the primary monitor.
#### Start Paused
Running the program with this setting enabled will cause the program to begin in a paused state. Pressing F3 will unpause.
#### Buy closest nodes first
By default the program will buy the furthest node from the center available.
Choosing this option will invert this behaviour, meaning that the inner rings are bought first.
#### Randomize order
The nodes will be bought in a random order
#### Auto-Prestige
Automatically buys the prestige node that appears after 50 levels.
Disabling this option will pause the program when a prestige node is detected.
#### Time limit
Can be used to run the program for a set amount of time in minutes. Set to 0 to never stop automatically.


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

*Note:* Due to [Gooey Issue #149](https://github.com/chriskiehl/Gooey/issues/149) the custom program icons in the `data/` directory won't show up in the packaged build. A temporary workaround is to copy and replace the images in `.venv/Lib/site-packages/gooey/images` with the images from the `data/` directory before building.

## Libraries Used
* [python-mss](https://github.com/BoboTiG/python-mss): Screen capture
* [Gooey](https://github.com/chriskiehl/Gooey): GUI library
* [mouse](https://github.com/boppreh/mouse): Mouse event simulation
* [keyboard](https://github.com/boppreh/keyboard): Hotkey events
* [NumPy](https://numpy.org): Image data arrays
