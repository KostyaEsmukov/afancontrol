from afancontrol.arduino import ArduinoConnection, ArduinoPin
from afancontrol.pwmfan.base import BasePWMFan, FanValue, PWMValue


class ArduinoPWMFan(BasePWMFan):
    def __init__(
        self,
        arduino_connection: ArduinoConnection,
        *,
        pwm_pin: ArduinoPin,
        tacho_pin: ArduinoPin
    ) -> None:
        super().__init__()
        self._conn = arduino_connection
        self._pwm_pin = pwm_pin
        self._tacho_pin = tacho_pin

    def get(self) -> PWMValue:
        return PWMValue(int(self._conn.get_pwm(self._pwm_pin)))

    def _set_raw(self, pwm: PWMValue) -> None:
        self._conn.set_pwm(self._pwm_pin, pwm)

    def get_speed(self) -> FanValue:
        return FanValue(self._conn.get_rpm(self._tacho_pin))

    def __enter__(self):  # reusable
        self._conn.__enter__()
        super().__enter__()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        try:
            super().__exit__(exc_type, exc_value, exc_tb)
        finally:
            self._conn.__exit__(exc_type, exc_value, exc_tb)

    def _enable_pwm(self) -> None:
        self.set_full_speed()

    def _disable_pwm(self) -> None:
        self.set_full_speed()
        self._conn.wait_for_status()

        if self.get() >= type(self).max_pwm:
            return

        raise RuntimeError("Couldn't disable PWM on the fan %r" % self)

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return (
                self._conn == other._conn
                and self._pwm_pin == other._pwm_pin
                and self._tacho_pin == other._tacho_pin
            )

        return NotImplemented

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return "%s(%r, pwm_pin=%r, tacho_pin=%r)" % (
            type(self).__name__,
            self._conn,
            self._pwm_pin,
            self._tacho_pin,
        )
