"""
Defines generic sensor data and metadata for API-independent analysis
all timestamps are integers in microseconds unless otherwise stated
"""
import enum
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

import redvox.common.date_time_utils as dtu
from redvox.api1000.wrapped_redvox_packet.wrapped_packet import WrappedRedvoxPacketM
from redvox.api1000.wrapped_redvox_packet.sensors import xyz, single


class SensorType(enum.Enum):
    """
    Enumeration of possible types of sensors to read data from
    """

    UNKNOWN_SENSOR = 0  # unknown sensor
    ACCELEROMETER = 1  # meters/second^2
    AMBIENT_TEMPERATURE = 2  # degrees Celsius
    AUDIO = 3  # normalized counts
    COMPRESSED_AUDIO = 4  # bytes (codec specific)
    GRAVITY = 5  # meters/second^2
    GYROSCOPE = 6  # radians/second
    IMAGE = 7  # bytes (codec specific)
    LIGHT = 8  # lux
    LINEAR_ACCELERATION = 9  # meters/second^2
    LOCATION = 10  # See standard
    MAGNETOMETER = 11  # microtesla
    ORIENTATION = 12  # radians
    PRESSURE = 13  # kilopascal
    PROXIMITY = 14  # on, off, cm
    RELATIVE_HUMIDITY = 15  # percentage
    ROTATION_VECTOR = 16  # Unitless
    INFRARED = 17  # this is proximity
    STATION_HEALTH = 18
    # battery charge and current level, phone internal temperature, network source and strength,
    # available RAM of the system, cell service status, amount of hard disk space left, power charging state

    @staticmethod
    def type_from_str(type_str: str) -> "SensorType":
        """
        converts a string to a sensor type
        :param type_str: string to convert
        :return: a sensor type, UNKNOWN_SENSOR is the default for invalid inputs
        """
        if type_str.lower() == "mic" or type_str.lower() == "audio":
            return SensorType.AUDIO
        elif type_str.lower() == "accelerometer" or type_str.lower() == "accel":
            return SensorType.ACCELEROMETER
        elif type_str.lower() == "ambient_temperature":
            return SensorType.AMBIENT_TEMPERATURE
        elif type_str.lower() == "compressed_audio":
            return SensorType.COMPRESSED_AUDIO
        elif type_str.lower() == "gravity":
            return SensorType.GRAVITY
        elif type_str.lower() == "gyroscope" or type_str.lower() == "gyro":
            return SensorType.GYROSCOPE
        elif type_str.lower() == "image":
            return SensorType.IMAGE
        elif type_str.lower() == "light":
            return SensorType.LIGHT
        elif (
            type_str.lower() == "linear_acceleration"
            or type_str.lower() == "linear_accel"
        ):
            return SensorType.LINEAR_ACCELERATION
        elif type_str.lower() == "location" or type_str.lower() == "loc":
            return SensorType.LOCATION
        elif type_str.lower() == "magnetometer" or type_str.lower() == "mag":
            return SensorType.MAGNETOMETER
        elif type_str.lower() == "orientation":
            return SensorType.ORIENTATION
        elif (
            type_str.lower() == "pressure"
            or type_str.lower() == "bar"
            or type_str.lower() == "barometer"
        ):
            return SensorType.PRESSURE
        elif type_str.lower() == "proximity" or type_str.lower() == "infrared":
            return SensorType.PROXIMITY
        elif type_str.lower() == "relative_humidity":
            return SensorType.RELATIVE_HUMIDITY
        elif type_str.lower() == "rotation_vector":
            return SensorType.ROTATION_VECTOR
        else:
            return SensorType.UNKNOWN_SENSOR


