import time
from collections import deque
from statistics import median
from typing import Deque, Dict, Tuple


# Stores the deque for total supply and reserves for each pool
class PoolDataStore:
    """
    Implementation of a double ended queue. Deque is preferred over a list because quicker 
    append and pop operations from both the ends of the container. In our case, it allows us to remove stale data 
    (over 10 minutes)
    """
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

    def calculate_median_supply(self) -> int:
        # Compute the median for the total supply
        return median(item["value"] for item in self.total_supply)

    def calculate_median_reserves(self) -> Tuple[int, int]:
        if not self.reserves:
            return (None, None)  # If there are no reserves, return None for both

        # Extract reserve_0 and reserve_1 values from the tuples
        reserve_0_values = [item["value"][0] for item in self.reserves]
        reserve_1_values = [item["value"][1] for item in self.reserves]

        # Calculate the median for each part of the reserves
        median_reserve_0 = median(reserve_0_values)
        median_reserve_1 = median(reserve_1_values)

        return (median_reserve_0, median_reserve_1)
        