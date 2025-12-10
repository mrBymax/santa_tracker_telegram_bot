from src.santa_bot.core.tracker import get_santa_status
from src.santa_bot.services.santa_api import SantaAPI

# Initialize API once
api = SantaAPI()
route = api.get_route()


def test_santa_at_north_pole_before_start():
    # Set time to 1 hour BEFORE the first stop (Santa's Village departure)
    # Santa's Village is usually the first stop in the JSON
    start_time = route[0]["arrival"]
    fake_now = start_time - (60 * 60 * 1000)  # 1 hour before in ms

    msg, current, next_s = get_santa_status(route, current_time_ms=fake_now)

    # He should be "in the air" heading to the first real stop, or at the pole
    # Note: Your logic might handle "before start" as "resting" or "heading to stop 1"
    # Adjust assertion based on your specific logic preferences
    assert "North Pole" in msg


def test_santa_visiting_a_city():
    # Pick the 2nd stop (usually Provideniya or similar)
    target_stop = route[1]

    # Set time to be exactly inside the arrival and departure window
    # arrival + 10 seconds
    fake_now = target_stop["arrival"] + 10000

    msg, current, next_s = get_santa_status(route, current_time_ms=fake_now)

    if current is not None:
        assert current["city"] == target_stop["city"]
    assert "currently visiting" in msg
    assert target_stop["city"] in msg


def test_santa_flying_between_cities():
    # Pick two consecutive stops
    stop_a = route[1]
    stop_b = route[2]

    # Set time to be right in the middle of the flight
    # (After A departs, before B arrives)
    flight_duration = stop_b["arrival"] - stop_a["departure"]
    fake_now = stop_a["departure"] + (flight_duration / 2)

    msg, current, next_s = get_santa_status(route, current_time_ms=fake_now)

    assert "in the air" in msg
    assert f"left **{stop_a['city']}" in msg
    assert f"heading to **{stop_b['city']}" in msg


def test_santa_finished_route():
    # Set time to 1 day AFTER the last stop
    last_stop = route[-1]
    fake_now = last_stop["departure"] + (24 * 60 * 60 * 1000)

    msg, current, next_s = get_santa_status(route, current_time_ms=fake_now)

    assert "resting" in msg
