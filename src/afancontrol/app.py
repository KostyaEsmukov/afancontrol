import argparse
import logging
import os
import signal
import sys
import threading
from contextlib import ExitStack
from pathlib import Path
from typing import Optional

from afancontrol.manager.manager import Manager
from afancontrol.manager.report import Report

from .config import DEFAULT_CONFIG, DEFAULT_PIDFILE, DaemonCLIConfig, parse_config
from .logger import logger
from .metrics import Metrics, NullMetrics, PrometheusMetrics


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--test", help="test config", action="store_true")
    parser.add_argument(
        "-d", "--daemon", help="execute in daemon mode", action="store_true"
    )
    parser.add_argument(
        "-v", "--verbose", help="increase output verbosity", action="store_true"
    )
    parser.add_argument(
        "-c",
        "--config",
        help="config path [%s]" % DEFAULT_CONFIG,
        default=DEFAULT_CONFIG,
    )
    parser.add_argument("--pidfile", help="pidfile path [%s]" % DEFAULT_PIDFILE)
    parser.add_argument("--logfile", help="logfile path (disabled by default)")
    parser.add_argument(
        "--exporter-listen-host",
        help=(
            "prometheus exporter listen host, e.g. `127.0.0.1:8000` "
            "(disabled by default)"
        ),
    )
    return parser.parse_args()


def main():
    args = parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    config_path = Path(args.config)
    daemon_cli_config = DaemonCLIConfig(
        pidfile=args.pidfile,
        logfile=args.logfile,
        exporter_listen_host=args.exporter_listen_host,
    )
    config = parse_config(config_path, daemon_cli_config)

    if config.daemon.exporter_listen_host:
        metrics = PrometheusMetrics(config.daemon.exporter_listen_host)  # type: Metrics
    else:
        metrics = NullMetrics()

    manager = Manager(
        fans=config.fans,
        temps=config.temps,
        mappings=config.mappings,
        report=Report(report_command=config.report_cmd),
        triggers_config=config.triggers,
        metrics=metrics,
        fans_speed_check_interval=config.daemon.fans_speed_check_interval,
    )

    pidfile = None  # type: Optional[PidFile]
    if config.daemon.pidfile is not None:
        pidfile = PidFile(config.daemon.pidfile)

    if args.test:
        print("Config file '%s' if good" % config_path)
        return

    if config.daemon.logfile:
        # Logging to file should not be configured when running in
        # the config test mode.
        logging.getLogger().addHandler(logging.FileHandler(config.daemon.logfile))

    signals = Signals()
    signal.signal(signal.SIGTERM, signals.sigterm)
    signal.signal(signal.SIGQUIT, signals.sigterm)
    signal.signal(signal.SIGINT, signals.sigterm)
    signal.signal(signal.SIGHUP, signals.sigterm)

    with ExitStack() as stack:
        if pidfile is not None:
            stack.enter_context(pidfile)
            # Ensure that pidfile is writable before forking:
            pidfile.save_pid(os.getpid())

        stack.enter_context(manager)

        # Make a first tick without forking. If something is wrong,
        # (e.g. bad fan/temp file paths), an exception would be raised
        # here.
        manager.tick()

        if args.daemon:
            daemonize(pidfile)

        while not signals.wait_for_term_queued(config.daemon.interval):
            manager.tick()


def daemonize(pidfile: Optional["PidFile"]) -> None:  # pragma: no cover
    child_pid = os.fork()
    # child_pid == 0 -- the daemonized process, which is
    #   now responsible for the `manager`'s context manager.
    #
    # child_pid != 0 -- the master process, which MUST NOT
    #   reach the end of the `with` block -- it must be terminated
    #   with the `sys.exit` call.
    if child_pid != 0:
        try:
            if pidfile is not None:
                pidfile.save_pid(child_pid)
        except Exception:
            logger.error("Unable to save process pid=%s to %s", child_pid, pidfile)
            sys.exit(1)
        else:
            sys.exit(0)


class PidFile:
    def __init__(self, pidfile: str) -> None:
        self.pidfile = Path(pidfile)

    def __str__(self):
        return "%s" % self.pidfile

    def __enter__(self):
        self.raise_if_pidfile_exists()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.remove()
        return None

    def save_pid(self, pid: int) -> None:
        self.pidfile.write_text(str(pid))

    def remove(self) -> None:
        self.pidfile.unlink()

    def raise_if_pidfile_exists(self) -> None:
        if self.pidfile.exists():
            raise RuntimeError(
                "pidfile %s already exists. Is daemon already running? "
                "Remove this file if it's not.",
                self,
            )


class Signals:
    def __init__(self):
        self._term_event = threading.Event()

    def sigterm(self, signum, stackframe):
        self._term_event.set()

    def wait_for_term_queued(self, seconds: float) -> bool:
        is_set = self._term_event.wait(seconds)
        if is_set:
            return True
        return False
