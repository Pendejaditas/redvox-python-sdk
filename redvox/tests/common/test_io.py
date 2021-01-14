from datetime import datetime, timedelta
import os
import os.path
import shutil
import tempfile
from typing import Iterator, Optional, Union
from unittest import TestCase

from redvox.api1000.wrapped_redvox_packet.wrapped_packet import WrappedRedvoxPacketM
from redvox.common.date_time_utils import (
    datetime_from_epoch_milliseconds_utc as ms2dt,
    datetime_from_epoch_microseconds_utc as us2dt,
    datetime_to_epoch_milliseconds_utc as dt2ms,
    datetime_to_epoch_microseconds_utc as dt2us,
)
import redvox.common.io as io


def dt_range(start: datetime,
             end: datetime,
             step: timedelta) -> Iterator[datetime]:
    dt: datetime = start
    while dt <= end:
        yield dt
        dt += step


def write_min_api_1000(base_dir: str, file_name: Optional[str] = None) -> str:
    packet: WrappedRedvoxPacketM = WrappedRedvoxPacketM.new()
    packet.set_api(1000.0)
    return packet.write_compressed_to_file(base_dir, file_name)


def write_min_api_900(base_dir: str, file_name: Optional[str] = None) -> str:
    from redvox.api900.wrapped_redvox_packet import WrappedRedvoxPacket
    packet: WrappedRedvoxPacket = WrappedRedvoxPacket()
    packet.set_api(900)
    packet.write_rdvxz(base_dir, file_name)
    return os.path.join(base_dir, packet.default_filename() if file_name is None else file_name)


def copy_api_900(template_path: str,
                 base_dir: str,
                 structured: bool,
                 station_id: str,
                 ts_dt: Union[int, datetime],
                 ext: str = ".rdvxz") -> str:
    ts_ms: int = ts_dt if isinstance(ts_dt, int) else dt2ms(ts_dt)

    target_dir: str
    if structured:
        dt: datetime = ms2dt(ts_ms)
        target_dir = os.path.join(base_dir,
                                  "api900",
                                  f"{dt.year:04}",
                                  f"{dt.month:02}",
                                  f"{dt.day:02}")
    else:
        target_dir = base_dir

    os.makedirs(target_dir, exist_ok=True)

    file_name: str = f"{station_id}_{ts_ms}{ext}"
    file_path: str = os.path.join(target_dir, file_name)
    shutil.copy2(template_path, file_path)

    return file_path


def copy_api_1000(template_path: str,
                  base_dir: str,
                  structured: bool,
                  station_id: str,
                  ts_dt: Union[int, datetime],
                  ext: str = ".rdvxm") -> str:
    ts_us: int = ts_dt if isinstance(ts_dt, int) else dt2us(ts_dt)

    target_dir: str
    if structured:
        dt: datetime = us2dt(ts_us)
        target_dir = os.path.join(base_dir,
                                  "api1000",
                                  f"{dt.year:04}",
                                  f"{dt.month:02}",
                                  f"{dt.day:02}",
                                  f"{dt.hour:02}")
    else:
        target_dir = base_dir

    os.makedirs(target_dir, exist_ok=True)

    file_name: str = f"{station_id}_{ts_us}{ext}"
    file_path: str = os.path.join(target_dir, file_name)
    shutil.copy2(template_path, file_path)

    return file_path


def copy_exact(template_path: str,
               base_dir: str,
               name: str) -> str:
    os.makedirs(base_dir, exist_ok=True)
    file_path: str = os.path.join(base_dir, name)
    shutil.copy2(template_path, file_path)
    return file_path


class IoTests(TestCase):
    def test_is_int_good(self):
        self.assertEqual(0, io._is_int("0"))
        self.assertEqual(1, io._is_int("01"))
        self.assertEqual(1, io._is_int("00001"))
        self.assertEqual(10, io._is_int("000010"))
        self.assertEqual(-10, io._is_int("-000010"))

    def test_is_int_bad(self):
        self.assertIsNone(io._is_int(""))
        self.assertIsNone(io._is_int("000a"))
        self.assertIsNone(io._is_int("foo"))
        self.assertIsNone(io._is_int("1.325"))

    def test_not_none(self):
        self.assertTrue(io._not_none(""))
        self.assertFalse(io._not_none(None))


class IndexEntryTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.temp_dir_path = cls.temp_dir.name

        cls.template_dir: str = os.path.join(cls.temp_dir_path, "templates")
        os.makedirs(cls.template_dir, exist_ok=True)

        cls.unstructured_900_dir: str = os.path.join(cls.temp_dir_path, "unstructured_900")
        os.makedirs(cls.unstructured_900_dir, exist_ok=True)

        cls.unstructured_1000_dir: str = os.path.join(cls.temp_dir_path, "unstructured_1000")
        os.makedirs(cls.unstructured_1000_dir, exist_ok=True)

        cls.unstructured_900_1000_dir: str = os.path.join(cls.temp_dir_path, "unstructured_900_1000")
        os.makedirs(cls.unstructured_900_1000_dir, exist_ok=True)

        cls.template_900_path = os.path.join(cls.template_dir, "template_900.rdvxz")
        cls.template_1000_path = os.path.join(cls.template_dir, "template_1000.rdvxm")

        write_min_api_900(cls.template_dir, "template_900.rdvxz")
        write_min_api_1000(cls.template_dir, "template_1000.rdvxm")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()

    def test_from_path_900_good(self) -> None:
        path: str = copy_exact(self.template_900_path, self.unstructured_900_dir, "0000000900_1609459200000.rdvxz")
        entry: io.IndexEntry = io.IndexEntry.from_path(path)
        self.assertIsNotNone(entry)
        self.assertEqual("0000000900", entry.station_id)
        self.assertEqual(io.ApiVersion.API_900, entry.api_version)
        self.assertEqual(datetime(2021, 1, 1), entry.date_time)
        self.assertEqual(".rdvxz", entry.extension)

    def test_from_path_900_good_short_station_id(self) -> None:
        path: str = copy_exact(self.template_900_path, self.unstructured_900_dir, "9_1609459200000.rdvxz")
        entry: io.IndexEntry = io.IndexEntry.from_path(path)
        self.assertEqual("9", entry.station_id)

    def test_from_path_900_good_long_station_id(self) -> None:
        path: str = copy_exact(self.template_900_path, self.unstructured_900_dir, "00000009000000000900_1609459200000.rdvxz")
        entry: io.IndexEntry = io.IndexEntry.from_path(path)
        self.assertEqual("00000009000000000900", entry.station_id)

    def test_from_path_900_no_station_id(self) -> None:
        path: str = copy_exact(self.template_900_path, self.unstructured_900_dir, "_1609459200000.rdvxz")
        entry: io.IndexEntry = io.IndexEntry.from_path(path)
        self.assertIsNone(entry)

    def test_from_path_900_bad_station_id(self) -> None:
        path: str = copy_exact(self.template_900_path, self.unstructured_900_dir, "foo_1609459200000.rdvxz")
        entry: io.IndexEntry = io.IndexEntry.from_path(path)
        self.assertIsNone(entry)

    def test_from_path_900_unix_epoch(self) -> None:
        path: str = copy_exact(self.template_900_path, self.unstructured_900_dir, "00000009000000000900_0.rdvxz")
        entry: io.IndexEntry = io.IndexEntry.from_path(path)
        self.assertEqual(datetime(1970, 1, 1), entry.date_time)

    def test_from_path_900_neg_epoch(self) -> None:
        path: str = copy_exact(self.template_900_path, self.unstructured_900_dir, "00000009000000000900_-31536000000.rdvxz")
        entry: io.IndexEntry = io.IndexEntry.from_path(path)
        self.assertEqual(datetime(1969, 1, 1), entry.date_time)

    def test_from_path_900_no_epoch(self) -> None:
        path: str = copy_exact(self.template_900_path, self.unstructured_900_dir, "00000009000000000900_.rdvxz")
        entry: io.IndexEntry = io.IndexEntry.from_path(path)
        self.assertIsNone(entry)

    def test_from_path_900_bad_epoch(self) -> None:
        path: str = copy_exact(self.template_900_path, self.unstructured_900_dir, "00000009000000000900_foo.rdvxz")
        entry: io.IndexEntry = io.IndexEntry.from_path(path)
        self.assertIsNone(entry)

    def test_from_path_900_different_ext(self) -> None:
        path: str = copy_exact(self.template_900_path, self.unstructured_900_dir, "0_0.foo")
        entry: io.IndexEntry = io.IndexEntry.from_path(path)
        self.assertEqual(".foo", entry.extension)

    def test_from_path_900_no_ext(self) -> None:
        path: str = copy_exact(self.template_900_path, self.unstructured_900_dir, "0_0")
        entry: io.IndexEntry = io.IndexEntry.from_path(path)
        self.assertEqual("", entry.extension)

    def test_from_path_900_no_split(self) -> None:
        path: str = copy_exact(self.template_900_path, self.unstructured_900_dir, "00.rdvxz")
        entry: io.IndexEntry = io.IndexEntry.from_path(path)
        self.assertIsNone(entry)

    def test_from_path_900_multi_split(self) -> None:
        path: str = copy_exact(self.template_900_path, self.unstructured_900_dir, "0_0_0.rdvxz")
        entry: io.IndexEntry = io.IndexEntry.from_path(path)
        self.assertIsNone(entry)


class IndexTests(TestCase):
    pass


class ReadFilterTests(TestCase):
    pass
