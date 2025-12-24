# LTCLocations
A python script to be ran in Termux on Android to find London Ontario's London Transit Commission buses.

# Getting Started
1. Install [Termux](https://termux.dev/en/), this is typically done through the F-Droid app.

2. Within Termux, install python:
```
apt install python
```

3. Download this repository:
```
apt install wget
# Choose a directory
mkdir -p path/to/LTCLocations
cd path/to/LTCLocations
wget https://github.com/brianbaillargeon1/LTCLocations/archive/refs/heads/main.zip
unzip main.zip
```

4. Grant yourself execute permission
```
chmod +x locate.sh
```

# Usage
To run the program:
```
path/to/LTCLocations/locate.sh
```

Note that this relies on termux-location, which may prompt for location permission.
It can be beneficial to run termux-location before running locate.sh to ensure the permissions are allowed.
