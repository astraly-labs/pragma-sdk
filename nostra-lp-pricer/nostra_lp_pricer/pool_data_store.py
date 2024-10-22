import time
from collections import deque
from statistics import median
from typing import Deque, Dict


# Stores the deque for total supply and reserves for each pool
class PoolDataStore:
    def __init__(self, max_age: int):
        self.total_supply: Deque[Dict] = deque()
        self.reserves: Deque[Dict] = deque()
        self.max_age = max_age  # In seconds (600 for 10 minutes)

    def append_total_supply(self, supply: float):
        current_time = time.time()
        self.total_supply.append({"timestamp": current_time, "value": supply})
        self._clean_old_data(self.total_supply)

    def append_reserves(self, reserves: float):
        current_time = time.time()
        self.reserves.append({"timestamp": current_time, "value": reserves})
        self._clean_old_data(self.reserves)

    def _clean_old_data(self, data_queue: Deque[Dict]):
        current_time = time.time()
        # Remove data older than max_age (10 minutes)
        while data_queue and (current_time - data_queue[0]["timestamp"]) > self.max_age:
            data_queue.popleft()

    def calculate_median_supply(self):
        return median(item["value"] for item in self.total_supply)

    def calculate_median_reserves(self):
        return median(item["value"] for item in self.reserves)