class SensorData:
    """
    Generic SensorData class for API-independent analysis
    Properties:
        name: string, name of sensor
        type: SensorType, enumerated type of sensor
        data_df: dataframe of the sensor data; always has timestamps as the first column,
                    the other columns are the data fields
        sample_rate: float, sample rate in Hz of the sensor, default np.nan, usually 1/sample_interval_s
        sample_interval_s: float, mean duration in seconds between samples, default np.nan, usually 1/sample_rate
        sample_interval_std_s: float, standard deviation in seconds between samples, default np.nan
        is_sample_rate_fixed: bool, True if sample rate is constant, default False
        timestamps_altered: bool, True if timestamps in the sensor have been altered from their original values
                            default False
    """

    def __init__(
        self,
        sensor_name: str,
        sensor_data: pd.DataFrame,
        sensor_type: SensorType = SensorType.UNKNOWN_SENSOR,
        sample_rate: float = np.nan,
        sample_interval_s: float = np.nan,
        sample_interval_std_s: float = np.nan,
        is_sample_rate_fixed: bool = False,
        are_timestamps_altered: bool = False,
    ):
        """
        initialize the sensor data with params
        :param sensor_name: name of the sensor
        :param sensor_type: enumerated type of the sensor, default SensorType.UNKNOWN_SENSOR
        :param sensor_data: dataframe with the timestamps and sensor data; first column is always the timestamps,
                            the other columns are the data channels in the sensor
        :param sample_rate: sample rate in hz of the data
        :param sample_interval_s: sample interval in seconds of the data
        :param sample_interval_std_s: std dev of sample interval in seconds of the data
        :param is_sample_rate_fixed: if True, sample rate is constant for all data, default False
        :param are_timestamps_altered: if True, timestamps in the sensor have been altered from their
                                        original values, default False
        """
        if "timestamps" not in sensor_data.columns:
            raise AttributeError(
                'SensorData requires the data frame to contain a column titled "timestamps"'
            )
        self.name: str = sensor_name
        self.type: SensorType = sensor_type
        self.data_df: pd.DataFrame = sensor_data
        self.sample_rate: float = sample_rate
        self.sample_interval_s: float = sample_interval_s
        self.sample_interval_std_s: float = sample_interval_std_s
        self.is_sample_rate_fixed: bool = is_sample_rate_fixed
        self.timestamps_altered: bool = are_timestamps_altered
        self.sort_by_data_timestamps()
        # todo: store the non-consecutive timestamp indices (idk how to find those)

    def is_sample_interval_invalid(self) -> bool:
        """
        :return: True if sample interval is np.nan or equal to 0.0
        """
        return np.isnan(self.sample_interval_s) or self.sample_interval_s == 0.0

    def organize_and_update_stats(self) -> "SensorData":
        """
        sorts the data by timestamps, then if the sample rate is not fixed, recalculates the sample rate, interval,
            and interval std dev.  If there is only one value, sets the sample rate, interval, and interval std dev
            to np.nan.  Updates the SensorData object with the new values
        :return: updated version of self
        """
        self.sort_by_data_timestamps()
        if not self.is_sample_rate_fixed:
            if self.num_samples() > 1:
                timestamp_diffs = np.diff(self.data_timestamps())
                self.sample_interval_s = dtu.microseconds_to_seconds(
                    float(np.mean(timestamp_diffs))
                )
                self.sample_interval_std_s = dtu.microseconds_to_seconds(
                    float(np.std(timestamp_diffs))
                )
                self.sample_rate = (
                    np.nan
                    if self.is_sample_interval_invalid()
                    else 1 / self.sample_interval_s
                )
            else:
                self.sample_interval_s = np.nan
                self.sample_interval_std_s = np.nan
                self.sample_rate = np.nan
        return self

    def append_data(
        self, new_data: pd.DataFrame, recalculate_stats: bool = False
    ) -> "SensorData":
        """
        append the new data to the dataframe, update the sensor's stats on demand if it doesn't have a fixed
            sample rate, then return the updated SensorData object
        :param new_data: Dataframe containing data to add to the sensor's dataframe
        :param recalculate_stats: if True and the sensor does not have a fixed sample rate, sort the timestamps,
                                    recalculate the sample rate, interval, and interval std dev, default False
        :return: the updated SensorData object
        """
        self.data_df = self.data_df.append(new_data, ignore_index=True)
        if recalculate_stats and not self.is_sample_rate_fixed:
            self.organize_and_update_stats()
        return self

    def sensor_type_as_str(self) -> str:
        """
        gets the sensor type as a string
        :return: sensor type of the sensor as a string
        """
        return self.type.name

    def samples(self) -> np.ndarray:
        """
        gets the samples of dataframe
        :return: the data values of the dataframe as a numpy ndarray
        """
        return self.data_df.iloc[:, 1:].T.to_numpy()

    def get_data_channel(self, channel_name: str) -> np.array:
        """
        gets the data channel specified, raises an error and lists valid fields if channel_name is not in the dataframe
        :param channel_name: the name of the channel to get data for
        :return: the data values of the channel as a numpy array or a list of strings if the channel is enumerated
        """
        if channel_name not in self.data_df.columns:
            raise ValueError(
                f"WARNING: {channel_name} does not exist; try one of {self.data_channels()}"
            )
        return self.data_df[channel_name].to_numpy()

    def get_valid_data_channel_values(self, channel_name: str) -> np.array:
        """
        gets all non-nan values from the channel specified
        :param channel_name: the name of the channel to get data for
        :return: non-nan values of the channel as a numpy array
        """
        channel_data = self.get_data_channel(channel_name)
        return channel_data[~np.isnan(channel_data)]

    def data_timestamps(self) -> np.array:
        """
        :return: the timestamps as a numpy array
        """
        return self.data_df["timestamps"].to_numpy(dtype=np.float)

    def first_data_timestamp(self) -> float:
        """
        :return: timestamp of the first data point
        """
        return self.data_df["timestamps"].iloc[0]

    def last_data_timestamp(self) -> float:
        """
        :return: timestamp of the last data point
        """
        return self.data_df["timestamps"].iloc[-1]

    def num_samples(self) -> int:
        """
        :return: the number of rows (samples) in the dataframe
        """
        return self.data_df.shape[0]

    def data_duration_s(self) -> float:
        """
        calculate the duration in seconds of the dataframe: last - first timestamp if enough data, otherwise np.nan
        :return: duration in seconds of the dataframe
        """
        if self.num_samples() > 1:
            return dtu.microseconds_to_seconds(
                self.last_data_timestamp() - self.first_data_timestamp()
            )
        return np.nan

    def data_channels(self) -> List[str]:
        """
        :return: a list of the names of the columns (data channels) of the dataframe
        """
        return self.data_df.columns.to_list()

    def update_data_timestamps(self, time_delta: float):
        """
        adds the time_delta to the sensor's timestamps; use negative values to go backwards in time
        :param time_delta: time to add to sensor's timestamps
        """
        new_timestamps = self.data_timestamps() + time_delta
        self.data_df["timestamps"] = new_timestamps
        self.timestamps_altered = True

    def sort_by_data_timestamps(self, ascending: bool = True):
        """
        sorts the data based on timestamps
        :param ascending: if True, timestamps are sorted in ascending order
        """
        self.data_df = self.data_df.sort_values("timestamps", ascending=ascending)


