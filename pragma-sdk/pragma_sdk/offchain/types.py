from enum import StrEnum, unique
from typing import Dict, Optional, Tuple

PublishEntriesAPIResult = Tuple[Optional[Dict], Optional[Dict]]


@unique
class Interval(StrEnum):
    ONE_MINUTE = "1min"
    FIFTEEN_MINUTES = "15min"
    ONE_HOUR = "1h"
    TWO_HOURS = "2h"

    def serialize(self):
        return {self.value: None}
