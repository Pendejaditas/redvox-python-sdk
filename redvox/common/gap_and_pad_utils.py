import pandas as pd
import numpy as np

from redvox.api1000.wrapped_redvox_packet.sensors.audio import AudioCodec
from redvox.api1000.wrapped_redvox_packet.sensors.location import LocationProvider
from redvox.api1000.wrapped_redvox_packet.sensors.image import ImageCodec
from redvox.api1000.wrapped_redvox_packet.station_information import NetworkType, PowerState, CellServiceState

# default maximum number of points required to brute force calculating gap timestamps
DEFAULT_MAX_BRUTE_FORCE_GAP_TIMESTAMPS: int = 5000


def pad_data(
        expected_start: float,
        expected_end: float,
        data_df: pd.DataFrame,
        sample_interval_micros: float,
) -> pd.DataFrame:
    """
    Pad the start and end of the dataframe with np.nan
    :param expected_start: timestamp indicating start time of the data to pad from
    :param expected_end: timestamp indicating end time of the data to pad from
    :param data_df: dataframe with timestamps as column "timestamps"
    :param sample_interval_micros: constant sample interval in microseconds
    :return: dataframe padded with np.nans in front and back to meet full size of expected start and end
    """
    # extract the necessary information to pad the data
    data_time_stamps = data_df["timestamps"].to_numpy()
    first_data_timestamp = data_time_stamps[0]
    last_data_timestamp = data_time_stamps[-1]
    result_df = data_df.copy()
    result_before_update_length = len(result_df) - 1
    # FRONT/END GAP FILL!  calculate the audio samples missing based on inputs
    if expected_start < first_data_timestamp:
        start_diff = first_data_timestamp - expected_start
        num_missing_samples = np.floor(start_diff / sample_interval_micros)
        if num_missing_samples > 0:
            # add the gap data to the result dataframe
            result_df = add_dataless_timestamps_to_df(
                result_df,
                0,
                sample_interval_micros,
                num_missing_samples,
                True
            )
    if expected_end > last_data_timestamp:
        last_diff = expected_end - last_data_timestamp
        num_missing_samples = np.floor(last_diff / sample_interval_micros)
        if num_missing_samples > 0:
            # add the gap data to the result dataframe
            result_df = add_dataless_timestamps_to_df(
                result_df,
                result_before_update_length,
                sample_interval_micros,
                num_missing_samples
            )
    return result_df.sort_values("timestamps", ignore_index=True)


def fill_gaps(
        data_df: pd.DataFrame,
        sample_interval_micros: float,
        gap_time_micros: float,
        num_points_to_brute_force: int = DEFAULT_MAX_BRUTE_FORCE_GAP_TIMESTAMPS,
) -> pd.DataFrame:
    """
    fills gaps in the dataframe with np.nan by interpolating timestamps based on the mean expected sample interval
    :param data_df: dataframe with timestamps as column "timestamps"
    :param sample_interval_micros: sample interval in microseconds
    :param gap_time_micros: minimum amount of microseconds between data points that would indicate a gap
    :param num_points_to_brute_force: maximum number of points to calculate when filling a gap
    :return: dataframe without gaps
    """
    # extract the necessary information to compute gap size and gap timestamps
    data_time_stamps = data_df["timestamps"].to_numpy()
    first_data_timestamp = data_time_stamps[0]
    last_data_timestamp = data_time_stamps[-1]
    data_duration_micros = last_data_timestamp - first_data_timestamp
    num_points = len(data_time_stamps)
    # add one to calculation to include the last timestamp
    expected_num_points = np.ceil(data_duration_micros / sample_interval_micros) + 1
    # gap duration cannot be less than sample interval + one standard deviation
    gap_time_micros = np.max([sample_interval_micros, gap_time_micros])
    result_df = data_df.copy()
    # if there are less points than our expected amount, we have gaps to fill
    if num_points < expected_num_points:
        # if the data we're looking at is short enough, we can start comparing points
        if num_points < num_points_to_brute_force:
            # look at every timestamp difference
            timestamp_diffs = np.diff(data_time_stamps)
            for index in np.where(timestamp_diffs > gap_time_micros)[0]:
                # calc samples to add, subtracting 1 to prevent copying last timestamp
                num_new_samples = (
                        np.ceil(timestamp_diffs[index] / sample_interval_micros) - 1
                )
                if timestamp_diffs[index] > gap_time_micros and num_new_samples > 0:
                    # add the gap data to the result dataframe
                    result_df = add_dataless_timestamps_to_df(
                        result_df,
                        index,
                        sample_interval_micros,
                        num_new_samples,
                    )
                    if len(result_df) >= expected_num_points:
                        break  # stop the for loop execution when enough points are added
        else:
            # too many points to check, divide and conquer using recursion!
            half_samples = int(num_points / 2)
            first_data_df = data_df.iloc[:half_samples].copy().reset_index(drop=True)
            second_data_df = data_df.iloc[half_samples:].copy().reset_index(drop=True)
            # give half the samples to each recursive call
            first_data_df = fill_gaps(
                first_data_df,
                sample_interval_micros,
                gap_time_micros,
                num_points_to_brute_force,
            )
            second_data_df = fill_gaps(
                second_data_df,
                sample_interval_micros,
                gap_time_micros,
                num_points_to_brute_force,
            )
            result_df = first_data_df.append(second_data_df, ignore_index=True)
            if result_df["timestamps"].size < expected_num_points:
                mid_df = data_df.iloc[half_samples-1:half_samples+1].copy().reset_index(drop=True)
                mid_df = fill_gaps(mid_df, sample_interval_micros, gap_time_micros, num_points_to_brute_force)
                mid_df = mid_df.iloc[1:len(mid_df["timestamps"])-1]
                result_df = result_df.append(mid_df, ignore_index=True)
    return result_df.sort_values("timestamps", ignore_index=True)