def get_empty_sensor_data(
    name: str, sensor_type: SensorType = SensorType.UNKNOWN_SENSOR
) -> SensorData:
    """
    create a sensor data object with no data
    :param name: name of the sensor
    :param sensor_type: type of the sensor to create, default SensorType.UNKNOWN_SENSOR
    :return: empty sensor
    """
    return SensorData(name, pd.DataFrame([], columns=["timestamps"]), sensor_type)


def calc_evenly_sampled_timestamps(
    start: float, samples: int, rate_hz: float
) -> np.array:
    """
    given a start time, calculates samples amount of evenly spaced timestamps at rate_hz
    :param start: float, start timestamp in microseconds
    :param samples: int, number of samples
    :param rate_hz: float, sample rate in hz
    :return: np.array with evenly spaced timestamps starting at start
    """
    return start + (np.arange(0, samples) / rate_hz) * dtu.MICROSECONDS_IN_SECOND


def get_sample_statistics(data_df: pd.DataFrame) -> Tuple[float, float, float]:
    """
    calculate the sample rate, interval and interval std dev using the timestamps in the dataframe
    :param data_df: the dataframe containing timestamps to calculate statistics from
    :return: a Tuple containing the sample rate, interval and interval std dev
    """
    if data_df["timestamps"].size > 1:
        sample_interval = dtu.microseconds_to_seconds(
            float(np.mean(np.diff(data_df["timestamps"])))
        )
        sample_interval_std = dtu.microseconds_to_seconds(
            float(np.std(np.diff(data_df["timestamps"])))
        )
    else:
        sample_interval = np.nan
        sample_interval_std = np.nan
    return 1 / sample_interval, sample_interval, sample_interval_std


def read_apim_xyz_sensor(sensor: xyz.Xyz, column_id: str) -> pd.DataFrame:
    """
    read a sensor that has xyz data channels from an api M data packet
    raises Attribute Error if sensor does not contain xyz channels
    :param sensor: the xyz api M sensor to read
    :param column_id: string, used to name the columns
    :return: Dataframe representing the data in the sensor
    """
    timestamps = sensor.get_timestamps().get_timestamps()
    try:
        columns = ["timestamps", f"{column_id}_x", f"{column_id}_y", f"{column_id}_z"]
        return pd.DataFrame(
            np.transpose(
                [
                    timestamps,
                    sensor.get_x_samples().get_values(),
                    sensor.get_y_samples().get_values(),
                    sensor.get_z_samples().get_values(),
                ]
            ),
            columns=columns,
        )
    except AttributeError:
        raise


def read_apim_single_sensor(sensor: single.Single, column_id: str) -> pd.DataFrame:
    """
    read a sensor that has a single data channel from an api M data packet
    raises Attribute Error if sensor does not contain exactly one data channel
    :param sensor: the single channel api M sensor to read
    :param column_id: string, used to name the columns
    :return: Dataframe representing the data in the sensor
    """
    timestamps = sensor.get_timestamps().get_timestamps()
    try:
        columns = ["timestamps", column_id]
        return pd.DataFrame(
            np.transpose([timestamps, sensor.get_samples().get_values()]),
            columns=columns,
        )
    except AttributeError:
        raise


def load_apim_audio(wrapped_packet: WrappedRedvoxPacketM) -> Optional[SensorData]:
    """
    load audio data from a single wrapped packet
    :param wrapped_packet: packet with data to load
    :return: audio sensor data if it exists, None otherwise
    """
    audio = wrapped_packet.get_sensors().get_audio()
    if audio and wrapped_packet.get_sensors().validate_audio():
        sample_rate_hz = audio.get_sample_rate()
        data_for_df = audio.get_samples().get_values()
        timestamps = calc_evenly_sampled_timestamps(
            audio.get_first_sample_timestamp(), audio.get_num_samples(), sample_rate_hz
        )
        return SensorData(
            audio.get_sensor_description(),
            pd.DataFrame(
                np.transpose([timestamps, data_for_df]),
                columns=["timestamps", "microphone"],
            ),
            SensorType.AUDIO,
            sample_rate_hz,
            1 / sample_rate_hz,
            0.0,
            True,
        )
    return None


def load_apim_audio_from_list(
    wrapped_packets: List[WrappedRedvoxPacketM],
) -> Optional[SensorData]:
    """
    load audio data from a list of wrapped packets
    :param wrapped_packets: packets with data to load
    :return: audio sensor data if it exists, None otherwise
    """
    if len(wrapped_packets) > 0:
        result = load_apim_audio(wrapped_packets[0])
        if len(wrapped_packets) == 1:
            return result
        for wrapped_packet in wrapped_packets[1:]:
            next_result = load_apim_audio(wrapped_packet)
            if next_result:
                result.append_data(next_result.data_df)
        return result.organize_and_update_stats()
    return None


def load_apim_compressed_audio(
    wrapped_packet: WrappedRedvoxPacketM,
) -> Optional[SensorData]:
    """
    load compressed audio data from a single wrapped packet
    :param wrapped_packet: packet with data to load
    :return: compressed audio sensor data if it exists, None otherwise
    """
    comp_audio = wrapped_packet.get_sensors().get_compressed_audio()
    if comp_audio and wrapped_packet.get_sensors().validate_compressed_audio():
        sample_rate_hz = comp_audio.get_sample_rate()
        return SensorData(
            comp_audio.get_sensor_description(),
            pd.DataFrame(
                np.transpose(
                    [
                        comp_audio.get_first_sample_timestamp(),
                        comp_audio.get_audio_bytes(),
                        comp_audio.get_audio_codec(),
                    ]
                ),
                columns=["timestamps", "compressed_audio", "audio_codec"],
            ),
            SensorType.COMPRESSED_AUDIO,
            sample_rate_hz,
            1 / sample_rate_hz,
            0.0,
            True,
        )
    return None


