"""
Prompts you for bus routes from the London Transit Commission (LTC) in London Ontario.
Displays the distances and directions to all the buses on your selected routes.

The raw data is available from LTC under their terms of use:
https://www.londontransit.ca/open-data/
"""

import curses
from curses import window
import json
import math
import os
import subprocess
import threading
import time
from typing import Any
from typing import List
from typing import Optional
import requests


# pylint: disable=C0103, C0301, R0903, W0603, W0702, W0718


# LTC's open data URL for vehicle positions
LTC_VEHICLE_URL = "http://gtfs.ltconline.ca/Vehicle/VehiclePositions.json"

REFRESH_LTC_SECONDS = 10
REFRESH_GPS_SECONDS = 10

EARTH_RADIUS_KM = 6371

thread_output: dict[str, Any] = {"location": None, "vehicles": None}

DIRECTIONS = [
    "North",
    "North East",
    "East",
    "South East",
    "South",
    "South West",
    "West",
    "North West"
]

DEBUG = False

routes : list[str] = []

stop = False

out_row = 0

scr : Optional[window] = None

# Set to True to draw output using curses; it mostly works until you tilt the screen...
use_curses = False


def prntln(text: str) -> None:
    """
    Prints text to screen as appropriate wrt use_curses
    """
    global out_row
    if use_curses and scr:
        height = scr.getmaxyx()[0]
        fitting_lines = text.split("\n")[-height+1:]
        fitting_text = "\n".join(fitting_lines)
        scr.addstr(out_row, 0, fitting_text)
        out_row += len(fitting_lines)
    else:
        print(text)


def sleep(seconds: float):
    """
    Calls time.sleep; signals to exit the program if interrupted
    """
    global stop
    try:
        time.sleep(seconds)
    except KeyboardInterrupt:
        stop = True


def get_location() -> None:
    """
    Retrieves the device's location in latitude and longitude.
    Stores the result in thread_output["location"] as a tuple[float, float]

    This implementation assumes this script is running in termux on an Android device.
    Other devices will need to customize this method however appropriate.
    """
    last_refresh = time.time() - REFRESH_GPS_SECONDS
    while not stop:
        start = time.time()

        if start - last_refresh >= REFRESH_GPS_SECONDS:
            last_refresh = time.time()
            tloc = json.loads(subprocess.run("termux-location", check=False, stdout=subprocess.PIPE, text=True).stdout)
            if DEBUG:
                prntln("termux location")
                prntln(json.dumps(tloc, indent=4))

            thread_output["location"] = (tloc["latitude"], tloc["longitude"])

        # Loop every second so we can break out if interrupted
        sleep_time = 1 - (time.time() - start)
        if sleep_time > 0:
            sleep(sleep_time)
    if DEBUG:
        prntln("get_location aborting.")


def get_vehicles() -> None:
    """
    Retrieves vehicle positions via LTC's open data URL
    Stores result in thread_output["vehicles"]
    """
    last_refresh = time.time() - REFRESH_LTC_SECONDS
    while not stop:
        start = time.time()

        if start - last_refresh >= REFRESH_LTC_SECONDS:
            last_refresh = time.time()
            response = requests.get(LTC_VEHICLE_URL, timeout=30)
            data = response.json()

            if DEBUG:
                prntln("Vehicles:")
                prntln(json.dumps(data, indent=4))

            thread_output["vehicles"] = [e["vehicle"] for e in data["entity"]]

        # Loop every second so we can break out if interrupted
        sleep_time = 1 - (time.time() - start)
        if sleep_time > 0:
            sleep(sleep_time)
    if DEBUG:
        prntln("get_vehicles aborting.")


class Bus:
    """
    Data class; presents nice as an str
    """
    def __init__(self, route: Optional[str], lat: float, lng: float, bearing: str):
        self.route = route
        self.lat = lat
        self.lng = lng
        # Direction the bus is facing
        self.bearing = bearing
        self.distance: float = -1
        # Direction from you to the bus
        self.direction: Optional[str] = None

    def __str__(self):
        if self.route:
            return f"""Bus {self.route}, ({self.lat}, {self.lng}):
    Distance: {self.distance:.3f} km {self.direction}
    Direction: {self.bearing}"""
        return f"""Bus ({self.lat}, {self.lng}):
    Distance: {self.distance:.3f} km {self.direction}
    Direction: {self.bearing}"""


def direction(degrees: float) -> str:
    """
    Takes a bearing in degrees; returns "North", "North East", etc.
    """
    # E.g. if 4 directions, they each have 90 degrees; North = 315 to 45 degrees, East = 45 to 135, etc.
    angle_per_direction = 360/len(DIRECTIONS)

    # E.g. if 4 directions, add 45 degrees; North becomes 0 to 90 degrees; East becomes 90 to 180, etc.
    shift = (degrees + angle_per_direction / 2) % 360

    # Scale to the range of len(DIRECTIONS) to get an index
    index = int(len(DIRECTIONS) * shift / 360)
    return DIRECTIONS[index]


