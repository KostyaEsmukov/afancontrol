import logging
import os
import signal
import threading
from contextlib import ExitStack
from pathlib import Path
from typing import Optional

import click

from afancontrol.config import (
    DEFAULT_CONFIG,
    DEFAULT_PIDFILE,
    DaemonCLIConfig,
    parse_config,
)
from afancontrol.manager import Manager
from afancontrol.metrics import Metrics, NullMetrics, PrometheusMetrics
from afancontrol.report import Report


@click.command()
@click.option("-t", "--test", is_flag=True, help="Test config")
@click.option("-v", "--verbose", is_flag=True, help="Increase logging verbosity")
@click.option(
    "-c",
    "--config",
    help="Config path",
    default=DEFAULT_CONFIG,
    show_default=True,
    type=click.Path(exists=True, dir_okay=False),
)
@click.option(
    "--pidfile",
    help="Pidfile path (default is %s)" % DEFAULT_PIDFILE,
    # The default is set by the `config` module.
    type=click.Path(exists=False),
)
@click.option(
    "--logfile",
    help="Logfile path (log to stdout by default)",
    type=click.Path(exists=False),
)
@click.option(
    "--exporter-listen-host",
    help="Prometheus exporter listen host, e.g. `127.0.0.1:8000` (disabled by default)",
    type=str,
)
def daemon(
    *,
    test: bool,
    verbose: bool,
    config: str,
    pidfile: str,
    logfile: str,
    exporter_listen_host: str
):
    """The main program of afancontrol."""

    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)

    config_path = Path(config)
    daemon_cli_config = DaemonCLIConfig(
        pidfile=pidfile, logfile=logfile, exporter_listen_host=exporter_listen_host
    )
    parsed_config = parse_config(config_path, daemon_cli_config)

    if parsed_config.daemon.exporter_listen_host:
        metrics: Metrics = PrometheusMetrics(parsed_config.daemon.exporter_listen_host)
    else:
        metrics = NullMetrics()

    manager = Manager(
        arduino_connections=parsed_config.arduino_connections,
        fans=parsed_config.fans,
        readonly_fans=parsed_config.readonly_fans,
        temps=parsed_config.temps,
        mappings=parsed_config.mappings,
        report=Report(report_command=parsed_config.report_cmd),
        triggers_config=parsed_config.triggers,
        metrics=metrics,
    )

    pidfile_instance: Optional[PidFile] = None
    if parsed_config.daemon.pidfile is not None:
        pidfile_instance = PidFile(parsed_config.daemon.pidfile)

    if test:
        print("Config file '%s' is good" % config_path)
        return

    if parsed_config.daemon.logfile:
        # Logging to file should not be configured when running in
        # the config test mode.
        file_handler = logging.FileHandler(parsed_config.daemon.logfile)
        file_handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)s:%(name)s:%(message)s")
        )
        logging.getLogger().addHandler(file_handler)

    signals = Signals()
    signal.signal(signal.SIGTERM, signals.sigterm)
    signal.signal(signal.SIGQUIT, signals.sigterm)
    signal.signal(signal.SIGINT, signals.sigterm)
    signal.signal(signal.SIGHUP, signals.sigterm)

    with ExitStack() as stack:
        if pidfile_instance is not None:
            stack.enter_context(pidfile_instance)
            pidfile_instance.save_pid(os.getpid())

        stack.enter_context(manager)

        # Make a first tick. If something is wrong, (e.g. bad fan/temp
        # file paths), an exception would be raised here.
        manager.tick()

        while not signals.wait_for_term_queued(parsed_config.daemon.interval):
            manager.tick()


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
                "Remove this file if it's not." % self
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
