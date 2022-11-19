# Bloodweb AutoBuy
Automates spending bloodpoints in Dead by Daylight.

Works by sampling pixels at predefined positions in the Bloodweb GUI and detecting which nodes are available to buy according to the pixel color.

Currently only works on 1920x1080 game window

* Choose between buying nodes from either inside towards the edges, or vice versa. Random order also supported.
* Set a time limit to stop progressing the Bloodweb
* Optionally prestige automatically, or stop when completing level 50

Any possible game filters should be disabled, since they'll affect the color detection. Some detection parameters are exposed to the user.

## Installation
Download the [latest release](https://github.com/NG0N/BloodwebAutoBuy/releases/latest/download/Bloodweb_AutoBuy_v1.0.exe) and run `Dead by Daylight Bloodweb AutoBuy.exe`
## Manual setup
Manual installation instructions

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
The resulting directory with the executable will be in `dist/`

## Libraries Used
* [python-mss](https://github.com/BoboTiG/python-mss): Screen capture
* [Gooey](https://github.com/chriskiehl/Gooey): GUI library
* [mouse](https://github.com/boppreh/mouse): Mouse event simulation