def fill_audio_gaps(
        timestamps: np.array,
        audio_data: np.array,
        sample_interval_micros: float,
        samples_per_packet: int,
        num_points_to_brute_force: int = DEFAULT_MAX_BRUTE_FORCE_GAP_TIMESTAMPS,
        gap_upper_limit: float = .9,
        gap_lower_limit: float = .02
) -> pd.DataFrame:
    """
    fills gaps in the dataframe with np.nan by interpolating timestamps based on the mean expected sample interval
      ignores gaps with duration less than or equal to packet length * gap_lower_limit

      converts gaps with duration greater than or equal to packet length * gap_upper_limit into a multiple of
      packet length
    :param timestamps: array of timestamps for the data
    :param audio_data: array of data points
    :param sample_interval_micros: sample interval in microseconds
    :param samples_per_packet: number of samples to create per packet
    :param num_points_to_brute_force: maximum number of timestamps required to check the timestamps for gaps
    :param gap_upper_limit: percentage of packet length required to confirm gap is at least 1 packet
    :param gap_lower_limit: percentage of packet length required to disregard gap
    :return: dataframe without gaps
    """
    result_df = pd.DataFrame(np.transpose([timestamps, timestamps, audio_data]),
                             columns=["timestamps", "unaltered_timestamps", "microphone"])
    num_points = len(timestamps)
    # if there are less points than our expected amount, we have gaps to fill
    if num_points < num_points_to_brute_force:
        # look at every timestamp difference
        timestamp_diffs = np.diff(timestamps)
        for index in np.where(timestamp_diffs > sample_interval_micros)[0]:
            num_samples = np.ceil(timestamp_diffs[index] / sample_interval_micros) - 1
            if num_samples <= samples_per_packet * gap_lower_limit:
                break  # difference too small, no gap
            elif num_samples >= samples_per_packet * gap_upper_limit:
                # add samples per packet for each packet missing
                num_samples = samples_per_packet * np.floor(num_samples / (samples_per_packet * gap_upper_limit))
            # add the gap data to the result dataframe
            result_df = add_dataless_timestamps_to_df(
                result_df,
                index,
                sample_interval_micros,
                num_samples,
            )
    else:
        # too many points to check, divide and conquer using recursion!
        half_samples = int(num_points / 2)
        first_data_timestamps = timestamps[:half_samples]
        first_audio_data = audio_data[:half_samples]
        second_data_timestamps = timestamps[half_samples:]
        second_audio_data = audio_data[half_samples:]
        # give half the samples to each recursive call
        first_data_timestamps = fill_audio_gaps(
            first_data_timestamps,
            first_audio_data,
            sample_interval_micros,
            samples_per_packet,
        )
        second_data_timestamps = fill_audio_gaps(
            second_data_timestamps,
            second_audio_data,
            sample_interval_micros,
            samples_per_packet,
        )
        result_df = first_data_timestamps.append(second_data_timestamps, ignore_index=True)
        mid_timestamps = timestamps[half_samples-1:half_samples+1]
        mid_audio_data = audio_data[half_samples-1:half_samples+1]
        mid_df = fill_audio_gaps(mid_timestamps, mid_audio_data, sample_interval_micros, samples_per_packet)
        if len(mid_df["timestamps"]) > 2:
            mid_df = mid_df.iloc[1:len(mid_df["timestamps"])-1]
            result_df = result_df.append(mid_df, ignore_index=True)
    return result_df.sort_values("timestamps", ignore_index=True)


