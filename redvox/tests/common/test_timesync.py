"""
tests for timesync
"""
import unittest
import numpy as np
import redvox.tests as tests
from typing import List
from redvox.common import sensor_data as sd, timesync as ts
from redvox.api900 import reader


class TimesyncTest(unittest.TestCase):
    def setUp(self) -> None:
        packets = reader.read_rdvxz_file_range(tests.TEST_DATA_DIR, structured_layout=False, redvox_ids=["1637680001"],
                                               concat_continuous_segments=False)
        self.wrapped_packets_fs: List[reader.WrappedRedvoxPacket] = packets["1637680001:976500716"]
        stations = sd.load_file_range_from_api900(tests.TEST_DATA_DIR, structured_layout=False,
                                                  redvox_ids=["1637680001"], concat_continuous_segments=False)
        self.time_sync_analysis = ts.TimeSyncAnalysis(stations[0])

    def test_my_test(self):
        test_timesync = ts.TimeSyncData()
        self.assertEqual(test_timesync.sample_rate_hz, None)

    def test_validate_sensors(self):
        test_ts = ts.TimeSyncData()
        test_ts.station_id = "test"
        test_ts.sample_rate_hz = 80.0
        test_ts.station_start_timestamp = 1
        other_ts = ts.TimeSyncData()
        other_ts.station_id = "test"
        other_ts.sample_rate_hz = 80.0
        tsa_test = ts.TimeSyncAnalysis()
        tsa_test.station_id = "test"
        tsa_test.timesync_data = [test_ts, other_ts]
        tsa_test.sample_rate_hz = 80.0
        tsa_test.station_start_timestamp = 1
        # there should be a warning message
        self.assertFalse(ts.validate_sensors(tsa_test))

    def test_get_time_sync_data(self):
        self.assertEqual(len(self.time_sync_analysis.get_start_times()), len(self.wrapped_packets_fs))
        self.assertEqual(len(self.time_sync_analysis.get_latencies()), len(self.wrapped_packets_fs))
        self.assertEqual(len(self.time_sync_analysis.get_offsets()), len(self.wrapped_packets_fs))
        self.assertEqual(self.time_sync_analysis.get_best_latency(), 69664.0)

    def test_compute_tri_message_stats(self):
        self.assertEqual(self.time_sync_analysis.get_latencies()[0], 69664.0)
        self.assertEqual(self.time_sync_analysis.get_offsets()[0], -22906528)

    def test_find_bad_packets(self):
        self.assertEqual(len(self.time_sync_analysis.get_bad_packets()), 0)

    def test_evaluate_latencies_and_offsets(self):
        self.assertEqual(len(self.time_sync_analysis.get_latencies()), len(self.wrapped_packets_fs))
        self.assertEqual(len(self.time_sync_analysis.get_offsets()), len(self.wrapped_packets_fs))
        self.assertEqual(self.time_sync_analysis.get_best_latency(), 69664.0)
        self.assertEqual(self.time_sync_analysis.best_latency_index, 0)

    def test_get_latency_mean(self):
        self.assertAlmostEqual(self.time_sync_analysis.get_mean_latency(), 118049.66, 2)

    def test_get_latency_std_dev(self):
        self.assertAlmostEqual(self.time_sync_analysis.get_latency_std(), 84458.71, 2)

    def test_get_offset_mean(self):
        self.assertAlmostEqual(self.time_sync_analysis.get_mean_offset(), -22903096.02, 2)

    def test_get_offset_std_dev(self):
        self.assertAlmostEqual(self.time_sync_analysis.get_offset_std(), 91847.39, 2)

    def test_get_best_start_time(self):
        best_start = self.time_sync_analysis.get_best_start_time()
        self.assertEqual(1532459197088000, best_start)

    def test_correct_time_array(self):
        """ Example: A sample is taken every 0.5 seconds, and a file has 5 seconds (10 samples). Let's say we sampled
        for a total of 20 seconds (4 files, 40 samples). At the beginning of each file (every 10th sample, or every
        5 seconds), there is a start mach time and a start epoch time. Rebuild the time array
        with the packet with the lowest latency being the best start time. In this case, the best latency is 1,
        which occurs in file 2, which starts at 4 seconds.  In the end we should get 40 timestamps,
        starting at -1.0 and increasing at a rate of 0.5 seconds, and the 11th sample (idx 10) = 4 seconds. """
        # the revised start times are in microseconds, but the corrected time is in seconds
        tsd_one = ts.TimeSyncData()
        tsd_one.packet_start_time = 1000000
        tsd_one.best_latency = 2
        tsd_one.sample_rate_hz = 2
        tsd_one.station_start_timestamp = 0
        tsd_two = ts.TimeSyncData()
        tsd_two.packet_start_time = 4000000
        tsd_two.best_latency = 1
        tsd_two.sample_rate_hz = 2
        tsd_thr = ts.TimeSyncData()
        tsd_thr.packet_start_time = 8000000
        tsd_thr.best_latency = 2
        tsd_thr.sample_rate_hz = 2
        tsd_for = ts.TimeSyncData()
        tsd_for.packet_start_time = 13000000
        tsd_for.best_latency = 2
        tsd_for.sample_rate_hz = 2
        tsa_one = ts.TimeSyncAnalysis()
        tsa_one.station_id = "test_station"
        tsa_one.timesync_data = [tsd_one, tsd_two, tsd_thr, tsd_for]
        tsa_one.best_latency_index = 1
        tsa_one.sample_rate_hz = 2
        file_samples = 10  # 10 samples per file
        correct_time_array_sec = ts.update_evenly_sampled_time_array(tsa_one, file_samples)

        self.assertTrue(np.array_equal(np.arange(-1.0, 19.0, 0.5), correct_time_array_sec))
        self.assertEqual(4.0, correct_time_array_sec[10])
        self.assertTrue(isinstance(correct_time_array_sec, np.ndarray))