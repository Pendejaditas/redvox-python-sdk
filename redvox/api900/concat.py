"""
This module contains functions for concatenating multiple WrappedRedvoxPackets together.
"""

import itertools
import typing

import redvox.api900.date_time_utils as _date_time_utils
import redvox.api900.exceptions as _exceptions
import redvox.api900.reader as _reader
import redvox.api900.sensors.evenly_sampled_sensor as evenly_sampled_sensor
import redvox.api900.sensors.time_synchronization_sensor as time_synchronization_sensor
import redvox.api900.sensors.unevenly_sampled_sensor as unevenly_sampled_sensor

import redvox.api900.sensors.microphone_sensor as microphone_sensor
import redvox.api900.sensors.barometer_sensor as barometer_sensor
import redvox.api900.sensors.location_sensor as location_sensor
import redvox.api900.sensors.gyroscope_sensor as gyroscope_sensor
import redvox.api900.sensors.magnetometer_sensor as magnetometer_sensor
import redvox.api900.sensors.accelerometer_sensor as accelerometer_sensor
import redvox.api900.sensors.light_sensor as light_sensor
import redvox.api900.sensors.infrared_sensor as infrared_sensor
import redvox.api900.sensors.image_sensor as image_sensor
from redvox.api900.wrapped_redvox_packet import WrappedRedvoxPacket

RedvoxSensor = typing.Union[
    evenly_sampled_sensor.EvenlySampledSensor,
    unevenly_sampled_sensor.UnevenlySampledSensor,
    microphone_sensor.MicrophoneSensor,
    barometer_sensor.BarometerSensor,
    location_sensor.LocationSensor,
    time_synchronization_sensor.TimeSynchronizationSensor,
    accelerometer_sensor.AccelerometerSensor,
    gyroscope_sensor.GyroscopeSensor,
    magnetometer_sensor.MagnetometerSensor,
    light_sensor.LightSensor,
    infrared_sensor.InfraredSensor,
    image_sensor.ImageSensor
]
RedvoxSensors = typing.List[RedvoxSensor]

import numpy as _np

_NONE_HASH = hash(None)


def _partial_hash_sensor(sensor: typing.Optional[RedvoxSensor]) -> int:
    """
    Performs a partial hash on a sensor hashing the sensor name, sample rate, and payload type.
    :param sensor: The sensor to hash.
    :return: Hash of the sensor.
    """
    if sensor is None:
        return _NONE_HASH

    if isinstance(sensor, unevenly_sampled_sensor.UnevenlySampledSensor):
        return hash((sensor.sensor_name(), sensor.payload_type()))

    if isinstance(sensor, evenly_sampled_sensor.EvenlySampledSensor):
        return hash((sensor.sample_rate_hz(), sensor.sensor_name(), sensor.payload_type()))

    if isinstance(sensor, time_synchronization_sensor.TimeSynchronizationSensor):
        return hash("TimeSynchronizationSensor")

    raise _exceptions.ConcatenationException("trying to hash non-sensor type=%s" % type(sensor))


def _partial_hash_packet(wrapped_redvox_packet) -> int:
    """
    Computes the partial hash of a wrapped redvox packet.

    The hash is computed by hashing all of the partial hashes of the sensor channels.
    :param wrapped_redvox_packet: Packet to hash.
    :return: The has of this packet.
    """
    if wrapped_redvox_packet is None:
        return _NONE_HASH

    return hash((wrapped_redvox_packet.redvox_id(),
                 wrapped_redvox_packet.uuid(),
                 _partial_hash_sensor(wrapped_redvox_packet.microphone_sensor()),
                 _partial_hash_sensor(wrapped_redvox_packet.barometer_sensor()),
                 _partial_hash_sensor(wrapped_redvox_packet.location_sensor()),
                 _partial_hash_sensor(wrapped_redvox_packet.time_synchronization_sensor()),
                 _partial_hash_sensor(wrapped_redvox_packet.accelerometer_sensor()),
                 _partial_hash_sensor(wrapped_redvox_packet.gyroscope_sensor()),
                 _partial_hash_sensor(wrapped_redvox_packet.magnetometer_sensor()),
                 _partial_hash_sensor(wrapped_redvox_packet.light_sensor()),
                 _partial_hash_sensor(wrapped_redvox_packet.infrared_sensor())))


def _packet_len_s(wrapped_redvox_packet) -> float:
    """
    Returns the length of a packet in seconds.
    :param wrapped_redvox_packet: Packet to find the length of.
    :return: The length of a packet in seconds.
    """
    microphone_sensor = wrapped_redvox_packet.microphone_sensor()
    return len(microphone_sensor.payload_values()) / microphone_sensor.sample_rate_hz()


