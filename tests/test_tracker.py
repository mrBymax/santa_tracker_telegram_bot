from src.santa_bot.core.tracker import calculate_distance, find_nearest_stop


def test_calculate_distance_same_point():
    """Distance to self should be 0."""
    assert calculate_distance(52.5200, 13.4050, 52.5200, 13.4050) == 0.0


def test_calculate_distance_known_cities():
    """
    Test distance between Berlin (52.52, 13.405) and Paris (48.8566, 2.3522).
    Real world distance is approx 878 km.
    """
    dist = calculate_distance(52.5200, 13.4050, 48.8566, 2.3522)
    # Allow a margin of error (e.g., +/- 5km) due to float precision
    assert 870 < dist < 885


def test_find_nearest_stop():
    """
    Given a user in London, and stops in New York, Paris, and Tokyo,
    it should return Paris.
    """
    mock_route = [
        {
            "id": "nyc",
            "city": "New York",
            "location": {"lat": 40.7128, "lng": -74.0060},
        },
        {"id": "par", "city": "Paris", "location": {"lat": 48.8566, "lng": 2.3522}},
        {"id": "tok", "city": "Tokyo", "location": {"lat": 35.6762, "lng": 139.6503}},
    ]

    # User is in London (51.5074, -0.1278) -> Paris is closest
    nearest = find_nearest_stop(51.5074, -0.1278, mock_route)

    assert nearest is not None
    assert nearest["id"] == "par"

    # Ensure our logic attached the calculated distance
    assert "distance_from_user_km" in nearest
