"""
This module contains utilies for working with dates and times.
"""

import datetime

MICROSECONDS_PER_SECOND = 1_000_000.0
MILLISECONDS_PER_SECONDS = 1_000.0


def microseconds_to_seconds(microseconds: float) -> float:
    """
    Converts microseconds to seconds.
    :param microseconds: The microseconds to convert to seconds.
    :return: Seconds from microseconds.
    """
    return microseconds / MICROSECONDS_PER_SECOND


def seconds_to_microseconds(seconds: float) -> float:
    return seconds * MICROSECONDS_PER_SECOND


def milliseconds_to_seconds(milliseconds: float) -> float:
    return milliseconds / MICROSECONDS_PER_SECOND


class DateIterator:
    def __init__(self,
                 start_timestamp_utc_s: int,
                 end_timestamp_utc_s: int):
        self.start_dt = datetime.datetime.utcfromtimestamp(start_timestamp_utc_s)
        self.end_dt = datetime.datetime.utcfromtimestamp(end_timestamp_utc_s)
        self._one_day = datetime.timedelta(days=1)

    def __iter__(self):
        return self

    def next(self) -> (str, str, str):
        if self.start_dt > self.end_dt:
            raise StopIteration()

        year = str(self.start_dt.year)
        month = f"{self.start_dt.month:02}"
        day = f"{self.start_dt.day:02}"

        self.start_dt += self._one_day

        return year, month, day
