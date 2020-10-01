import abc
import contextlib
import threading
from http.server import HTTPServer
from socketserver import ThreadingMixIn
from timeit import default_timer
from typing import ContextManager, Mapping, Optional, Union

from afancontrol.arduino import ArduinoConnection, ArduinoName
from afancontrol.config import TempName
from afancontrol.fans import Fans
from afancontrol.logger import logger
from afancontrol.pwmfan import AnyFanName, FanName, ReadonlyFanName
from afancontrol.pwmfannorm import PWMFanNorm, ReadonlyPWMFanNorm
from afancontrol.temps import ObservedTempStatus
from afancontrol.trigger import Triggers

try:
    import prometheus_client as prom

    prometheus_available = True
except ImportError:
    prometheus_available = False


class Metrics(abc.ABC):
    @abc.abstractmethod
    def __enter__(self):
        pass

    @abc.abstractmethod
    def __exit__(self, exc_type, exc_value, exc_tb):
        pass

    @abc.abstractmethod
    def tick(
        self,
        temps: Mapping[TempName, ObservedTempStatus],
        fans: Fans,
        triggers: Triggers,
        arduino_connections: Mapping[ArduinoName, ArduinoConnection],
    ) -> None:
        pass

    @abc.abstractmethod
    def measure_tick(self) -> ContextManager[None]:
        pass


class NullMetrics(Metrics):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        pass

    def tick(
        self,
        temps: Mapping[TempName, ObservedTempStatus],
        fans: Fans,
        triggers: Triggers,
        arduino_connections: Mapping[ArduinoName, ArduinoConnection],
    ) -> None:
        pass

    def measure_tick(self) -> ContextManager[None]:
        @contextlib.contextmanager
        def null_context_manager():
            yield

        return null_context_manager()


