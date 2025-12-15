import math
import time
from typing import Any, Dict, List, Optional, Tuple

"""
Find distance between two points using Haversine Formula:
    hav(theta) = hav(delta(phi)) + cos(phi1)cos(phi2)hav(delta(lambda))
where:
    - phi are the latitudes of the two points
    - lambda are the longitudes of the two points
    - delta(phi) = phi2 - phi1, delta(lambda) = lambda2 - lambda1

We can write the identity as:
    a = sin^2(delta(phi)/2) + cos(phi1)cos(phi2)sin^2(delta(lambda)/2)
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    d = R * c
    where R is the radius of the Earth (mean radius = 6,371km)
"""
# Earth radius in km
EARTH_RADIUS = 6371.0


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # Convert degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Calculate differences
    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad

    # Calculate Haversine formula components
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Calculate distance
    distance = EARTH_RADIUS * c
    return distance


def find_nearest_stop(
    user_lat: float, user_lon: float, route: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    if not route:
        return None

    nearest_stop = None
    min_distance = float("inf")

    for stop in route:
        stop_lat = stop["location"]["lat"]
        stop_lon = stop["location"]["lng"]
        distance = calculate_distance(user_lat, user_lon, stop_lat, stop_lon)

        if distance < min_distance:
            min_distance = distance
            nearest_stop = stop
            nearest_stop["distance_from_user_km"] = round(distance, 2)

    return nearest_stop


"""
Pretty print minutes
"""


def prettify(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} minutes"

    hours = minutes // 60
    minutes = minutes % 60

    if hours < 24:
        return f"{hours}h {minutes}"

    days = hours // 24
    hours = hours % 24

    return f"{days}d {hours}h {minutes}m"


"""
Determines Santa's status based on a specific time.
"""


def get_santa_status(
    route: List[Dict[str, Any]], current_time_ms: Optional[float] = None
) -> Tuple[str, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if current_time_ms is None:
        current_time_ms = time.time() * 1000

    msg = ""

    # Find current status
    start_point = route[0]
    end_point = route[-1]

    # Before Christmas
    if current_time_ms < start_point["departure"]:
        time_diff = start_point["departure"] - current_time_ms
        minutes_left = int(time_diff / 1000 / 60)
        time_str = prettify(minutes_left)  # TODO: pretty print this

        msg = (
            f"🎅🏻 **Santa is at the North Pole!** 🏠\n\n"
            f"He is currently preparing the sleigh and feeding the reindeer.\n"
            f"🚀 **Takeoff in:** {time_str}"
        )
        return msg, start_point, route[1]

    # After Christmas
    if current_time_ms > end_point["arrival"]:
        msg = "🎅🏻**Santa has returned to the North Pole!** 😴\n\nChristmas is over for this year. See you next time!"
        return msg, start_point, None

    # Active Scenario
    current_stop = None
    next_stop = None
    for i, stop in enumerate(route):
        arrival = stop["arrival"]
        departure = stop["departure"]

        # Santa is AT this stop
        if arrival <= current_time_ms <= departure:
            current_stop = stop
            next_stop = route[i + 1] if i + 1 < len(route) else None
            # Build message
            msg = (
                f"🎅🏻 **Santa is currently visiting {current_stop['city']}!** \n\n"
                f"He is delivering presents right now in {current_stop['region']}. 🎁"
            )
            return msg, current_stop, next_stop
        # Santa has passed, but has not reached the next
        if current_time_ms < arrival:
            next_stop = stop
            current_stop = route[i - 1] if i > 0 else None

            minutes_left = int((next_stop["arrival"] - current_time_ms) / 1000 / 60)

            # Edge case: in the air before the first stop
            origin = current_stop["city"] if current_stop else "the North Pole"

            # Build message
            msg = (
                f"🎅🏻 **Santa is in the air!** 🛷\n\n"
                f"He has just left **{origin}**.\n"
                f"He is heading to **{next_stop['city']}** and will land in {minutes_left} minutes!"
            )
            return msg, current_stop, next_stop

    return "Santa is currently resting at the North Pole! ❄️", None, None


"""
Returns the arrival time in a custom city.
If the city is in the dataset, return the timestamp from the dataset,
else, use interpolate previous and next stop
"""


def calculate_arrival_time(
    user_lat: float, user_lon: float, route: List[Dict[str, Any]]
) -> Optional[float]:
    if not route or len(route) < 2:
        return None

    best_arrival_time = None
    min_detour = float("inf")  # for the cities that are not in the dataset

    # Iterate through all segments
    for i in range(len(route) - 1):
        stop_a = route[i]
        stop_b = route[i + 1]

        # Coordinates
        lat_a, lon_a = stop_a["location"]["lat"], stop_a["location"]["lng"]
        lat_b, lon_b = stop_b["location"]["lat"], stop_b["location"]["lng"]

        # Distances
        dist_a_b = calculate_distance(lat_a, lon_a, lat_b, lon_b)
        dist_a_user = calculate_distance(lat_a, lon_a, user_lat, user_lon)
        dist_user_b = calculate_distance(user_lat, user_lon, lat_b, lon_b)

        # Detour is how much extra distance is added by visiting the user
        detour = (dist_a_user + dist_user_b) - dist_a_b

        if detour < min_detour:
            min_detour = detour

            # Assuming constant velocity
            fraction = dist_a_user / (dist_a_user + dist_user_b)
            dep_a = stop_a["departure"]
            arr_b = stop_b["arrival"]
            duration = arr_b - dep_a

            best_arrival_time = dep_a + (duration * fraction)

    return best_arrival_time