def haversine(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """
    Finds the great-circle distance between two points on a sphere; Earth in this case.

    This implementation assumes the earth is round.
    If you live on a flat earth, you will need to customize this method to apply the pythatogrean theorem.
    """
    alat = math.radians(p1[0])
    alng = math.radians(p1[1])
    blat = math.radians(p2[0])
    blng = math.radians(p2[1])

    distance = EARTH_RADIUS_KM * math.acos(
        (math.sin(alat) * math.sin(blat)) +
        (math.cos(alat) * math.cos(blat) * math.cos(
            alng - blng
        ))
    )
    return distance


def azimuth(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """
    Calculates the bearing in degrees when facing p2 from p1's location
    """
    alat = math.radians(p1[0])
    alng = math.radians(p1[1])
    blat = math.radians(p2[0])
    blng = math.radians(p2[1])

    dlng = blng - alng
    y = math.sin(dlng) * math.cos(blat)
    x = math.cos(alat) * math.sin(blat) - math.sin(alat) * math.cos(blat) * math.cos(dlng)
    bearing = math.atan2(y, x)
    return math.degrees(bearing + 2*math.pi) % 360


def print_buses() -> None:
    """
    Prints all the buses for the user's selected routes sorted by distance.
    If we don't yet have enough information, prints which service we're waiting on.
    """
    # Inform user if we haven't gotten a response from LTC yet:
    if not thread_output["vehicles"]:
        # LTC is behind schedule!
        prntln("Still waiting on LTC...")
        return

    # Halt until the vehicle thread completes; grab the output
    vehicles = list(thread_output["vehicles"])

    # Filter vehicles on the desired route
    vehicles = [vehicle for vehicle in vehicles if vehicle["trip"]["route_id"] in routes]

    if DEBUG:
        prntln("Buses on selected routes:")
        prntln(json.dumps(vehicles, indent=4))

    buses = [
        Bus(
            v["trip"]["route_id"] if len(routes) > 1 else None,
            float(v["position"]["latitude"]),
            float(v["position"]["longitude"]),
            direction(v["position"]["bearing"])
        )
        for v in vehicles
    ]

    # Inform user if we're not done pew pewing satellites
    if not thread_output["location"]:
        prntln("Termux-location still pew pewing satellites...")
        return

    # Halt until satellite pew pew triangulation is finished; grab the cooordinates
    loc = thread_output["location"]
    if DEBUG:
        prntln("Location")
        prntln(loc)

    # Calculate bus distances, and which direction they're in relative to our position
    for bus in buses:
        bloc = (bus.lat, bus.lng)
        bus.distance = haversine(loc, bloc)
        bus.direction = direction(azimuth(loc, bloc))

    # Sort buses by distance; nearest at the bottom, then print them
    buses.sort(key=lambda b: b.distance, reverse = True)
    prntln("\n".join(str(bus) for bus in buses))


def refresh_loop(stdscr: Optional[window]) -> None:
    """
    Prints buses locations every greatest common denominator of the GPS and LTC refresh rates
    """
    global stop
    global scr
    global out_row

    scr = stdscr

    refresh_rate = math.gcd(REFRESH_GPS_SECONDS, REFRESH_LTC_SECONDS)
    last_refresh = time.time() - refresh_rate

    last_routes = routes

    while not stop:
        out_row = 0

        start = time.time()

        if start - last_refresh < refresh_rate and last_routes == routes:
            # Continue for 'stop' interrupt every second
            sleep(1)
            continue

        last_refresh = time.time()
        last_routes = routes

        try:
            if use_curses and scr:
                scr.clear()
            else:
                os.system('clear')

            prntln(time.ctime())

            route_word = "route" if len(routes) == 1 else "routes"
            prntln(f"Showing buses on {route_word} {', '.join(routes)}.")
            prntln("Refreshes data from LTC every 10 seconds;")
            prntln("data typically updates every 30 seconds.")
            prntln("You may enter different bus routes,")
            prntln("or type 'quit' <ENTER> to exit.")

            print_buses()

            if use_curses and scr:
                scr.refresh()
        except:
            stop = True
    if DEBUG:
        prntln("refresh_loop aborting.")


def to_route_list(user_input: str) -> List[str]:
    """
    Parses user input into a list of bus routes, padded to match the LTC json data (E.g. route 2 is "02").
    Routes can be delimited with commas or whitespace
    """
    route_list = user_input.replace(",", " ").split()

    # LTC pads single digit routes to two digits, E.g. 2 -> 02
    return [route.zfill(2) for route in route_list]


def read_routes_loop() -> None:
    """
    User input loop.
    Allows the user to change which routes are being filtered on or to quit the program.
    """
    global routes
    global stop

    exit_words = ["quit", "exit"]

    in_str = None
    while not stop and in_str not in exit_words:
        if use_curses and scr:
            try:
                in_str = scr.getstr(out_row, 0).decode(encoding="utf-8")

                # Update presented routes if to_route_list's result is truthy
                as_routes = to_route_list(in_str)
                if as_routes:
                    routes = as_routes
                elif in_str not in exit_words:
                    prntln(f"Invalid input: {in_str}")
            except Exception as ex:
                prntln(str(ex))
                break
        else:
            # ^c typically interrupts the other threads while this call lingers; consider replacing this with a lib like asyncio
            in_str = input()
            as_routes = to_route_list(in_str)
            if as_routes:
                routes = as_routes
            elif in_str not in exit_words:
                prntln(f"Invalid input: {in_str}")

    stop = True
    if DEBUG:
        prntln("read_routes_loop aborting.")


def main() -> None:
    """
    Main program
    """
    global routes

    # While we wait for user input, pew some satellites and stuff
    loc_thread = threading.Thread(target=get_location)
    loc_thread.start()

    vehicle_thread = threading.Thread(target=get_vehicles)
    vehicle_thread.start()

    routes = to_route_list(input("Which routes? "))

    read_routes_thread = threading.Thread(target=read_routes_loop)
    read_routes_thread.start()

    try:
        if use_curses:
            curses.wrapper(refresh_loop)
        else:
            refresh_loop(None)
    except Exception as e:
        prntln(str(e))

main()