def _identify_gaps(wrapped_redvox_packets,
                   allowed_timing_error_s: float) -> typing.List[int]:
    """
    Identifies gaps in redvox packets by first comparing hashes which identifies sensor changes and then looking at
    timing gas.
    :param wrapped_redvox_packets: Packets to look for gaps in.
    :param allowed_timing_error_s: The amount of timing error in seconds.
    :return: A list of indices into the original list where gaps were found.
    """

    if len(wrapped_redvox_packets) <= 1:
        return []

    gaps = set()

    truth_hash = _partial_hash_packet(wrapped_redvox_packets[0])
    truth_len = _packet_len_s(wrapped_redvox_packets[0])
    for i in range(1, len(wrapped_redvox_packets)):
        prev_packet = wrapped_redvox_packets[i - 1]
        next_packet = wrapped_redvox_packets[i]

        # Sensor changes
        candidate_hash = _partial_hash_packet(next_packet)
        if truth_hash != candidate_hash:
            gaps.add(i)
            truth_hash = candidate_hash

        # Time based gap

        prev_timestamp = prev_packet.microphone_sensor().first_sample_timestamp_epoch_microseconds_utc()
        next_timestamp = next_packet.microphone_sensor().first_sample_timestamp_epoch_microseconds_utc()
        if _date_time_utils.microseconds_to_seconds(next_timestamp - prev_timestamp) > (
                truth_len + allowed_timing_error_s):
            gaps.add(i)
            truth_len = _packet_len_s(wrapped_redvox_packets[i])

    return sorted(list(gaps))


def _concat_numpy(sensors: RedvoxSensors,
                  array_extraction_fn: typing.Callable[[RedvoxSensor], _np.ndarray]) -> _np.ndarray:
    """
    Given a list of sensors concatenate the numpy arrays found with the extraction function.
    :param sensors: Sensors to extract arrays from.
    :param array_extraction_fn: A function that takes a sensor and returns a numpy array.
    :return: An array of concatenated arrays.
    """
    return _np.concatenate(list(map(array_extraction_fn, sensors)))


def _concat_lists(sensors: RedvoxSensors,
                  list_extraction_fn: typing.Callable[[RedvoxSensor], typing.List[str]]) -> typing.List[
    str]:
    """
    Given a list of sensors concatenate the lists found with the extraction function.
    :param sensors: Sensors to extract lists from.
    :param list_extraction_fn: A function that takes a sensor and returns a list.
    :return: A list of concatenated arrays.
    """
    metadata_list = list(map(list_extraction_fn, sensors))
    return list(itertools.chain(*metadata_list))


