import os.path
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

import redvox
import redvox.api1000.proto.redvox_api_m_pb2 as api_m
import redvox.common.date_time_utils as dtu
import redvox.common.session_io as s_io
import redvox.common.session_model_utils as smu
from redvox.cloud import session_model_api as cloud_sm
from redvox.common.errors import RedVoxError, RedVoxExceptions


SESSION_VERSION = "2023-06-28"  # Version of the SessionModel
CLIENT_NAME = "redvox-sdk/session_model"  # Name of the client used to create the SessionModel
CLIENT_VERSION = SESSION_VERSION  # Version of the client used to create the SessionModel
APP_NAME = "RedVox"  # Default name of the app
DAILY_SESSION_NAME = "Day"  # Identifier for day-long dynamic sessions
HOURLY_SESSION_NAME = "Hour"  # Identifier for hour-long dynamic sessions


class SessionModel:
    """
    SDK version of Session from the cloud API
    """

    def __init__(
        self, session: Optional[cloud_sm.Session] = None, dynamic: Optional[Dict[str, cloud_sm.DynamicSession]] = None
    ):
        self.cloud_session: Optional[cloud_sm.Session] = session
        self.dynamic_sessions: Dict[str, cloud_sm.DynamicSession] = {} if dynamic is None else dynamic
        self._sdk_version: str = redvox.VERSION
        self._errors: RedVoxExceptions = RedVoxExceptions("SessionModel")

    def __repr__(self):
        return (
            f"cloud_session: {self.cloud_session}, "
            f"dynamic_sessions: {self.dynamic_sessions}, "
            f"sdk_version: {self._sdk_version}"
            f"errors: {self._errors}"
        )

    def as_dict(self) -> dict:
        """
        :return: SessionModel as dictionary
        """
        return {
            "cloud_session": self.cloud_session.to_dict(),
            "dynamic_sessions": {n: m.to_dict() for n, m in self.dynamic_sessions.items()},
        }

    @staticmethod
    def from_dict(dictionary: Dict) -> "SessionModel":
        """
        :param dictionary: dictionary to read from
        :return: SessionModel from the dict
        """
        return SessionModel(
            cloud_sm.Session.from_dict(dictionary["cloud_session"]),
            {n: cloud_sm.DynamicSession.from_dict(m) for n, m in dictionary["dynamic_sessions"].items()},
        )

    def compress(self, out_dir: str = ".") -> Path:
        """
        Compresses this SessionModel to a file at out_dir.
        Uses the id and start_ts to name the file.

        :param out_dir: Directory to save file to.  Default "." (current directory)
        :return: The path to the written file.
        """
        return s_io.compress_session_model(self, out_dir)

    def save(self, out_type: str = "json", out_dir: str = ".") -> Path:
        """
        Save the SessionModel to disk.  Options for out_type are "json" for JSON file and "pkl" for .pkl file.
        Defaults to "json".  File will be named after id and start_ts of the SessionModel

        :param out_type: "json" for JSON file and "pkl" for .pkl file
        :param out_dir: Directory to save file to.  Default "." (current directory)
        :return: path to saved file
        """
        if out_type == "pkl":
            return self.compress(out_dir)
        return s_io.session_model_to_json_file(self, out_dir)

    @staticmethod
    def load(file_path: str) -> "SessionModel":
        """
        Load only works on a JSON or .pkl file.

        :param file_path: full name and path to the SessionModel file
        :return: SessionModel from a JSON or .pkl file.
        """
        ext = os.path.splitext(file_path)[1]
        if ext == ".json":
            return SessionModel.from_dict(s_io.session_model_dict_from_json_file(file_path))
        elif ext == ".pkl":
            return s_io.decompress_session_model(file_path)
        else:
            raise ValueError(f"{file_path} has unknown file extension; this function only accepts json and pkl files.")

    def default_file_name(self) -> str:
        """
        :return: Default file name as [id]_[start_ts]_model, with start_ts as integer of microseconds
                    since epoch UTC.  File extension NOT included.
        """
        return (
            f"{self.cloud_session.id}_"
            f"{0 if np.isnan(self.cloud_session.start_ts) else self.cloud_session.start_ts}_model"
        )

    @staticmethod
    def create_from_packet(packet: api_m.RedvoxPacketM) -> "SessionModel":
        """
        :param packet: API M packet of data to read
        :return: Session using the data from the packet
        """
        try:
            duration = (
                packet.timing_information.packet_end_mach_timestamp
                - packet.timing_information.packet_start_mach_timestamp
            )
            all_sensors = smu.get_all_sensors_in_packet(packet)
            sensors = [cloud_sm.Sensor(s[0], s[1], smu.add_to_stats(s[2])) for s in all_sensors]
            local_ts = smu.get_local_timesync(packet)
            if local_ts is None:
                raise RedVoxError(
                    f"Unable to find timing data for station {packet.station_information.id}.\n"
                    f"Timing is required to complete SessionModel.\nNow Quitting."
                )
            fst_lst = cloud_sm.FirstLastBufTimeSync([], smu.NUM_BUFFER_POINTS, [], smu.NUM_BUFFER_POINTS)
            for f in local_ts[5]:
                smu.add_to_fst_buffer(fst_lst.fst, fst_lst.fst_max_size, f.ts, f)
                smu.add_to_lst_buffer(fst_lst.lst, fst_lst.lst_max_size, f.ts, f)
            timing = cloud_sm.Timing(local_ts[0], local_ts[1], local_ts[2], local_ts[3], local_ts[4], fst_lst)
            result = SessionModel(
                cloud_sm.Session(
                    id=packet.station_information.id,
                    uuid=packet.station_information.uuid,
                    desc=packet.station_information.description,
                    start_ts=int(packet.timing_information.app_start_mach_timestamp),
                    client=CLIENT_NAME,
                    client_ver=CLIENT_VERSION,
                    session_ver=SESSION_VERSION,
                    app=APP_NAME,
                    api=int(packet.api),
                    sub_api=int(packet.sub_api),
                    make=packet.station_information.make,
                    model=packet.station_information.model,
                    app_ver=packet.station_information.app_version,
                    owner=packet.station_information.auth_id,
                    private=packet.station_information.is_private,
                    packet_dur=duration,
                    sensors=sensors,
                    n_pkts=1,
                    timing=timing,
                    sub=[],
                )
            )
            result.sub = [result.add_dynamic_day(packet)]
        except Exception as e:
            # result = SessionModel(station_description=f"FAILED: {e}")
            raise e
        return result

    @staticmethod
    def create_from_stream(data_stream: List[api_m.RedvoxPacketM]) -> "SessionModel":
        """
        :param data_stream: list of API M packets from a single station to read
        :return: SessionModel using the data packets from the stream
        """
        p1 = data_stream.pop(0)
        model = SessionModel.create_from_packet(p1)
        for p in data_stream:
            model.add_data_from_packet(p)
        data_stream.insert(0, p1)
        return model

    def add_data_from_packet(self, packet: api_m.RedvoxPacketM):
        """
        Adds the data from the packet to the SessionModel.
        If the packet doesn't match the key of the SessionModel, writes an error and no data is added

        :param packet: packet to add
        """
        if (
            self.cloud_session.session_key() != f"{packet.station_information.id}:{packet.station_information.uuid}:"
            f"{int(packet.timing_information.app_start_mach_timestamp)}"
        ):
            self._errors.append(
                "Attempted to add packet with invalid key: "
                f"{packet.station_information.id}:{packet.station_information.uuid}:"
                f"{int(packet.timing_information.app_start_mach_timestamp)}"
            )
            return
        local_ts = smu.get_local_timesync(packet)
        if local_ts is None:
            self._errors.append(
                f"Timesync doesn't exist in packet starting at "
                f"{packet.timing_information.packet_start_mach_timestamp}."
            )
        else:
            timing = self.cloud_session.timing
            for f in local_ts[5]:
                smu.add_to_fst_buffer(timing.fst_lst.fst, timing.fst_lst.fst_max_size, f.ts, f)
                smu.add_to_lst_buffer(timing.fst_lst.lst, timing.fst_lst.lst_max_size, f.ts, f)
            timing.n_ex += local_ts[2]
            timing.mean_lat = (timing.mean_lat * self.cloud_session.n_pkts + local_ts[3]) / (
                self.cloud_session.n_pkts + 1
            )
            timing.mean_off = (timing.mean_off * self.cloud_session.n_pkts + local_ts[4]) / (
                self.cloud_session.n_pkts + 1
            )
            if local_ts[0] < timing.first_data_ts:
                timing.first_data_ts = local_ts[0]
            if local_ts[1] > timing.last_data_ts:
                timing.last_data_ts = local_ts[1]
        all_sensors = smu.get_all_sensors_in_packet(packet)
        for s in all_sensors:
            sensor = self.get_sensor(s[0], s[1])
            if sensor is not None:
                sensor.sample_rate_stats = smu.add_to_stats(s[2], sensor.sample_rate_stats)
            else:
                self.cloud_session.sensors.append(cloud_sm.Sensor(s[0], s[1], smu.add_to_stats(s[2])))
        self.add_dynamic_day(packet)
        self.cloud_session.n_pkts += 1

    def add_dynamic_hour(self, data: dict, packet_start: float, session_key: str) -> str:
        """
        Add (or update an existing session if key exists) a dynamic session with length of 1 hour using a single packet

        :param data: dictionary of data to add
        :param packet_start: starting timestamp of the packet in microseconds since epoch UTC
        :param session_key: the session key of the parent Session
        :return: the key to the new dynamic session
        """
        start_dt = dtu.datetime_from_epoch_microseconds_utc(packet_start)
        hour_start_dt = dtu.datetime(start_dt.year, start_dt.month, start_dt.day, start_dt.hour)
        hour_end_ts = int(dtu.datetime_to_epoch_microseconds_utc(hour_start_dt + dtu.timedelta(hours=1)))
        hour_start_ts = int(dtu.datetime_to_epoch_microseconds_utc(hour_start_dt))
        key = f"{session_key}:{hour_start_ts}:{hour_end_ts}"
        if key in self.dynamic_sessions.keys():
            self._update_dynamic_session(key, data, [f"{packet_start}"])
        else:
            self.dynamic_sessions[key] = cloud_sm.DynamicSession(
                1,
                smu.add_location_data(data["location"]),
                smu.add_to_stats(data["battery"]),
                smu.add_to_stats(data["temperature"]),
                session_key,
                hour_start_ts,
                hour_end_ts,
                HOURLY_SESSION_NAME,
                [f"{packet_start}"],
            )
        return key

    def add_dynamic_day(self, packet: api_m.RedvoxPacketM) -> str:
        """
        Add (or update an existing session if key exists) a dynamic session with length of 1 day using a single packet

        :param packet: packet to read data from
        :return: the key to the new or updated dynamic session
        """
        data = smu.get_dynamic_data(packet)
        start_dt = dtu.datetime_from_epoch_microseconds_utc(packet.timing_information.packet_start_mach_timestamp)
        day_start_dt = dtu.datetime(start_dt.year, start_dt.month, start_dt.day)
        day_end_ts = int(dtu.datetime_to_epoch_microseconds_utc(day_start_dt + dtu.timedelta(days=1)))
        day_start_ts = int(dtu.datetime_to_epoch_microseconds_utc(day_start_dt))
        session_key = (
            f"{packet.station_information.id}:{packet.station_information.uuid}:"
            f"{packet.timing_information.app_start_mach_timestamp}"
        )
        key = f"{session_key}:{day_start_ts}:{day_end_ts}"
        hourly_key = self.add_dynamic_hour(data, packet.timing_information.packet_start_mach_timestamp, session_key)
        if key in self.dynamic_sessions.keys():
            self._update_dynamic_session(key, data, [hourly_key])
        else:
            self.dynamic_sessions[key] = cloud_sm.DynamicSession(
                1,
                smu.add_location_data(data["location"]),
                smu.add_to_stats(data["battery"]),
                smu.add_to_stats(data["temperature"]),
                session_key,
                day_start_ts,
                day_end_ts,
                DAILY_SESSION_NAME,
                [hourly_key],
            )
        return key

    def _update_dynamic_session(self, key: str, data: Dict, sub: List[str]):
        """
        update a dynamic session with a given key.

        :param key: key to the dynamic session
        :param data: dictionary of data to add
        :param sub: the list of keys that the dynamic session is linked to
        """
        if key not in self.dynamic_sessions.keys():
            self._errors.append(f"Attempted to update non-existent key: {key}.")
        else:
            dyn_sess = self.dynamic_sessions[key]
            dyn_sess.n_pkts += 1
            dyn_sess.location = smu.add_location_data(data["location"], dyn_sess.location)
            dyn_sess.battery = smu.add_to_stats(data["battery"], dyn_sess.battery)
            dyn_sess.temperature = smu.add_to_stats(data["temperature"], dyn_sess.temperature)
            for s in sub:
                if s in self.dynamic_sessions.keys():
                    self._update_dynamic_session(s, data, self.dynamic_sessions[s].sub)

    def sdk_version(self) -> str:
        """
        :return: sdk version used to create the SessionModel
        """
        return self._sdk_version

    def num_sensors(self) -> int:
        """
        :return: number of sensors in the Session
        """
        return len(self.cloud_session.sensors)

    def get_sensor_names(self) -> List[str]:
        """
        :return: number of sensors in the Session
        """
        return [n.name for n in self.cloud_session.sensors]

    def get_sensor(self, name: str, desc: Optional[str] = None) -> Optional[cloud_sm.Sensor]:
        """
        :param name: name of the sensor to get
        :param desc: Optional description of the sensor to get.  If None, will get the first sensor that
                        matches the name given.  Default None.
        :return: the first sensor that matches the name and description given or None if sensor was not found
        """
        for s in self.cloud_session.sensors:
            if s.name == name:
                if desc is None or s.description == desc:
                    return s
        return None

    def audio_sample_rate_nominal_hz(self) -> float:
        """
        :return: number of sensors in the Session
        """
        for n in self.cloud_session.sensors:
            if n.name == "audio":
                return n.sample_rate_stats.welford.mean

    def get_daily_dynamic_sessions(self) -> List[cloud_sm.DynamicSession]:
        """
        :return: all day-long dynamic sessions in the Session
        """
        return [n for n in self.dynamic_sessions.values() if n.dur == DAILY_SESSION_NAME]

    def get_hourly_dynamic_sessions(self) -> List[cloud_sm.DynamicSession]:
        """
        :return: all hour-long dynamic sessions in the Session
        """
        return [n for n in self.dynamic_sessions.values() if n.dur == HOURLY_SESSION_NAME]

    def print_errors(self):
        """
        print all errors encountered by the SessionModel
        """
        self._errors.print()


class LocalSessionModels:
    """
    SDK version of SessionModelsResp from the cloud API
    """

    def __init__(self):
        self.sessions: Dict[str, SessionModel] = {}

    def add_packet(self, packet: api_m.RedvoxPacketM) -> str:
        """
        add a packet to one of the models, or make a new one

        :param packet: packet of data to add.
        :return: key of new or updated packet
        """
        key = (
            f"{packet.station_information.id}:{packet.station_information.uuid}:"
            f"{int(packet.timing_information.app_start_mach_timestamp)}"
        )
        if key not in self.sessions.keys():
            self.sessions[key] = SessionModel.create_from_packet(packet)
        else:
            self.sessions[key].add_data_from_packet(packet)
        return self.sessions[key].cloud_session.session_key()

    def get_session(self, key: str) -> Optional[SessionModel]:
        """
        :param key: key of SessionModel to get
        :return: SessionModel that matches the given key or None
        """
        if key in self.sessions.keys():
            return self.sessions[key]
        return None