def load_apim_compressed_audio_from_list(
    wrapped_packets: List[WrappedRedvoxPacketM],
) -> Optional[SensorData]:
    """
    load compressed audio data from a list of wrapped packets
    :param wrapped_packets: packets with data to load
    :return: compressed audio sensor data if it exists, None otherwise
    """
    if len(wrapped_packets) > 0:
        result = load_apim_compressed_audio(wrapped_packets[0])
        if len(wrapped_packets) == 1:
            return result
        for wrapped_packet in wrapped_packets[1:]:
            next_result = load_apim_compressed_audio(wrapped_packet)
            if next_result:
                result.append_data(next_result.data_df)
        return result.organize_and_update_stats()
    return None


def load_apim_image(wrapped_packet: WrappedRedvoxPacketM) -> Optional[SensorData]:
    """
    load image data from a single wrapped packet
    :param wrapped_packet: packet with data to load
    :return: image sensor data if it exists, None otherwise
    """
    image = wrapped_packet.get_sensors().get_image()
    if image and wrapped_packet.get_sensors().validate_image():
        timestamps = image.get_timestamps().get_timestamps()
        codecs = np.full(len(timestamps), image.get_image_codec().value)
        data_df = pd.DataFrame(
            np.transpose([timestamps, image.get_samples(), codecs]),
            columns=["timestamps", "image", "image_codec"],
        )
        sample_rate, sample_interval, sample_interval_std = get_sample_statistics(
            data_df
        )
        return SensorData(
            image.get_sensor_description(),
            data_df,
            SensorType.IMAGE,
            sample_rate,
            sample_interval,
            sample_interval_std,
            False,
        )
    return None


def load_apim_image_from_list(
    wrapped_packets: List[WrappedRedvoxPacketM],
) -> Optional[SensorData]:
    """
    load image data from a list of wrapped packets
    :param wrapped_packets: packets with data to load
    :return: image sensor data if it exists, None otherwise
    """
    if len(wrapped_packets) > 0:
        result = load_apim_image(wrapped_packets[0])
        if len(wrapped_packets) == 1:
            return result
        for wrapped_packet in wrapped_packets[1:]:
            next_result = load_apim_image(wrapped_packet)
            if next_result:
                result.append_data(next_result.data_df)
        return result.organize_and_update_stats()
    return None


def load_apim_location(wrapped_packet: WrappedRedvoxPacketM) -> Optional[SensorData]:
    """
    load location data from a single wrapped packet
    :param wrapped_packet: packet with data to load
    :return: location sensor data if it exists, None otherwise
    """
    loc = wrapped_packet.get_sensors().get_location()
    if loc and wrapped_packet.get_sensors().validate_location():
        if loc.is_only_best_values():
            if loc.get_last_best_location():
                best_loc = loc.get_last_best_location()
            else:
                best_loc = loc.get_overall_best_location()
            data_for_df = [
                [
                    best_loc.get_latitude_longitude_timestamp().get_mach(),
                    best_loc.get_latitude(),
                    best_loc.get_longitude(),
                    best_loc.get_altitude(),
                    best_loc.get_speed(),
                    best_loc.get_bearing(),
                    best_loc.get_horizontal_accuracy(),
                    best_loc.get_vertical_accuracy(),
                    best_loc.get_speed_accuracy(),
                    best_loc.get_bearing_accuracy(),
                    best_loc.get_location_provider(),
                ]
            ]
        else:
            timestamps = loc.get_timestamps().get_timestamps()
            data_for_df = []
            if len(timestamps) > 0:
                lat_samples = loc.get_latitude_samples().get_values()
                lon_samples = loc.get_longitude_samples().get_values()
                alt_samples = loc.get_altitude_samples().get_values()
                spd_samples = loc.get_speed_samples().get_values()
                bear_samples = loc.get_bearing_samples().get_values()
                hor_acc_samples = loc.get_horizontal_accuracy_samples().get_values()
                vert_acc_samples = loc.get_vertical_accuracy_samples().get_values()
                spd_acc_samples = loc.get_speed_accuracy_samples().get_values()
                bear_acc_samples = loc.get_bearing_accuracy_samples().get_values()
                loc_prov_samples = loc.get_location_providers().get_values()
                for i in range(len(timestamps)):
                    new_entry = [
                        timestamps[i],
                        lat_samples[i],
                        lon_samples[i],
                        np.nan if len(alt_samples) < i + 1 else alt_samples[i],
                        np.nan if len(spd_samples) < i + 1 else spd_samples[i],
                        np.nan if len(bear_samples) < i + 1 else bear_samples[i],
                        np.nan if len(hor_acc_samples) < i + 1 else hor_acc_samples[i],
                        np.nan
                        if len(vert_acc_samples) < i + 1
                        else vert_acc_samples[i],
                        np.nan if len(spd_acc_samples) < i + 1 else spd_acc_samples[i],
                        np.nan
                        if len(bear_acc_samples) < i + 1
                        else bear_acc_samples[i],
                        np.nan
                        if len(loc_prov_samples) < i + 1
                        else loc_prov_samples[i],
                    ]
                    data_for_df.append(new_entry)
        data_df = pd.DataFrame(
            data_for_df,
            columns=[
                "timestamps",
                "latitude",
                "longitude",
                "altitude",
                "speed",
                "bearing",
                "horizontal_accuracy",
                "vertical_accuracy",
                "speed_accuracy",
                "bearing_accuracy",
                "location_provider",
            ],
        )
        sample_rate, sample_interval, sample_interval_std = get_sample_statistics(
            data_df
        )
        return SensorData(
            loc.get_sensor_description(),
            data_df,
            SensorType.LOCATION,
            sample_rate,
            sample_interval,
            sample_interval_std,
            False,
        )
    return None


