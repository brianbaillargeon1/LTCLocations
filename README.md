# LTCLocations
A python script for Termux on Android to find London Transit Commission buses in London Ontario.

The raw data is available from LTC under their terms of use:
https://www.londontransit.ca/open-data/

# Getting Started
## 1. Install [Termux](https://termux.dev/en/)

This is typically done through the F-Droid app, a free app in the Google Play Store to manage Free Open Source Software (FOSS).

Termux allows you to operate a BASH shell on your device. This guide uses BASH commands, and you would do well to be familiar with, at the very least:
- pwd
- ls
- cd

There are many great resources to familiarize with BASH commands such as [this Bash cheat sheet](https://github.com/RehanSaeed/Bash-Cheat-Sheet).

## 2. Within Termux, install python:
```
apt install python
```

## 3. Download this repository:
```
apt install wget
# Choose a directory
mkdir -p path/to/LTCLocations
cd path/to/LTCLocations
wget https://github.com/brianbaillargeon1/LTCLocations/archive/refs/heads/main.zip
unzip main.zip
```

## 4. Grant yourself execute permission
```
chmod +x locate.sh
```

# Usage
To run the program:
```
path/to/LTCLocations/locate.sh
```

Note that this relies on termux-location, which may prompt for location permissions.
It can be beneficial to run termux-location before running locate.sh to ensure the permissions are allowed.
