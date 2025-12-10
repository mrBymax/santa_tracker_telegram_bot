import math
from typing import Any, Dict, List, Optional

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
