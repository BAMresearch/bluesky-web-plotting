import os
import signal
import time
from multiprocessing import Process, Queue

import pytest
import zmq
from bluesky.callbacks.zmq import Proxy, Publisher
from bluesky.run_engine import RunEngine

from bluesky_web_plots import WebPlotCallback

EXAMPLE_MODE = os.getenv("BLUESKY_WEB_PLOTS_EXAMPLE_MODE", "0") == "1"


def _start_proxy_and_dispatcher(exception_queue: Queue, in_port: int, out_port: int) -> None:
    """Top-level so multiprocessing 'spawn' can pickle it on macOS."""
    try:
        proxy = Proxy(in_port=in_port, out_port=out_port)
        proxy.start()
    except Exception as e:
        exception_queue.put(e)


def _start_plotly_callback(exception_queue: Queue, zmq_uri: str, example_mode: bool) -> None:
    """Top-level so multiprocessing spawn can pickle it."""
    try:
        callback = WebPlotCallback(zmq_uri=zmq_uri, local_window_mode=example_mode)

        if example_mode:
            if callback._local_window_process is None:
                raise RuntimeError(
                    "Example mode requested but local window process could not be created. "
                    "Have you installed the local optional dependencies?"
                )

            def _wait_for_local_window_close(signum, frame):
                assert callback._local_window_process is not None
                while callback._local_window_process.is_alive():
                    pass
                raise SystemExit(0)

            signal.signal(signal.SIGINT, _wait_for_local_window_close)

        callback.run()
    except Exception as e:
        exception_queue.put(e)


@pytest.fixture(scope="session")
def zmq_proxy_subprocess():
    exception_queue = Queue()

    zmq_proxy = Process(
        target=_start_proxy_and_dispatcher,
        args=(exception_queue, 5577, 5578),
        daemon=True,
    )
    try:
        zmq_proxy.start()
        time.sleep(1)
        yield zmq_proxy
    finally:
        if not zmq_proxy.is_alive():
            if not exception_queue.empty():
                raise exception_queue.get()
            else:
                raise RuntimeError("ZMQ proxy died during test.")
        zmq_proxy.terminate()
        zmq_proxy.join(timeout=1)
        zmq_proxy.close()


@pytest.fixture(scope="function")
def zmq_proxy_run_engine(zmq_proxy_subprocess):
    RE = RunEngine()
    publisher = Publisher(address="0.0.0.0:5577")
    RE.subscribe(publisher)
    try:
        yield RE
    finally:
        publisher.close()


@pytest.fixture(scope="function")
def threaded_callback_run_engine():
    RE = RunEngine()
    RE.subscribe(WebPlotCallback())
    return RE


@pytest.fixture(scope="function")
def plot_subprocess():
    exception_queue = Queue()

    def start_plotly_callback():
        try:
            callback = WebPlotCallback(
                zmq_uri="tcp://127.0.0.1:5578", local_window_mode=EXAMPLE_MODE
            )

            def wait_for_local_window_close(signum, frame):
                assert callback._local_window_process is not None
                while callback._local_window_process.is_alive():
                    # For use in example mode, wait for the user to close
                    # the local window.
                    pass
                exit(0)

            if EXAMPLE_MODE:
                if callback._local_window_process is None:
                    raise RuntimeError(
                        "Example mode requested but local window process could not be created. "
                        "Have you installed the local optional dependencies?"
                    )
                signal.signal(signal.SIGINT, wait_for_local_window_close)

            callback.run()
        except Exception as e:
            exception_queue.put(e)

    zmq_callback = Process(
        target=_start_plotly_callback,
        args=(exception_queue, "tcp://127.0.0.1:5578", EXAMPLE_MODE),
        daemon=True,
    )

    try:
        zmq_callback.start()
        time.sleep(1)
        yield zmq_callback
    finally:

        def wait_for_zmq_drain(out_address, timeout=2.0):
            ctx = zmq.Context()
            socket = ctx.socket(zmq.SUB)
            socket.connect(out_address)
            socket.setsockopt(zmq.SUBSCRIBE, b"")
            poller = zmq.Poller()
            poller.register(socket, zmq.POLLIN)
            last_msg_time = time.time()
            while True:
                socks = dict(poller.poll(timeout=100))
                if socket in socks and socks[socket] == zmq.POLLIN:
                    _ = socket.recv()
                    last_msg_time = time.time()
                elif time.time() - last_msg_time > timeout:
                    break
            socket.close()
            ctx.term()

        wait_for_zmq_drain("tcp://127.0.0.1:5578")
        if not zmq_callback.is_alive():
            if not exception_queue.empty():
                raise exception_queue.get()
            else:
                raise RuntimeError("ZMQ Plot callback died during test.")

        if EXAMPLE_MODE:
            join_time = None
            os.kill(zmq_callback.pid, signal.SIGINT)  # type: ignore
        else:
            join_time = 1
            zmq_callback.terminate()
        zmq_callback.join(timeout=join_time)
        zmq_callback.close()
