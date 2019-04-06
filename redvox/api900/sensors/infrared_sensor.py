import typing

import redvox.api900.constants as constants
import redvox.api900.lib.api900_pb2 as api900_pb2
from redvox.api900.sensors.unevenly_sampled_channel import UnevenlySampledChannel
from redvox.api900.sensors.unevenly_sampled_sensor import UnevenlySampledSensor

import numpy


class InfraredSensor(UnevenlySampledSensor):
    """High-level wrapper around light channels."""

    def __init__(self, unevenly_sampled_channel: UnevenlySampledChannel = None):
        """
        Initializes this class
        :param unevenly_sampled_channel: UnevenlySampledChannel with infrared sensor payload
        """
        super().__init__(unevenly_sampled_channel)
        self._unevenly_sampled_channel.set_channel_types([api900_pb2.INFRARED])

    def concat(self, infrared_sensor: 'InfraredSensor') -> 'InfraredSensor':
        if self._can_concat(infrared_sensor):
            concat_values = numpy.concatenate([self.payload_values(), infrared_sensor.payload_values()])
            return self._concat_timestamps(infrared_sensor)._concat_metadata(infrared_sensor) \
                .set_payload_values(concat_values)

    def payload_values(self) -> numpy.ndarray:
        """
        Returns a numpy ndarray of floats representing this sensor's payload.
        :return: A numpy ndarray of floats representing this sensor's payload.
        """
        return self._unevenly_sampled_channel.get_payload(api900_pb2.INFRARED)

    def set_payload_values(self, values: typing.Union[typing.List[float], numpy.ndarray]) -> 'InfraredSensor':
        """
        Sets this channel's payload values.
        :param values: Payload values.
        :return: An instance of the sensor.
        """
        self._unevenly_sampled_channel.set_payload(values, constants.PayloadType.FLOAT64_PAYLOAD)
        return self

    def payload_mean(self) -> float:
        """
        The mean of this channel's payload.
        :return: Mean of this channel's payload.
        """
        return self._unevenly_sampled_channel.get_value_mean(api900_pb2.INFRARED)

    def payload_median(self) -> float:
        """
        The median of this channel's payload.
        :return: Median of this channel's payload.
        """
        return self._unevenly_sampled_channel.get_value_median(api900_pb2.INFRARED)

    def payload_std(self) -> float:
        """
        The standard deviation of this channel's payload.
        :return: Standard deviation of this channel's payload.
        """
        return self._unevenly_sampled_channel.get_value_std(api900_pb2.INFRARED)