def load_apim_location_from_list(
    wrapped_packets: List[WrappedRedvoxPacketM],
) -> Optional[SensorData]:
    """
    load location data from a list of wrapped packets
    :param wrapped_packets: packets with data to load
    :return: location sensor data if it exists, None otherwise
    """
    if len(wrapped_packets) > 0:
        result = load_apim_location(wrapped_packets[0])
        if len(wrapped_packets) == 1:
            return result
        for wrapped_packet in wrapped_packets[1:]:
            next_result = load_apim_location(wrapped_packet)
            if next_result:
                result.append_data(next_result.data_df)
        return result.organize_and_update_stats()
    return None


def load_apim_pressure(wrapped_packet: WrappedRedvoxPacketM) -> Optional[SensorData]:
    """
    load pressure data from a single wrapped packet
    :param wrapped_packet: packet with data to load
    :return: pressure sensor data if it exists, None otherwise
    """
    pressure = wrapped_packet.get_sensors().get_pressure()
    if pressure and wrapped_packet.get_sensors().validate_pressure():
        data_df = read_apim_single_sensor(pressure, "pressure")
        sample_rate, sample_interval, sample_interval_std = get_sample_statistics(
            data_df
        )
        return SensorData(
            pressure.get_sensor_description(),
            data_df,
            SensorType.PRESSURE,
            sample_rate,
            sample_interval,
            sample_interval_std,
            False,
        )


def load_apim_pressure_from_list(
    wrapped_packets: List[WrappedRedvoxPacketM],
) -> Optional[SensorData]:
    """
    load pressure data from a list of wrapped packets
    :param wrapped_packets: packets with data to load
    :return: pressure sensor data if it exists, None otherwise
    """
    if len(wrapped_packets) > 0:
        result = load_apim_pressure(wrapped_packets[0])
        if len(wrapped_packets) == 1:
            return result
        for wrapped_packet in wrapped_packets[1:]:
            next_result = load_apim_pressure(wrapped_packet)
            if next_result:
                result.append_data(next_result.data_df)
        return result.organize_and_update_stats()
    return None


def load_apim_light(wrapped_packet: WrappedRedvoxPacketM) -> Optional[SensorData]:
    """
    load light data from a single wrapped packet
    :param wrapped_packet: packet with data to load
    :return: light sensor data if it exists, None otherwise
    """
    light = wrapped_packet.get_sensors().get_light()
    if light and wrapped_packet.get_sensors().validate_light():
        data_df = read_apim_single_sensor(light, "light")
        sample_rate, sample_interval, sample_interval_std = get_sample_statistics(
            data_df
        )
        return SensorData(
            light.get_sensor_description(),
            data_df,
            SensorType.LIGHT,
            sample_rate,
            sample_interval,
            sample_interval_std,
            False,
        )


def load_apim_light_from_list(
    wrapped_packets: List[WrappedRedvoxPacketM],
) -> Optional[SensorData]:
    """
    load light data from a list of wrapped packets
    :param wrapped_packets: packets with data to load
    :return: light sensor data if it exists, None otherwise
    """
    if len(wrapped_packets) > 0:
        result = load_apim_light(wrapped_packets[0])
        if len(wrapped_packets) == 1:
            return result
        for wrapped_packet in wrapped_packets[1:]:
            next_result = load_apim_light(wrapped_packet)
            if next_result:
                result.append_data(next_result.data_df)
        return result.organize_and_update_stats()
    return None


def load_apim_proximity(wrapped_packet: WrappedRedvoxPacketM) -> Optional[SensorData]:
    """
    load proximity data from a single wrapped packet
    :param wrapped_packet: packet with data to load
    :return: proximity sensor data if it exists, None otherwise
    """
    proximity = wrapped_packet.get_sensors().get_proximity()
    if proximity and wrapped_packet.get_sensors().validate_proximity():
        data_df = read_apim_single_sensor(proximity, "proximity")
        sample_rate, sample_interval, sample_interval_std = get_sample_statistics(
            data_df
        )
        return SensorData(
            proximity.get_sensor_description(),
            data_df,
            SensorType.PROXIMITY,
            sample_rate,
            sample_interval,
            sample_interval_std,
            False,
        )


def load_apim_proximity_from_list(
    wrapped_packets: List[WrappedRedvoxPacketM],
) -> Optional[SensorData]:
    """
    load proximity data from a list of wrapped packets
    :param wrapped_packets: packets with data to load
    :return: proximity sensor data if it exists, None otherwise
    """
    if len(wrapped_packets) > 0:
        result = load_apim_proximity(wrapped_packets[0])
        if len(wrapped_packets) == 1:
            return result
        for wrapped_packet in wrapped_packets[1:]:
            next_result = load_apim_proximity(wrapped_packet)
            if next_result:
                result.append_data(next_result.data_df)
        return result.organize_and_update_stats()
    return None


