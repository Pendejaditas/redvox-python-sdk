#!/usr/bin/env python3

"""
This module provides methods and classes for requesting bulk RedVox data.
"""

import bz2
import logging
import multiprocessing
import os
from typing import Callable, Dict, List, Tuple, Union

import numpy as np
import requests


log = logging.getLogger(__name__)


class ProcessPool:
    """
    Creates a process pool used for fetching the files from S3.
    """

    def __init__(self,
                 num_processes: int,
                 func: Callable[[List[str], str], None],
                 data: List[str],
                 out_dir: str,
                 retries: int):
        """
        Instantiates a new process pool.
        :param num_processes: The number of processes to create.
        :param func: The function to run which should take a list of strings representing data keys and a string
                     representing the out_dir.
        :param data: The list of data keys to process.
        :param out_dir: The output directory to write the data files to.
        :param retries: The number of times the HTTP client should retry getting a file.
        """

        self.num_processes: int = num_processes
        self.func: Callable[[List[str]], None] = func
        self.data: List[List[str]] = list(map(list, np.array_split(np.array(data), num_processes)))
        self.out_dir = out_dir
        self.retries = retries

    def run(self):
        """
        Runs this process pool. This will block until all processes finish fetching data.
        """
        processes: List[multiprocessing.Process] = []

        for i in range(self.num_processes):
            process: multiprocessing.Process = multiprocessing.Process(target=self.func, args=(self.data[i],
                                                                                               self.out_dir,
                                                                                               self.retries))
            processes.append(process)
            process.start()

        # Wait for all processes to finish
        for process in processes:
            process.join()


def find_between(start: str, end: str, contents: str) -> str:
    """
    Find the string contents between two other strings.
    :param start: The first string.
    :param end: The seconds string.
    :param contents: The full string.
    :return: The contents between the start and end strings.
    """
    s = contents.find(start)
    e = contents.find(end)
    return contents[s + len(start):e]


def get_file(url: str,
             session: requests.Session,
             out_dir: str,
             retries: int) -> Tuple[str, int]:
    """
    Attempts to download a file from S3.
    :param url: The URL to retrieve.
    :param session: The HTTP session.
    :param out_dir: The output directory where files will be stored.
    :param retries: The number of times to retry failed file downloads.
    :return: A tuple containing the data_key and the length of the download response.
    """
    try:
        resp: requests.Response = session.get(url)
        if resp.status_code == 200:
            data_key = find_between("/rdvxdata/", "?X-Amz-Algorithm=", url)

            directory = os.path.dirname(data_key)
            full_dir = f"{out_dir}/{directory}"
            if not os.path.exists(full_dir):
                log.info(f"Directory {full_dir} does not exist, creating it")
                os.makedirs(full_dir)

            full_path = f"{out_dir}/{data_key}"
            with open(full_path, "wb") as fout:
                flen = fout.write(resp.content)
                log.info(f"Wrote {full_path} {flen}")

            return data_key, len(resp.content)

        else:
            log.error(f"Received error response when requesting data for url={url}: {resp.status_code} {resp.text}")
            if retries > 0:
                log.info(f"Retrying with {retries} retries")
                get_file(url, session, out_dir, retries - 1)
            log.error(f"All retries exhausted, could not get {url}")
            return "", 0
    except Exception as e:
        log.error(f"Encountered an error while getting data for {url}: {str(e)}")
        if retries > 0:
            log.info(f"Retrying with {retries} retries")
            get_file(url, session, out_dir, retries - 1)
        log.error(f"All retries exhausted, could not get {url}")
        return "", 0


def get_files(urls: List[str], out_dir: str, retries: int) -> None:
    """
    Download files from S3.
    :param urls: The URL of the files to download.
    :param out_dir: The output directory to store the downloaded files.
    :param retries: The number of retries for failed downloads.
    """
    session: requests.Session = requests.Session()

    for url in urls:
        data_key, resp_len = get_file(url, session, out_dir, retries)
        log.info(f"Recv {data_key} with len={resp_len}")


def handle_ok_resp(resp: requests.Response,
                   out_dir: str,
                   retries: int) -> bool:
    """
    Handle an Ok response from the RedVox data_server.
    :param resp: The response to handle.
    :param out_dir: The output directory to store downloaded files.
    :param retries: The number of retries to make on failed downloads.
    :return: True if this succeeds, False otherwise.
    """
    log.info("Handling ok response")

    compressed_index: bytes = resp.content
    log.info(f"Got compressed index ({len(compressed_index)} bytes)")

    decompressed_index: bytes = bz2.decompress(compressed_index)
    log.info(f"Got decompressed index ({len(decompressed_index)} bytes)")

    str_data: str = decompressed_index.decode()
    parsed_data: List[str] = list(
        filter(lambda line: len(line) > 0, map(lambda line: line.strip(), str_data.split("\n"))))
    log.info(f"Got parsed data ({len(parsed_data)} entries)")

    process_pool: ProcessPool = ProcessPool(4, get_files, parsed_data, out_dir, retries)
    process_pool.run()

    return True


def make_data_req(out_dir: str,
                  host: str,
                  port: int,
                  email: str,
                  password: str,
                  req_start_s: int,
                  req_end_s: int,
                  redvox_ids: List[str],
                  retries: int) -> bool:
    """
    Makes a data request to the RedVox data_server.
    :param out_dir: The output directory to store downloaded files.
    :param host: The host of the data server.
    :param port: The port of the data server.
    :param email: The email address of the redvox.io user.
    :param password: The password of the redvox.io user.
    :param req_start_s: The request start time as seconds since the epoch.
    :param req_end_s: The request end time as seconds since the epoch.
    :param redvox_ids: A list of RedVox ids.
    :param retries: The number of retries to perform on failed downloads.
    :return: True if this succeeds, False otherwise.
    """
    req: Dict[str, Union[str, int, List[str]]] = {"email": email,
                                                  "password": password,
                                                  "start_ts_s": req_start_s,
                                                  "end_ts_s": req_end_s,
                                                  "redvox_ids": redvox_ids}
    url: str = f"http://{host}:{port}/req"

    resp: requests.Response = requests.post(url, json=req)

    if resp.status_code == 200:
        log.info("Recv ok response.")
        return handle_ok_resp(resp, out_dir, retries)
    elif resp.status_code == 400:
        log.error(f"Bad request error: {resp.status_code} {resp.text}")
        return False
    elif resp.status_code == 401:
        log.error(f"Authentication error: {resp.status_code} {resp.text}")
        return False
    else:
        log.error(f"Server error: {resp.status_code} {resp.text}")
        return False