def add_dataless_timestamps_to_df(dataframe: pd.DataFrame,
                                  start_index: int,
                                  sample_interval_micros: float,
                                  num_samples_to_add: int,
                                  add_to_start: bool = False,) -> pd.DataFrame:
    """
    adds dataless timestamps directly to a dataframe that already contains data
      Note:
        * dataframe must not be empty
        * start_index must be non-negative and less than the length of dataframe
        * num_samples_to_add must be greater than 0
        * the points are added onto the end and the result is not sorted
    :param dataframe: dataframe to add dataless timestamps to
    :param start_index: index of the dataframe to use as starting point for creating new values
    :param sample_interval_micros: sample interval in microseconds of the timestamps
    :param num_samples_to_add: the number of timestamps to create
    :param add_to_start: if True, subtracts sample_interval_micros from start_timestamp, default False
    :return: updated dataframe with synthetic data points
    """
    if len(dataframe) > start_index and len(dataframe) > 0 and num_samples_to_add > 0:
        start_timestamp = dataframe["timestamps"][start_index]
        dataframe = dataframe.append(
            create_dataless_timestamps_df(start_timestamp, sample_interval_micros,
                                          dataframe.columns, num_samples_to_add, add_to_start),
            ignore_index=True)
    return dataframe


def create_dataless_timestamps_df(
        start_timestamp: float,
        sample_interval_micros: float,
        columns: pd.Index,
        num_samples_to_add: int,
        add_to_start: bool = False,
) -> pd.DataFrame:
    """
    Creates an empty dataframe with num_samples_to_add timestamps, using columns as the columns
    the first timestamp created is 1 sample_interval_s from the start_timestamp
    :param start_timestamp: timestamp in microseconds since epoch UTC to start calculating other timestamps from
    :param sample_interval_micros: fixed sample interval in microseconds since epoch UTC
    :param columns: dataframe the non-timestamp columns of the dataframe
    :param num_samples_to_add: the number of timestamps to create
    :param add_to_start: if True, subtracts sample_interval_s from start_timestamp, default False
    :return: dataframe with timestamps and no data
    """
    empty_df = pd.DataFrame([], columns=columns)
    if num_samples_to_add > 0:
        for column_index in columns:
            if column_index == "timestamps":
                if add_to_start:
                    sample_interval_micros = -sample_interval_micros
                empty_df[column_index] = (
                        start_timestamp + np.arange(1, num_samples_to_add + 1) * sample_interval_micros
                )
            elif column_index == "location_provider":
                empty_df[column_index] = LocationProvider.UNKNOWN
            elif column_index == "image_codec":
                empty_df[column_index] = ImageCodec.UNKNOWN
            elif column_index == "audio_codec":
                empty_df[column_index] = AudioCodec.UNKNOWN
            elif column_index == "network_type":
                empty_df[column_index] = NetworkType.UNKNOWN_NETWORK
            elif column_index == "power_state":
                empty_df[column_index] = PowerState.UNKNOWN_POWER_STATE
            elif column_index == "cell_service":
                empty_df[column_index] = CellServiceState.UNKNOWN
            else:
                empty_df[column_index] = np.nan
    return empty_df