def _concat_continuous_data(wrapped_redvox_packets: typing.List[WrappedRedvoxPacket]) -> WrappedRedvoxPacket:
    """
    Given a set of continuous wrapped redvox packets, concatenate the packets together by concatting the timestamps,
    payload values, and metadata.
    :param wrapped_redvox_packets: Packets to concatenate.
    :return: A single WrappedRedvoxPacket with concatenated data.
    """
    first_packet = wrapped_redvox_packets[0]

    # Concat channels
    if first_packet.has_microphone_sensor():
        sensors = list(map(_reader.WrappedRedvoxPacket.microphone_sensor, wrapped_redvox_packets))
        sensors[0].set_payload_values(_concat_numpy(sensors, _reader.MicrophoneSensor.payload_values)) \
            .set_metadata(_concat_lists(sensors, _reader.MicrophoneSensor.metadata))

    if first_packet.has_barometer_sensor():
        sensors = list(map(_reader.WrappedRedvoxPacket.barometer_sensor, wrapped_redvox_packets))
        sensors[0].set_payload_values(_concat_numpy(sensors, _reader.BarometerSensor.payload_values)) \
            .set_timestamps_microseconds_utc(
                _concat_numpy(sensors, _reader.BarometerSensor.timestamps_microseconds_utc)) \
            .set_metadata(_concat_lists(sensors, _reader.BarometerSensor.metadata))

    if first_packet.has_location_sensor():
        sensors = list(map(_reader.WrappedRedvoxPacket.location_sensor, wrapped_redvox_packets))
        sensors[0].set_payload_values(
                _concat_numpy(sensors, _reader.LocationSensor.payload_values_latitude),
                _concat_numpy(sensors, _reader.LocationSensor.payload_values_longitude),
                _concat_numpy(sensors, _reader.LocationSensor.payload_values_altitude),
                _concat_numpy(sensors, _reader.LocationSensor.payload_values_speed),
                _concat_numpy(sensors, _reader.LocationSensor.payload_values_accuracy)
        ) \
            .set_timestamps_microseconds_utc(
                _concat_numpy(sensors, _reader.LocationSensor.timestamps_microseconds_utc)) \
            .set_metadata(_concat_lists(sensors, _reader.LocationSensor.metadata))

    if first_packet.has_time_synchronization_sensor():
        sensors = list(map(_reader.WrappedRedvoxPacket.time_synchronization_sensor, wrapped_redvox_packets))
        sensors[0].set_payload_values(_concat_numpy(sensors, _reader.TimeSynchronizationSensor.payload_values)) \
            .set_metadata(_concat_lists(sensors, _reader.TimeSynchronizationSensor.metadata))

    if first_packet.has_magnetometer_sensor():
        sensors = list(map(_reader.WrappedRedvoxPacket.magnetometer_sensor, wrapped_redvox_packets))
        sensors[0].set_payload_values(
                _concat_numpy(sensors, _reader.MagnetometerSensor.payload_values_x),
                _concat_numpy(sensors, _reader.MagnetometerSensor.payload_values_y),
                _concat_numpy(sensors, _reader.MagnetometerSensor.payload_values_z)
        ) \
            .set_timestamps_microseconds_utc(
                _concat_numpy(sensors, _reader.MagnetometerSensor.timestamps_microseconds_utc)) \
            .set_metadata(_concat_lists(sensors, _reader.MagnetometerSensor.metadata))

    if first_packet.has_accelerometer_sensor():
        sensors = list(map(_reader.WrappedRedvoxPacket.accelerometer_sensor, wrapped_redvox_packets))
        sensors[0].set_payload_values(
                _concat_numpy(sensors, _reader.AccelerometerSensor.payload_values_x),
                _concat_numpy(sensors, _reader.AccelerometerSensor.payload_values_y),
                _concat_numpy(sensors, _reader.AccelerometerSensor.payload_values_z)
        ) \
            .set_timestamps_microseconds_utc(
                _concat_numpy(sensors, _reader.AccelerometerSensor.timestamps_microseconds_utc)) \
            .set_metadata(_concat_lists(sensors, _reader.AccelerometerSensor.metadata))

    if first_packet.has_gyroscope_sensor():
        sensors = list(map(_reader.WrappedRedvoxPacket.gyroscope_sensor, wrapped_redvox_packets))
        sensors[0].set_payload_values(
                _concat_numpy(sensors, _reader.GyroscopeSensor.payload_values_x),
                _concat_numpy(sensors, _reader.GyroscopeSensor.payload_values_y),
                _concat_numpy(sensors, _reader.GyroscopeSensor.payload_values_z)
        ) \
            .set_timestamps_microseconds_utc(
                _concat_numpy(sensors, _reader.GyroscopeSensor.timestamps_microseconds_utc)) \
            .set_metadata(_concat_lists(sensors, _reader.GyroscopeSensor.metadata))

    if first_packet.has_light_sensor():
        sensors = list(map(_reader.WrappedRedvoxPacket.light_sensor, wrapped_redvox_packets))
        sensors[0].set_payload_values(_concat_numpy(sensors, _reader.LightSensor.payload_values)) \
            .set_timestamps_microseconds_utc(
                _concat_numpy(sensors, _reader.LightSensor.timestamps_microseconds_utc)) \
            .set_metadata(_concat_lists(sensors, _reader.LightSensor.metadata))

    if first_packet.has_infrared_sensor():
        sensors = list(map(_reader.WrappedRedvoxPacket.infrared_sensor, wrapped_redvox_packets))
        sensors[0].set_payload_values(_concat_numpy(sensors, _reader.InfraredSensor.payload_values)) \
            .set_timestamps_microseconds_utc(
                _concat_numpy(sensors, _reader.InfraredSensor.timestamps_microseconds_utc)) \
            .set_metadata(_concat_lists(sensors, _reader.InfraredSensor.metadata))

    # Concat metadata
    all_metadata = list(map(_reader.WrappedRedvoxPacket.metadata, wrapped_redvox_packets))
    first_packet.set_metadata(list(itertools.chain(*all_metadata)))

    return first_packet


def concat_wrapped_redvox_packets(wrapped_redvox_packets: typing.List[WrappedRedvoxPacket]) -> typing.List[WrappedRedvoxPacket]:
    """
    Concatenates multiple WrappedRedvoxPackets together by combining sensor timestamps, values, and metadata.
    :param wrapped_redvox_packets: Packets to concatenate.
    :return: A list of concatenated WrappedRedvoxPackets. A list is returned because each packet represents a single
             continuous range of data.
    """
    if wrapped_redvox_packets is None or len(wrapped_redvox_packets) == 0:
        return []

    if len(wrapped_redvox_packets) == 1:
        return wrapped_redvox_packets

    # Check that packets are from same device
    device_ids = set(map(lambda packet: packet.redvox_id(), wrapped_redvox_packets))
    if len(device_ids) != 1:
        raise _exceptions.ConcatenationException("Not all packets from same device %s" % str(device_ids))

    # Check that packets are ordered
    machine_times = list(map(lambda packet: packet.app_file_start_timestamp_machine(),
                             wrapped_redvox_packets))

    if not _np.all(_np.diff(_np.array(machine_times)) > 0):
        raise _exceptions.ConcatenationException("Packets are not strictly monotonic")

    # Identify gaps
    gaps = _identify_gaps(wrapped_redvox_packets, 5)

    # Concat
    concatenated_packets = []
    start = 0
    end = len(wrapped_redvox_packets)

    for gap_idx in gaps:
        concatenated_packets.append(_concat_continuous_data(wrapped_redvox_packets[start:gap_idx]))
        start = gap_idx

    concatenated_packets.append(_concat_continuous_data(wrapped_redvox_packets[start:end]))

    return concatenated_packets
