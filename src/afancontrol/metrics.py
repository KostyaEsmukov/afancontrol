import abc
import threading
from http.server import HTTPServer
from socketserver import ThreadingMixIn
from typing import ContextManager, Mapping, Optional

from .config import TempName
from .manager.fans import Fans
from .manager.trigger import Triggers
from .temp import TempStatus

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
        temps: Mapping[TempName, Optional[TempStatus]],
        fans: Fans,
        triggers: Triggers,
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
        temps: Mapping[TempName, Optional[TempStatus]],
        fans: Fans,
        triggers: Triggers,
    ) -> None:
        pass

    def measure_tick(self) -> ContextManager[None]:
        pass


class PrometheusMetrics(Metrics):
    def __init__(self, listen_host: str) -> None:
        if not prometheus_available:
            raise RuntimeError(
                "`prometheus_client` is not installed. "
                "Run `pip install 'afancontrol[metrics]'`."
            )

        self._listen_addr, port_str = listen_host.rsplit(":", 1)
        self._listen_port = int(port_str)

        self._http_server = None  # type: Optional[HTTPServer]

        self.temperature_is_failing = prom.Gauge(
            "temperature_is_failing",
            "The temperature sensor is failing (it isn't returning data)",
            ["temp_name"],
        )
        self.temperature_current = prom.Gauge(
            "temperature_current",
            "The current temperature value (in celsius) from a `temp` sensor",
            ["temp_name"],
        )
        self.temperature_min = prom.Gauge(
            "temperature_min",
            "The min temperature value (in celsius) for a `temp` sensor",
            ["temp_name"],
        )
        self.temperature_max = prom.Gauge(
            "temperature_max",
            "The max temperature value (in celsius) for a `temp` sensor",
            ["temp_name"],
        )
        self.temperature_panic = prom.Gauge(
            "temperature_panic",
            "The panic temperature value (in celsius) for a `temp` sensor",
            ["temp_name"],
        )
        self.temperature_threshold = prom.Gauge(
            "temperature_threshold",
            "The panic temperature value (in celsius) for a `temp` sensor",
            ["temp_name"],
        )
        self.temperature_is_panic = prom.Gauge(
            "temperature_is_panic",
            "Is panic temperature reached for a `temp` sensor",
            ["temp_name"],
        )
        self.temperature_is_threshold = prom.Gauge(
            "temperature_is_threshold",
            "Is threshold temperature reached for a `temp` sensor",
            ["temp_name"],
        )

        self.fan_rpm = prom.Gauge(
            "fan_rpm", "Fan speed (RPM) as reported by the fan", ["fan_name"]
        )
        self.fan_pwm = prom.Gauge(
            "fan_pwm", "Current fan PWM value (from 0 to 255)", ["fan_name"]
        )
        self.fan_pwm_line_start = prom.Gauge(
            "fan_pwm_line_start",
            "PWM value where a linear correlation with RPM starts for the fan",
            ["fan_name"],
        )
        self.fan_pwm_line_end = prom.Gauge(
            "fan_pwm_line_end",
            "PWM value where a linear correlation with RPM ends for the fan",
            ["fan_name"],
        )
        self.fan_is_stopped = prom.Gauge(
            "fan_is_stopped",
            "PWM fan has been stopped because the corresponding temperatures "
            "are already low",
            ["fan_name"],
        )
        self.fan_is_failing = prom.Gauge(
            "fan_is_failing",
            "PWM fan has been marked as failing (e.g. because if jammed)",
            ["fan_name"],
        )

        self.is_panic = prom.Gauge("is_panic", "Is in panic mode")
        self.is_threshold = prom.Gauge("is_threshold", "Is in threshold mode")

        self.tick_duration = prom.Summary("tick_duration", "Duration of a single tick")

    def _start(self):
        # `prometheus_client.start_http_server` which persists a server reference
        # so it could be stopped later.
        CustomMetricsHandler = prom.MetricsHandler.factory(prom.REGISTRY)
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
        self._http_server.shutdown()  # stop serve_forever()
        self._http_server.server_close()
        self._http_server = None
        return None

    def tick(
        self,
        temps: Mapping[TempName, Optional[TempStatus]],
        fans: Fans,
        triggers: Triggers,
    ) -> None:
        for temp_name, temp_status in temps.items():
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

        for fan_name, pwm_fan_norm in fans.fans.items():
            self.fan_rpm.labels(fan_name).set(pwm_fan_norm.get_speed())
            self.fan_pwm.labels(fan_name).set(pwm_fan_norm.get_raw())
            self.fan_pwm_line_start.labels(fan_name).set(pwm_fan_norm.pwm_line_start)
            self.fan_pwm_line_end.labels(fan_name).set(pwm_fan_norm.pwm_line_end)
            self.fan_is_stopped.labels(fan_name).set(fans.is_fan_stopped(fan_name))
            self.fan_is_failing.labels(fan_name).set(fans.is_fan_failing(fan_name))

        self.is_panic.set(triggers.panic_trigger.is_alerting)
        self.is_threshold.set(triggers.threshold_trigger.is_alerting)

    def measure_tick(self) -> ContextManager[None]:
        return self.tick_duration.time()


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