def load_apim_ambient_temp(
    wrapped_packet: WrappedRedvoxPacketM,
) -> Optional[SensorData]:
    """
    load ambient temperature data from a single wrapped packet
    :param wrapped_packet: packet with data to load
    :return: ambient temperature sensor data if it exists, None otherwise
    """
    ambient_temp = wrapped_packet.get_sensors().get_ambient_temperature()
    if ambient_temp and wrapped_packet.get_sensors().validate_ambient_temperature():
        data_df = read_apim_single_sensor(ambient_temp, "ambient_temp")
        sample_rate, sample_interval, sample_interval_std = get_sample_statistics(
            data_df
        )
        return SensorData(
            ambient_temp.get_sensor_description(),
            data_df,
            SensorType.AMBIENT_TEMPERATURE,
            sample_rate,
            sample_interval,
            sample_interval_std,
            False,
        )


def load_apim_ambient_temp_from_list(
    wrapped_packets: List[WrappedRedvoxPacketM],
) -> Optional[SensorData]:
    """
    load ambient temperature data from a list of wrapped packets
    :param wrapped_packets: packets with data to load
    :return: ambient temperature sensor data if it exists, None otherwise
    """
    if len(wrapped_packets) > 0:
        result = load_apim_ambient_temp(wrapped_packets[0])
        if len(wrapped_packets) == 1:
            return result
        for wrapped_packet in wrapped_packets[1:]:
            next_result = load_apim_ambient_temp(wrapped_packet)
            if next_result:
                result.append_data(next_result.data_df)
        return result.organize_and_update_stats()
    return None


def load_apim_rel_humidity(
    wrapped_packet: WrappedRedvoxPacketM,
) -> Optional[SensorData]:
    """
    load relative humidity data from a single wrapped packet
    :param wrapped_packet: packet with data to load
    :return: relative humidity sensor data if it exists, None otherwise
    """
    rel_humidity = wrapped_packet.get_sensors().get_relative_humidity()
    if rel_humidity and wrapped_packet.get_sensors().validate_relative_humidity():
        data_df = read_apim_single_sensor(rel_humidity, "rel_humidity")
        sample_rate, sample_interval, sample_interval_std = get_sample_statistics(
            data_df
        )
        return SensorData(
            rel_humidity.get_sensor_description(),
            data_df,
            SensorType.RELATIVE_HUMIDITY,
            sample_rate,
            sample_interval,
            sample_interval_std,
            False,
        )


def load_apim_rel_humidity_from_list(
    wrapped_packets: List[WrappedRedvoxPacketM],
) -> Optional[SensorData]:
    """
    load relative humidity data from a list of wrapped packets
    :param wrapped_packets: packets with data to load
    :return: relative humidity sensor data if it exists, None otherwise
    """
    if len(wrapped_packets) > 0:
        result = load_apim_rel_humidity(wrapped_packets[0])
        if len(wrapped_packets) == 1:
            return result
        for wrapped_packet in wrapped_packets[1:]:
            next_result = load_apim_rel_humidity(wrapped_packet)
            if next_result:
                result.append_data(next_result.data_df)
        return result.organize_and_update_stats()
    return None


def load_apim_accelerometer(
    wrapped_packet: WrappedRedvoxPacketM,
) -> Optional[SensorData]:
    """
    load accelerometer data from a single wrapped packet
    :param wrapped_packet: packet with data to load
    :return: accelerometer sensor data if it exists, None otherwise
    """
    accel = wrapped_packet.get_sensors().get_accelerometer()
    if accel and wrapped_packet.get_sensors().validate_accelerometer():
        data_df = read_apim_xyz_sensor(accel, "accelerometer")
        sample_rate, sample_interval, sample_interval_std = get_sample_statistics(
            data_df
        )
        return SensorData(
            accel.get_sensor_description(),
            data_df,
            SensorType.ACCELEROMETER,
            sample_rate,
            sample_interval,
            sample_interval_std,
            False,
        )


def load_apim_accelerometer_from_list(
    wrapped_packets: List[WrappedRedvoxPacketM],
) -> Optional[SensorData]:
    """
    load accelerometer data from a list of wrapped packets
    :param wrapped_packets: packets with data to load
    :return: accelerometer sensor data if it exists, None otherwise
    """
    if len(wrapped_packets) > 0:
        result = load_apim_accelerometer(wrapped_packets[0])
        if len(wrapped_packets) == 1:
            return result
        for wrapped_packet in wrapped_packets[1:]:
            next_result = load_apim_accelerometer(wrapped_packet)
            if next_result:
                result.append_data(next_result.data_df)
        return result.organize_and_update_stats()
    return None


def load_apim_magnetometer(
    wrapped_packet: WrappedRedvoxPacketM,
) -> Optional[SensorData]:
    """
    load magnetometer data from a single wrapped packet
    :param wrapped_packet: packet with data to load
    :return: magnetometer sensor data if it exists, None otherwise
    """
    mag = wrapped_packet.get_sensors().get_magnetometer()
    if mag and wrapped_packet.get_sensors().validate_magnetometer():
        data_df = read_apim_xyz_sensor(mag, "magnetometer")
        sample_rate, sample_interval, sample_interval_std = get_sample_statistics(
            data_df
        )
        return SensorData(
            mag.get_sensor_description(),
            data_df,
            SensorType.MAGNETOMETER,
            sample_rate,
            sample_interval,
            sample_interval_std,
            False,
        )


