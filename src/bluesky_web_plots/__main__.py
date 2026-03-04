import argparse
from pathlib import Path

from bluesky_web_plots.web_plots.callback import WebPlotCallback


def main():
    parser = argparse.ArgumentParser(description="Bluesky Web Plots")
    parser.add_argument(
        "--zmq-uri",
        type=str,
        help="ZMQ host to connect to for documents. Example 127.0.0.1:5578",
    )
    parser.add_argument(
        "--plot-host",
        type=str,
        default="127.0.0.1",
        help="Host for viewing the web interface.",
    )
    parser.add_argument(
        "--plot-port",
        type=int,
        default=12354,
        help="Port for viewing the web interface.",
    )
    parser.add_argument(
        "--columns",
        type=int,
        default=2,
        help="Number of columns for plots in the web UI.",
    )
    parser.add_argument(
        "--local-window-mode",
        action="store_true",
        help="Produce a local window for plots.",
    )
    parser.add_argument(
        "--ignore-streams",
        type=str,
        nargs="*",
        default=[],
        help=(
            "Streams to 'ignore' (not display plots for). Example: "
            "--ignore-streams baseline secondary"
        ),
    )
    parser.add_argument(
        "--timeline-config", type=str, default=None,
        help="Enable Timeline tab using this JSON config."
        )
    parser.add_argument(
        "--tiled-uri", type=str, default=None,
        help="Override Tiled URI from config (optional)."
        )
    parser.add_argument(
        "--tiled-api-key",
        default=None,
        help="Tiled API key. If omitted, uses env var TILED_API_KEY when present.",
    )
    args = parser.parse_args()

    print(args.ignore_streams)
    WebPlotCallback(
        zmq_uri=args.zmq_uri or None,
        plot_host=args.plot_host,
        plot_port=args.plot_port,
        columns=args.columns,
        local_window_mode=bool(args.local_window_mode),
        ignore_streams=args.ignore_streams,
        timeline_config=Path(args.timeline_config) if args.timeline_config else None,
        tiled_uri=args.tiled_uri,
        tiled_api_key=args.tiled_api_key,
    ).run()


if __name__ == "__main__":
    main()
