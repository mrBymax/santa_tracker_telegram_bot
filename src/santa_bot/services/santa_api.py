import datetime
import json
from pathlib import Path
from typing import Any, Dict, List


class SantaAPI:
    def __init__(self, data_file_name: str = "santa_en.json"):
        self._route_cache = None
        self.data_path = Path(__file__).resolve().parents[3] / "data" / data_file_name

    """
    Loads the route data from the specified file and normalises the timestamps
    """

    def get_route(self) -> List[Dict[str, Any]]:
        if self._route_cache:
            return self._route_cache

        if not self.data_path.exists():
            raise FileNotFoundError(
                f"Could not find any Santa Data at {self.data_path}"
            )

        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_destinations = data.get("destinations", [])
            self._route_cache = self._normalize_timestamps(raw_destinations)

            return self._route_cache

        except json.JSONDecodeError:
            print(f"Error: Could not parse JSON data from {self.data_path}")
            return []

    def _normalize_timestamps(
        self, destinations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        first_stop_ts = destinations[0]["departure"] / 1000
        source_year = datetime.datetime.fromtimestamp(first_stop_ts).year

        now = datetime.datetime.now()
        if now.month == 12 and now.day > 25:
            target_year = now.year + 1
        else:
            target_year = now.year

        year_offset = target_year - source_year

        normalized_data = []
        for stop in destinations:
            new_stop = stop.copy()
            new_stop["arrival"] = self._shift_timestamp(stop["arrival"], year_offset)
            new_stop["departure"] = self._shift_timestamp(
                stop["departure"], year_offset
            )
            normalized_data.append(new_stop)

        return normalized_data

    def _shift_timestamp(self, ts_ms: int, year_offset: int) -> int:
        if ts_ms <= 0:
            return ts_ms
        dt = datetime.datetime.fromtimestamp(ts_ms / 1000)
        try:
            new_dt = dt.replace(year=dt.year + year_offset)
        except ValueError:
            new_dt = dt.replace(year=dt.year + year_offset, day=28)
        return int(new_dt.timestamp() * 1000)


if __name__ == "__main__":
    try:
        api = SantaAPI()
        route = api.get_route()
        print(f"Successfully loaded {len(route)} stops")
        if route:
            print(
                f"First stop time adjusted to: {datetime.datetime.fromtimestamp(route[0]['departure'] / 1000)}"
            )

    except FileNotFoundError as e:
        print(f"Error: {e}")
