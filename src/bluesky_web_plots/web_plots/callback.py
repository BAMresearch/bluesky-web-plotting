import multiprocessing
from pprint import pformat
from queue import Queue
from typing import cast

from bluesky.callbacks.zmq import RemoteDispatcher
from event_model import RunStop
from event_model.documents import (
    DataKey,
    Document,
    Event,
    EventDescriptor,
    EventPage,
    RunStart,
)
from plotly.io import from_json

from bluesky_web_plots.figures.array import ArrayFigureCallback
from bluesky_web_plots.figures.base_figure import BaseFigureCallback
from bluesky_web_plots.figures.sample_map import SampleMapFigureCallback
from bluesky_web_plots.figures.scalar import ScalarFigureCallback
from bluesky_web_plots.logger import logger
from bluesky_web_plots.structures import Array, Base, Scalar
from bluesky_web_plots.structures.array import View
from bluesky_web_plots.structures.sample_map import SampleMap
from bluesky_web_plots.structures.scalar import PlotAgainst
from bluesky_web_plots.utils import hinted_fields

from .server import PlotServer


class WebPlotCallback:
    def __init__(
        self,
        zmq_uri: str | None = None,
        plot_host: str = "0.0.0.0",
        plot_port=12354,
        columns=3,
        local_window_mode: bool = False,
        ignore_streams: tuple[str, ...] = (),
    ):
        """A callback for plotting event document output through the web, with either simple,
        or complicated structures.

        If `zmq_uri` is not provided then it the window will open in local_window_mode mode as the
        callback is not running as a service.

        Args:
            zmq_uri (str | None):
                The ZMQ host to connect to for documents. If not provided then the callback
                can be ran directly as a RE.subscribe callback instead.
            plot_host (str):
                The host that will be used for viewing the web interface.
            plot_port (str):
                The port that will be used for viewing the web interface.
            columns (int):
                The number of columns that the plots will be packed into in the web ui.
            local_window_mode (bool):
                Spawn a local Qt5 editor.
            ignore_streams (tuple[str, ...]):
                Stream names to ignore and not plot, e.g ("baseline",)
        """

        self.PLOT_PORT = plot_port
        plot_host = plot_host.lstrip(
            "http://"
        )  # will fail if you try e.g "http://0.0.0.0"
        if zmq_uri is None:
            logger.warning(
                "Creating a callback without a ZMQ stream... The plotter will slow down your run engine substantially for very large seq-num plans."
            )
        else:
            # Ensure no "tcp://" prefix, this is added in the RemoteDispatcher
            zmq_uri = zmq_uri.lstrip("tcp://")

        self.ZMQ_URI = zmq_uri

        self._server = PlotServer(
            host=plot_host,
            port=plot_port,
            columns=columns,
        )

        self._current_run_start: RunStart | None = None
        self.document_queue: Queue[Document] = Queue()
        self._figures: dict[tuple[str, ...], BaseFigureCallback] = {}

        # User defined structures. Cleared on each new run.
        self._structures: dict[frozenset, Base] = {}

        self._IGNORE_STREAMS = ignore_streams  # Streams to ignore.
        self._ignore_descriptors = set()  # Desscriptor uids to ignore.

        # local_window_mode creates a local window pyqt window in a subprocess to view your plot.
        # A new one is made for each run whenever it's closed, mimicking best effort callback
        # and not relying on the browser process which may be slow from an abundance
        # of tabs, or a bad browser. The plots will still be viewable from a normal browser.
        if local_window_mode and self._can_use_local_window():
            self._local_window_mode = local_window_mode
            self._local_window_process = multiprocessing.Process(
                target=self._create_local_window
            )
        else:
            self._local_window_mode = local_window_mode
            self._local_window_process = None

        self._multi_data_key_structures: dict[
            frozenset[str], type[BaseFigureCallback]
        ] = {frozenset(SampleMap.__annotations__.keys()): SampleMapFigureCallback}

        logger.info(f"Starting gui at http://{plot_host}:{plot_port}")
        self._server.run()

    def _can_use_local_window(self) -> bool:
        try:
            from PyQt5.QtCore import QUrl  # noqa: F401 # pyright: ignore
            from PyQt5.QtWebEngineWidgets import (
                QWebEngineView,  # noqa: F401 # pyright: ignore
            )
            from PyQt5.QtWidgets import (
                QApplication,  # noqa: F401 # pyright: ignore
                QMainWindow,  # noqa: F401 # pyright: ignore
            )
        except ImportError as exception:
            logger.warning(
                f"\033[93mLocal window mode requires the 'local' optional dependencies. {exception} "
                "Install with: pip install .[local].\033[0m"
            )
            return False
        return True

    def _create_local_window(self):
        from PyQt5.QtCore import QUrl
        from PyQt5.QtWebEngineWidgets import QWebEngineView
        from PyQt5.QtWidgets import QApplication, QMainWindow

        app = QApplication([])
        window = QMainWindow()
        browser = QWebEngineView()
        browser.load(QUrl(f"http://localhost:{self.PLOT_PORT}"))
        window.setCentralWidget(browser)
        window.show()
        app.exec_()

    def run(self):
        """Runs the callback as a service listening to ZMQ for event documents."""

        if self.ZMQ_URI is None:
            raise ValueError(
                "Cannot run as a service as the ZMQ host or port was not provided on init."
            )

        remote_dispatcher = RemoteDispatcher(self.ZMQ_URI)
        remote_dispatcher.subscribe(self)
        logger.info(f"Connected to {self.ZMQ_URI} Ready to Plot, Ctrl + C to Exit")
        try:
            remote_dispatcher.start()
        except KeyboardInterrupt:
            print("Exiting...")
            remote_dispatcher.stop()

        if self._local_window_mode and self._local_window_process is not None:
            self._local_window_process.start()

    def __call__(self, name: str, document: Document):
        if (
            self._local_window_mode
            and self._local_window_process is not None
            and not self._local_window_process.is_alive()
        ):
            self._local_window_process.start()

        if name == "start":
            self.run_start(cast(RunStart, document))
        if name == "descriptor":
            self.descriptor(cast(EventDescriptor, document))
        if name == "event":
            self.event(cast(Event, document))

    def run_start(self, run_start: RunStart):
        # The figures are all on the other thread. We can dereference here.
        self._structures.clear()
        self._ignore_descriptors.clear()

        while not self._server.deleted_plot_queue.empty():
            del self._figures[self._server.deleted_plot_queue.get()]

        info = run_start.get("hints", {}).get("BLUESKY_LIVE_PLOTS", {})

        structures = info.get("STRUCTURES", ())

        self._structures = {frozenset(s["names"]): s for s in structures}
        if self._structures:
            logger.info(f"New plot structures {pformat(self._structures)}")

        for structure in structures:
            if frozenset(structure.keys()) in self._multi_data_key_structures:
                figure_class = self._multi_data_key_structures[
                    frozenset(structure.keys())
                ]
                names = (structure["names"],)
                if names not in self._figures:
                    new_figure = figure_class(structure)
                    new_figure.run_start(run_start)
                    # These figures aren't persistent we use the scan ID
                    # and future runs will create new figures from them.
                    self._figures[structure["names"]] = new_figure

        # Cache this now for
        self._current_run_start = run_start

        # Non-interactive serialised plots from run_start
        non_interactive_plots = info.get("SERIALISED_PLOT", {})
        for name, plot in non_interactive_plots.items():
            figure = from_json(plot)  # Validate it's a figure.
            logger.info(f"New serialised plot {name}")
            self._server.updated_plot_queue.put(((name,), figure))

        for figure in self._figures.values():
            figure.run_start(run_start)

    def _new_figure_from_datakey(
        self, name: str, data_key: DataKey
    ) -> BaseFigureCallback | None:
        names = frozenset((name,))
        if data_key["dtype"] in ("number", "integer"):
            return ScalarFigureCallback(
                cast(
                    Scalar,
                    self._structures.get(
                        names, Scalar(names=(name,), plot_against=PlotAgainst.SEQ_NUM)
                    ),
                )
            )
        if data_key["dtype"] == "array":
            return ArrayFigureCallback(
                cast(
                    Array,
                    self._structures.get(names, Array(names=(name,), view=View.SLICE)),
                )
            )

        logger.warning(
            f"No figure available for data key {name} with dtype {data_key['dtype']}"
        )

    def descriptor(self, descriptor: EventDescriptor):
        if descriptor.get("name") in self._IGNORE_STREAMS:
            self._ignore_descriptors.add(descriptor["uid"])

        plotted_fields = hinted_fields(descriptor) + [
            field for field in "data_keys" if field in self._structures
        ]
        for name in plotted_fields:
            names = (name,)
            if names not in self._figures:
                new_figure = self._new_figure_from_datakey(
                    name, descriptor["data_keys"][name]
                )
                if not new_figure:
                    continue
                # If the service starts post run_start, but before descriptor
                # it'll work, but you'll get 0 as your data key. Not really an issue.
                if self._current_run_start:
                    new_figure.run_start(self._current_run_start)
                self._figures[names] = new_figure

        for figure in self._figures.values():
            figure.descriptor(descriptor)

    def event(self, event: Event):
        if event["descriptor"] in self._ignore_descriptors:
            return

        datakeys = frozenset((event["data"].keys()))
        for names, figure in self._figures.items():
            if set(names) <= datakeys:
                figure.event(event)
                self._server.updated_plot_queue.put((names, figure.figure))

    def event_page(self, event_page: EventPage):
        if event_page["descriptor"] in self._ignore_descriptors:
            return
        datakeys = frozenset(event_page["data"].keys())
        for names, figure in self._figures.items():
            if set(names) <= datakeys:
                figure.event_page(event_page)
                self._server.updated_plot_queue.put((names, figure.figure))

    def run_stop(self, run_stop: RunStop):
        while not self._server.deleted_plot_queue.empty():
            del self._figures[self._server.deleted_plot_queue.get()]
