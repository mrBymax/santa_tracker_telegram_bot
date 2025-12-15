import datetime
import json

import pytest

from src.santa_bot.services.santa_api import SantaAPI


# Create a temporary test file fixture
@pytest.fixture
def mock_santa_data_file(tmp_path):
    """
    Creates a temporary JSON file with old 2019 data.
    tmp_path is a built-in pytest fixture that cleans up after itself.
    """
    data = {
        "destinations": [
            {
                "id": "old_stop",
                "arrival": 1577181600000,  # Dec 24, 2019
                "departure": 1577181600000,
                "location": {"lat": 0, "lng": 0},
            }
        ]
    }

    # Create a subfolder 'data' in the temp directory to mimic real structure
    d = tmp_path / "data"
    d.mkdir()
    p = d / "santa_test.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_api_normalizes_year(mock_santa_data_file):
    """
    Test that reading 2019 data results in Current Year (or Next Year) data.
    """
    api = SantaAPI("santa_test.json")
    api.data_path = mock_santa_data_file

    route = api.get_route()

    assert len(route) == 1

    stop_ts = route[0]["arrival"]
    stop_date = datetime.datetime.fromtimestamp(stop_ts / 1000)

    current_year = datetime.datetime.now().year

    # The stop year should be >= current year
    assert stop_date.year >= current_year