def load_apim_magnetometer_from_list(
    wrapped_packets: List[WrappedRedvoxPacketM],
) -> Optional[SensorData]:
    """
    load magnetometer data from a list of wrapped packets
    :param wrapped_packets: packets with data to load
    :return: magnetometer sensor data if it exists, None otherwise
    """
    if len(wrapped_packets) > 0:
        result = load_apim_magnetometer(wrapped_packets[0])
        if len(wrapped_packets) == 1:
            return result
        for wrapped_packet in wrapped_packets[1:]:
            next_result = load_apim_magnetometer(wrapped_packet)
            if next_result:
                result.append_data(next_result.data_df)
        return result.organize_and_update_stats()
    return None


def load_apim_gyroscope(wrapped_packet: WrappedRedvoxPacketM) -> Optional[SensorData]:
    """
    load gyroscope data from a single wrapped packet
    :param wrapped_packet: packet with data to load
    :return: gyroscope sensor data if it exists, None otherwise
    """
    gyro = wrapped_packet.get_sensors().get_gyroscope()
    if gyro and wrapped_packet.get_sensors().validate_gyroscope():
        data_df = read_apim_xyz_sensor(gyro, "gyroscope")
        sample_rate, sample_interval, sample_interval_std = get_sample_statistics(
            data_df
        )
        return SensorData(
            gyro.get_sensor_description(),
            data_df,
            SensorType.GYROSCOPE,
            sample_rate,
            sample_interval,
            sample_interval_std,
            False,
        )


def load_apim_gyroscope_from_list(
    wrapped_packets: List[WrappedRedvoxPacketM],
) -> Optional[SensorData]:
    """
    load gyroscope data from a list of wrapped packets
    :param wrapped_packets: packets with data to load
    :return: gyroscope sensor data if it exists, None otherwise
    """
    if len(wrapped_packets) > 0:
        result = load_apim_gyroscope(wrapped_packets[0])
        if len(wrapped_packets) == 1:
            return result
        for wrapped_packet in wrapped_packets[1:]:
            next_result = load_apim_gyroscope(wrapped_packet)
            if next_result:
                result.append_data(next_result.data_df)
        return result.organize_and_update_stats()
    return None


def load_apim_gravity(wrapped_packet: WrappedRedvoxPacketM) -> Optional[SensorData]:
    """
    load gravity data from a single wrapped packet
    :param wrapped_packet: packet with data to load
    :return: gravity sensor data if it exists, None otherwise
    """
    gravity = wrapped_packet.get_sensors().get_gravity()
    if gravity and wrapped_packet.get_sensors().validate_gravity():
        data_df = read_apim_xyz_sensor(gravity, "gravity")
        sample_rate, sample_interval, sample_interval_std = get_sample_statistics(
            data_df
        )
        return SensorData(
            gravity.get_sensor_description(),
            data_df,
            SensorType.GRAVITY,
            sample_rate,
            sample_interval,
            sample_interval_std,
            False,
        )


def load_apim_gravity_from_list(
    wrapped_packets: List[WrappedRedvoxPacketM],
) -> Optional[SensorData]:
    """
    load gravity data from a list of wrapped packets
    :param wrapped_packets: packets with data to load
    :return: gravity sensor data if it exists, None otherwise
    """
    if len(wrapped_packets) > 0:
        result = load_apim_gravity(wrapped_packets[0])
        if len(wrapped_packets) == 1:
            return result
        for wrapped_packet in wrapped_packets[1:]:
            next_result = load_apim_gravity(wrapped_packet)
            if next_result:
                result.append_data(next_result.data_df)
        return result.organize_and_update_stats()
    return None


def load_apim_orientation(wrapped_packet: WrappedRedvoxPacketM) -> Optional[SensorData]:
    """
    load orientation data from a single wrapped packet
    :param wrapped_packet: packet with data to load
    :return: orientation sensor data if it exists, None otherwise
    """
    orientation = wrapped_packet.get_sensors().get_orientation()
    if orientation and wrapped_packet.get_sensors().validate_orientation():
        data_df = read_apim_xyz_sensor(orientation, "orientation")
        sample_rate, sample_interval, sample_interval_std = get_sample_statistics(
            data_df
        )
        return SensorData(
            orientation.get_sensor_description(),
            data_df,
            SensorType.ORIENTATION,
            sample_rate,
            sample_interval,
            sample_interval_std,
            False,
        )


def load_apim_orientation_from_list(
    wrapped_packets: List[WrappedRedvoxPacketM],
) -> Optional[SensorData]:
    """
    load orientation data from a list of wrapped packets
    :param wrapped_packets: packets with data to load
    :return: orientation sensor data if it exists, None otherwise
    """
    if len(wrapped_packets) > 0:
        result = load_apim_orientation(wrapped_packets[0])
        if len(wrapped_packets) == 1:
            return result
        for wrapped_packet in wrapped_packets[1:]:
            next_result = load_apim_orientation(wrapped_packet)
            if next_result:
                result.append_data(next_result.data_df)
        return result.organize_and_update_stats()
    return None


def load_apim_linear_accel(
    wrapped_packet: WrappedRedvoxPacketM,
) -> Optional[SensorData]:
    """
    load linear acceleration data from a single wrapped packet
    :param wrapped_packet: packet with data to load
    :return: linear acceleration sensor data if it exists, None otherwise
    """
    linear_accel = wrapped_packet.get_sensors().get_linear_acceleration()
    if linear_accel and wrapped_packet.get_sensors().validate_linear_acceleration():
        data_df = read_apim_xyz_sensor(linear_accel, "linear_accel")
        sample_rate, sample_interval, sample_interval_std = get_sample_statistics(
            data_df
        )
        return SensorData(
            linear_accel.get_sensor_description(),
            data_df,
            SensorType.LINEAR_ACCELERATION,
            sample_rate,
            sample_interval,
            sample_interval_std,
            False,
        )