class PrometheusMetrics(Metrics):
    def __init__(self, listen_host: str) -> None:
        if not prometheus_available:
            raise RuntimeError(
                "`prometheus_client` is not installed. "
                "Run `pip install 'afancontrol[metrics]'`."
            )

        self._listen_addr, port_str = listen_host.rsplit(":", 1)
        self._listen_port = int(port_str)

        self._http_server: Optional[HTTPServer] = None

        self._last_metrics_collect_clock = float("nan")

        # Create a separate registry for this instance instead of using
        # the default one (which is global and doesn't allow to instantiate
        # this class more than once due to having metrics below being
        # registered for a second time):
        self.registry = prom.CollectorRegistry(auto_describe=True)

        # Register some default prometheus_client metrics:
        prom.ProcessCollector(registry=self.registry)
        if hasattr(prom, "PlatformCollector"):
            prom.PlatformCollector(registry=self.registry)
        if hasattr(prom, "GCCollector"):
            prom.GCCollector(registry=self.registry)

        # Temps:
        self.temperature_is_failing = prom.Gauge(
            "temperature_is_failing",
            "The temperature sensor is failing (it isn't returning any data)",
            ["temp_name"],
            registry=self.registry,
        )
        self.temperature_current = prom.Gauge(
            "temperature_current",
            "The current (filtered) temperature value (in Celsius) "
            "from a temperature sensor",
            ["temp_name"],
            registry=self.registry,
        )
        self.temperature_min = prom.Gauge(
            "temperature_min",
            "The min temperature value (in Celsius) for a temperature sensor",
            ["temp_name"],
            registry=self.registry,
        )
        self.temperature_max = prom.Gauge(
            "temperature_max",
            "The max temperature value (in Celsius) for a temperature sensor",
            ["temp_name"],
            registry=self.registry,
        )
        self.temperature_panic = prom.Gauge(
            "temperature_panic",
            "The panic temperature value (in Celsius) for a temperature sensor",
            ["temp_name"],
            registry=self.registry,
        )
        self.temperature_threshold = prom.Gauge(
            "temperature_threshold",
            "The threshold temperature value (in Celsius) for a temperature sensor",
            ["temp_name"],
            registry=self.registry,
        )
        self.temperature_is_panic = prom.Gauge(
            "temperature_is_panic",
            "Is panic temperature reached for a temperature sensor",
            ["temp_name"],
            registry=self.registry,
        )
        self.temperature_is_threshold = prom.Gauge(
            "temperature_is_threshold",
            "Is threshold temperature reached for a temperature sensor",
            ["temp_name"],
            registry=self.registry,
        )

        self.temperature_current_raw = prom.Gauge(
            "temperature_current_raw",
            "The current (unfiltered) temperature value (in Celsius) "
            "from a temperature sensor",
            ["temp_name"],
            registry=self.registry,
        )

        # Fans:
        self.fan_rpm = prom.Gauge(
            "fan_rpm",
            "Fan speed (in RPM) as reported by the fan",
            ["fan_name"],
            registry=self.registry,
        )
        self.fan_pwm = prom.Gauge(
            "fan_pwm",
            "Current fan's PWM value (from 0 to 255)",
            ["fan_name"],
            registry=self.registry,
        )
        self.fan_pwm_normalized = prom.Gauge(
            "fan_pwm_normalized",
            "Current fan's normalized PWM value (from 0.0 to 1.0, within "
            "the `fan_pwm_line_start` and `fan_pwm_line_end` interval)",
            ["fan_name"],
            registry=self.registry,
        )
        self.fan_pwm_line_start = prom.Gauge(
            "fan_pwm_line_start",
            "PWM value where a linear correlation with RPM starts for the fan",
            ["fan_name"],
            registry=self.registry,
        )
        self.fan_pwm_line_end = prom.Gauge(
            "fan_pwm_line_end",
            "PWM value where a linear correlation with RPM ends for the fan",
            ["fan_name"],
            registry=self.registry,
        )
        self.fan_is_stopped = prom.Gauge(
            "fan_is_stopped",
            "Is PWM fan stopped because the corresponding temperatures "
            "are already low",
            ["fan_name"],
            registry=self.registry,
        )
        self.fan_is_failing = prom.Gauge(
            "fan_is_failing",
            "Is PWM fan marked as failing (e.g. because it has jammed)",
            ["fan_name"],
            registry=self.registry,
        )

        # Arduino boards:
        self.arduino_is_connected = prom.Gauge(
            "arduino_is_connected",
            "Is Arduino board connected via Serial",
            ["arduino_name"],
            registry=self.registry,
        )
        self.arduino_status_age_seconds = prom.Gauge(
            "arduino_status_age_seconds",
            "Seconds since the last `status` message from "
            "the Arduino board (measured at the latest tick)",
            ["arduino_name"],
            registry=self.registry,
        )

        # Others:
        self.is_panic = prom.Gauge(
            "is_panic", "Is in panic mode", registry=self.registry
        )
        self.is_threshold = prom.Gauge(
            "is_threshold", "Is in threshold mode", registry=self.registry
        )

        self.tick_duration = prom.Histogram(
            # Summary would have been better there, but prometheus_client
            # doesn't yet support quantiles in Summaries.
            # See: https://github.com/prometheus/client_python/issues/92
            "tick_duration",
            "Duration of a single tick",
            buckets=(0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 10.0, float("inf")),
            registry=self.registry,
        )
        last_metrics_tick_seconds_ago = prom.Gauge(
            "last_metrics_tick_seconds_ago",
            "The time in seconds since the last tick (which also updates these metrics)",
            registry=self.registry,
        )
        last_metrics_tick_seconds_ago.set_function(
            lambda: self.last_metrics_tick_seconds_ago
        )

    @property
    def last_metrics_tick_seconds_ago(self):
        return self._clock() - self._last_metrics_collect_clock

    def _start(self):
        # `prometheus_client.start_http_server` which persists a server reference
        # so it could be stopped later.
        CustomMetricsHandler = prom.MetricsHandler.factory(self.registry)
        httpd = _ThreadingSimpleServer(
            (self._listen_addr, self._listen_port), CustomMetricsHandler
        )
        t = threading.Thread(target=httpd.serve_forever)
        t.daemon = True
        t.start()
        return httpd

    def __enter__(self):
        self._http_server = self._start()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        assert self._http_server is not None
        self._http_server.shutdown()  # stop serve_forever()
        self._http_server.server_close()
        self._http_server = None
        return None

    def tick(
        self,
        temps: Mapping[TempName, ObservedTempStatus],
        fans: Fans,
        triggers: Triggers,
        arduino_connections: Mapping[ArduinoName, ArduinoConnection],
    ) -> None:
        for temp_name, observed_temp_status in temps.items():
            temp_status = observed_temp_status.filtered
            if temp_status is None:
                self.temperature_is_failing.labels(temp_name).set(1)
                self.temperature_current.labels(temp_name).set(none_to_nan(None))
                self.temperature_min.labels(temp_name).set(none_to_nan(None))
                self.temperature_max.labels(temp_name).set(none_to_nan(None))
                self.temperature_panic.labels(temp_name).set(none_to_nan(None))
                self.temperature_threshold.labels(temp_name).set(none_to_nan(None))
                self.temperature_is_panic.labels(temp_name).set(none_to_nan(None))
                self.temperature_is_threshold.labels(temp_name).set(none_to_nan(None))
            else:
                self.temperature_is_failing.labels(temp_name).set(0)
                self.temperature_current.labels(temp_name).set(temp_status.temp)
                self.temperature_min.labels(temp_name).set(temp_status.min)
                self.temperature_max.labels(temp_name).set(temp_status.max)
                self.temperature_panic.labels(temp_name).set(
                    none_to_nan(temp_status.panic)
                )
                self.temperature_threshold.labels(temp_name).set(
                    none_to_nan(temp_status.threshold)
                )
                self.temperature_is_panic.labels(temp_name).set(temp_status.is_panic)
                self.temperature_is_threshold.labels(temp_name).set(
                    temp_status.is_threshold
                )

            temp_status = observed_temp_status.raw
            if temp_status is None:
                self.temperature_current_raw.labels(temp_name).set(none_to_nan(None))
            else:
                self.temperature_current_raw.labels(temp_name).set(temp_status.temp)

        for fan_name, pwmfan_norm in fans.fans.items():
            self._collect_fan_metrics(fans, fan_name, pwmfan_norm)
        for readonly_fan_name, readonly_pwmfan_norm in fans.readonly_fans.items():
            self._collect_readonly_fan_metrics(
                fans, readonly_fan_name, readonly_pwmfan_norm
            )

        for arduino_name, arduino_connection in arduino_connections.items():
            self.arduino_is_connected.labels(arduino_name).set(
                arduino_connection.is_connected
            )
            self.arduino_status_age_seconds.labels(arduino_name).set(
                arduino_connection.status_age_seconds
            )

        self.is_panic.set(triggers.panic_trigger.is_alerting)
        self.is_threshold.set(triggers.threshold_trigger.is_alerting)

        self._last_metrics_collect_clock = self._clock()

    def measure_tick(self) -> ContextManager[None]:
        return self.tick_duration.time()

    def _collect_fan_metrics(
        self, fans: Fans, fan_name: FanName, pwm_fan_norm: PWMFanNorm
    ):
        self.fan_pwm_line_start.labels(fan_name).set(pwm_fan_norm.pwm_line_start)
        self.fan_pwm_line_end.labels(fan_name).set(pwm_fan_norm.pwm_line_end)
        self._collect_any_fan_metrics(fans, fan_name, pwm_fan_norm)

    def _collect_readonly_fan_metrics(
        self, fans: Fans, fan_name: ReadonlyFanName, pwm_fan_norm: ReadonlyPWMFanNorm
    ):
        self._collect_any_fan_metrics(fans, fan_name, pwm_fan_norm)

    def _collect_any_fan_metrics(
        self,
        fans: Fans,
        fan_name: AnyFanName,
        pwm_fan_norm: Union[PWMFanNorm, ReadonlyPWMFanNorm],
    ):
        self.fan_is_stopped.labels(fan_name).set(fans.is_fan_stopped(fan_name))
        self.fan_is_failing.labels(fan_name).set(fans.is_fan_failing(fan_name))
        try:
            self.fan_rpm.labels(fan_name).set(pwm_fan_norm.get_speed())
            self.fan_pwm.labels(fan_name).set(none_to_nan(pwm_fan_norm.get_raw()))
            self.fan_pwm_normalized.labels(fan_name).set(
                none_to_nan(pwm_fan_norm.get())
            )
        except Exception:
            logger.warning(
                "Failed to collect metrics for fan %s", fan_name, exc_info=True
            )
            self.fan_rpm.labels(fan_name).set(none_to_nan(None))
            self.fan_pwm.labels(fan_name).set(none_to_nan(None))
            self.fan_pwm_normalized.labels(fan_name).set(none_to_nan(None))

    def _clock(self):
        return default_timer()


def none_to_nan(v: Optional[float]) -> float:
    if v is None:
        return float("nan")
    return v


class _ThreadingSimpleServer(ThreadingMixIn, HTTPServer):
    """Thread per request HTTP server."""

    # https://github.com/prometheus/client_python/blob/31f5557e2e84ca4ffa9a03abf6e3f4d0c8b8c3eb/prometheus_client/exposition.py#L180-L187  # noqa
    #
    # Make worker threads "fire and forget". Beginning with Python 3.7 this
    # prevents a memory leak because ``ThreadingMixIn`` starts to gather all
    # non-daemon threads in a list in order to join on them at server close.
    # Enabling daemon threads virtually makes ``_ThreadingSimpleServer`` the
    # same as Python 3.7's ``ThreadingHTTPServer``.
    daemon_threads = True
