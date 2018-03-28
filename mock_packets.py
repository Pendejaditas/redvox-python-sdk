import api900.api900_pb2

import numpy

import typing


def set_payload(redvox_channel: typing.Union[api900.api900_pb2.EvenlySampledChannel,
                                             api900.api900_pb2.UnevenlySampledChannel],
                payload_type: typing.Type,
                payload: typing.List) -> typing.Union[api900.api900_pb2.EvenlySampledChannel,
                                                      api900.api900_pb2.UnevenlySampledChannel]:
    if payload_type == numpy.byte:
        redvox_channel.byte_payload.payload.extend(payload)
    elif payload_type == numpy.uint32:
        redvox_channel.uint32_payload.payload.extend(payload)
    elif payload_type == numpy.uint64:
        redvox_channel.uint64_payload.payload.extend(payload)
    elif payload_type == numpy.int32:
        redvox_channel.int32_payload.payload.extend(payload)
    elif payload_type == numpy.int64:
        redvox_channel.int64_payload.payload.extend(payload)
    elif payload_type == numpy.float32:
        redvox_channel.float32_payload.payload.extend(payload)
    elif payload_type == numpy.float64:
        redvox_channel.float64_payload.payload.extend(payload)
    else:
        return redvox_channel

    return redvox_channel


def base_packet() -> api900.api900_pb2.RedvoxPacket:
    base_packet = api900.api900_pb2.RedvoxPacket()

    base_packet.api = 900
    base_packet.redvox_id = "1"
    base_packet.uuid = "2"
    base_packet.authenticated_email = ""
    base_packet.authentication_token = ""
    base_packet.is_backfilled = False
    base_packet.is_scrambled = False
    base_packet.device_make = "test device make"
    base_packet.device_model = "test device model"
    base_packet.device_os = "test device os"
    base_packet.device_os_version = "test device os version"
    base_packet.app_version = "test app version"
    base_packet.acquisition_server = "test acquisition server"
    base_packet.time_synchronization_server = "test time synchronization server"
    base_packet.authentication_server = "test authentication server"
    base_packet.app_file_start_timestamp_epoch_microseconds_utc = 1519166348000000
    base_packet.server_timestamp_epoch_microseconds_utc = 1519166348000000 + 10000

    return base_packet


def with_evenly_sampled_channel(redvox_packet: api900.api900_pb2.RedvoxPacket,
                                channel_types: typing.List[int],
                                sensor_name: str,
                                sample_rate_hz: float,
                                first_sample_timestamp_epoch_microseconds_utc: int,
                                payload: typing.List[int],
                                value_means: typing.List[float],
                                value_stds: typing.List[float],
                                value_medians: typing.List[float],
                                metadata: typing.List[str]) -> api900.api900_pb2.RedvoxPacket:
    evenly_sampled_channel = api900.api900_pb2.EvenlySampledChannel()
    evenly_sampled_channel.channel_types.extend(channel_types)
    evenly_sampled_channel.sensor_name = sensor_name
    evenly_sampled_channel.sample_rate_hz = sample_rate_hz
    evenly_sampled_channel.first_sample_timestamp_epoch_microseconds_utc = first_sample_timestamp_epoch_microseconds_utc
    evenly_sampled_channel.int32_payload.payload.extend(payload)
    evenly_sampled_channel.value_means.extend(value_means)
    evenly_sampled_channel.value_stds.extend(value_stds)
    evenly_sampled_channel.value_medians.extend(value_medians)
    evenly_sampled_channel.metadata.extend(metadata)

    redvox_packet.evenly_sampled_channels.extend([evenly_sampled_channel])

    return redvox_packet


def with_unevenly_sampled_channel(redvox_packet: api900.api900_pb2.RedvoxPacket,
                                  channel_types: typing.List[int],
                                  sensor_name: str,
                                  timestamps: typing.List[int],
                                  payload: typing.List[float],
                                  value_means: typing.List[float],
                                  value_stds: typing.List[float],
                                  value_medians: typing.List[float],
                                  sample_interval_mean: float,
                                  sample_interval_std: float,
                                  sample_interval_median: float,
                                  metadata: typing.List[str]) -> api900.api900_pb2.RedvoxPacket:
    unevenly_sampled_channel = api900.api900_pb2.UnevenlySampledChannel()
    unevenly_sampled_channel.channel_types.extend(channel_types)
    unevenly_sampled_channel.sensor_name = sensor_name
    unevenly_sampled_channel.timestamps_microseconds_utc.extend(timestamps)
    unevenly_sampled_channel.float32_payload.payload.extend(payload)
    unevenly_sampled_channel.value_means.extend(value_means)
    unevenly_sampled_channel.value_stds.extend(value_stds)
    unevenly_sampled_channel.value_medians.extend(value_medians)
    unevenly_sampled_channel.sample_interval_mean = sample_interval_mean
    unevenly_sampled_channel.sample_interval_std = sample_interval_std
    unevenly_sampled_channel.sample_interval_median = sample_interval_median
    unevenly_sampled_channel.metadata.extend(metadata)

    redvox_packet.unevenly_sampled_channels.extend([unevenly_sampled_channel])

    return redvox_packet


def simple_mic_packet():
    packet = base_packet()
    packet.metadata.extend(["a", "b", "c", "d"])
    return with_evenly_sampled_channel(packet,
                                       [api900.api900_pb2.MICROPHONE],
                                       "test microphone sensor name",
                                       80.0,
                                       1519166348000000,
                                       [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                                       [5.5],
                                       [3.0277],
                                       [5.5],
                                       ["a", "b", "c", "d"])


def simple_unevenly_sampled_packet():
    return with_unevenly_sampled_channel(base_packet(),
                                         [api900.api900_pb2.OTHER],
                                         "test other sensor name",
                                         [1, 2, 3, 4, 5],
                                         [1.0, 2.0, 3.0, 4.0, 5.0],
                                         [1.0],
                                         [2.0],
                                         [3.0],
                                         1.0,
                                         2.0,
                                         3.0,
                                         [])


def simple_gps_packet():
    return with_unevenly_sampled_channel(base_packet(),
                                         [api900.api900_pb2.LATITUDE,
                                          api900.api900_pb2.LONGITUDE,
                                          api900.api900_pb2.SPEED,
                                          api900.api900_pb2.ALTITUDE],
                                         "test gps sensor name",
                                         [1, 2, 3, 4, 5],
                                         [19.0, 155.0, 1.0, 25.0,
                                          20.0, 156.0, 2.0, 26.0,
                                          21.0, 157.0, 3.0, 27.0,
                                          22.0, 158.0, 4.0, 28.0,
                                          23.0, 159.0, 5.0, 29.0],
                                         [1, 2, 3, 4],
                                         [1, 2, 3, 4],
                                         [1, 2, 3, 4],
                                         1.0,
                                         2.0,
                                         3.0,
                                         [])


def multi_channel_packet():
    packet = simple_gps_packet()
    packet = with_evenly_sampled_channel(packet,
                                         [api900.api900_pb2.MICROPHONE],
                                         "test microphone sensor name",
                                         80.0,
                                         1519166348000000,
                                         [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                                         [5.5],
                                         [3.0277],
                                         [5.5],
                                         ["a", "b", "c"])
    packet = with_unevenly_sampled_channel(packet,
                                           [api900.api900_pb2.OTHER],
                                           "test other sensor name",
                                           [1, 2, 3, 4, 5],
                                           [1.0, 2.0, 3.0, 4.0, 5.0],
                                           [1.0],
                                           [2.0],
                                           [3.0],
                                           1.0,
                                           2.0,
                                           3.0,
                                           [])

    return packet