def load_apim_linear_accel_from_list(
    wrapped_packets: List[WrappedRedvoxPacketM],
) -> Optional[SensorData]:
    """
    load linear acceleration data from a list of wrapped packets
    :param wrapped_packets: packets with data to load
    :return: linear acceleration sensor data if it exists, None otherwise
    """
    if len(wrapped_packets) > 0:
        result = load_apim_linear_accel(wrapped_packets[0])
        if len(wrapped_packets) == 1:
            return result
        for wrapped_packet in wrapped_packets[1:]:
            next_result = load_apim_linear_accel(wrapped_packet)
            if next_result:
                result.append_data(next_result.data_df)
        return result.organize_and_update_stats()
    return None


def load_apim_rotation_vector(
    wrapped_packet: WrappedRedvoxPacketM,
) -> Optional[SensorData]:
    """
    load rotation vector data from a single wrapped packet
    :param wrapped_packet: packet with data to load
    :return: rotation vector sensor data if it exists, None otherwise
    """
    rotation = wrapped_packet.get_sensors().get_rotation_vector()
    if rotation and wrapped_packet.get_sensors().validate_rotation_vector():
        data_df = read_apim_xyz_sensor(rotation, "rotation_vector")
        sample_rate, sample_interval, sample_interval_std = get_sample_statistics(
            data_df
        )
        return SensorData(
            rotation.get_sensor_description(),
            data_df,
            SensorType.ROTATION_VECTOR,
            sample_rate,
            sample_interval,
            sample_interval_std,
            False,
        )


def load_apim_rotation_vector_from_list(
    wrapped_packets: List[WrappedRedvoxPacketM],
) -> Optional[SensorData]:
    """
    load rotation vector data from a list of wrapped packets
    :param wrapped_packets: packets with data to load
    :return: rotation vector sensor data if it exists, None otherwise
    """
    if len(wrapped_packets) > 0:
        result = load_apim_rotation_vector(wrapped_packets[0])
        if len(wrapped_packets) == 1:
            return result
        for wrapped_packet in wrapped_packets[1:]:
            next_result = load_apim_rotation_vector(wrapped_packet)
            if next_result:
                result.append_data(next_result.data_df)
        return result.organize_and_update_stats()
    return None


def load_apim_health(wrapped_packet: WrappedRedvoxPacketM) -> Optional[SensorData]:
    """
    load station health data from a single wrapped packet
    :param wrapped_packet: packet with data to load
    :return: station health data if it exists, None otherwise
    """
    metrics = wrapped_packet.get_station_information().get_station_metrics()
    timestamps = metrics.get_timestamps().get_timestamps()
    data_for_df = []
    if len(timestamps) > 0:
        bat_samples = metrics.get_battery().get_values()
        bat_cur_samples = metrics.get_battery_current().get_values()
        temp_samples = metrics.get_temperature().get_values()
        net_samples = metrics.get_network_type().get_values()
        net_str_samples = metrics.get_network_strength().get_values()
        pow_samples = metrics.get_power_state().get_values()
        avail_ram_samples = metrics.get_available_ram().get_values()
        avail_disk_samples = metrics.get_available_disk().get_values()
        cell_samples = metrics.get_cell_service_state().get_values()
        for i in range(len(timestamps)):
            new_entry = [
                timestamps[i],
                np.nan if len(bat_samples) < i + 1 else bat_samples[i],
                np.nan if len(bat_cur_samples) < i + 1 else bat_cur_samples[i],
                np.nan if len(temp_samples) < i + 1 else temp_samples[i],
                np.nan if len(net_samples) < i + 1 else net_samples[i],
                np.nan if len(net_str_samples) < i + 1 else net_str_samples[i],
                np.nan if len(pow_samples) < i + 1 else pow_samples[i],
                np.nan if len(avail_ram_samples) < i + 1 else avail_ram_samples[i],
                np.nan if len(avail_disk_samples) < i + 1 else avail_disk_samples[i],
                np.nan if len(cell_samples) < i + 1 else cell_samples[i],
            ]
            data_for_df.append(new_entry)
    if len(data_for_df) > 0:
        data_df = pd.DataFrame(
            data_for_df,
            columns=[
                "timestamps",
                "battery_charge_remaining",
                "battery_current_strength",
                "internal_temp_c",
                "network_type",
                "network_strength",
                "power_state",
                "avail_ram",
                "avail_disk",
                "cell_service",
            ],
        )
        sample_rate, sample_interval, sample_interval_std = get_sample_statistics(
            data_df
        )
        return SensorData(
            "station health",
            data_df,
            SensorType.STATION_HEALTH,
            sample_rate,
            sample_interval,
            sample_interval_std,
            False,
        )
    return None


def load_apim_health_from_list(
    wrapped_packets: List[WrappedRedvoxPacketM],
) -> Optional[SensorData]:
    """
    load station health data from a list of wrapped packets
    :param wrapped_packets: packets with data to load
    :return: station health sensor data if it exists, None otherwise
    """
    if len(wrapped_packets) > 0:
        result = load_apim_health(wrapped_packets[0])
        if len(wrapped_packets) == 1:
            return result
        for wrapped_packet in wrapped_packets[1:]:
            next_result = load_apim_health(wrapped_packet)
            if next_result:
                result.append_data(next_result.data_df)
        return result.organize_and_update_stats()
    return None
