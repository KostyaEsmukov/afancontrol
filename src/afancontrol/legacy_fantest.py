#!/usr/bin/env python3
"""
    afancontrol_fantest - Test suit for your PWM fan.

    This program lets you test your PWM fans.
    Using output data you might build charts and choose proper settings for afancontrol config.

    Depends: lm_sensors

    Copyright 2013 Kostya Esmukov <kostya.shift@gmail.com>

    This file is part of afancontrol.

    afancontrol is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    afancontrol is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with afancontrol.  If not, see <http://www.gnu.org/licenses/>.

"""

import os
import sys
from sys import exit
from time import sleep

RESET_INTERVAL = 7


class afancontrol_pwmfan:
    """
    PWM fan methods
    """

    MAX_PWM = 255
    MIN_PWM = 0
    STOP_PWM = 0

    def __init__(self, fan_data):
        self._pwm = fan_data["pwm"]
        self._fan_input = fan_data["fan_input"]

    def _write(self, filepath, contents):
        h = open(filepath, mode="wt")
        h.write(contents)
        h.close()

    def _read(self, filepath):
        h = open(filepath, mode="rt")
        t = h.read().strip()
        h.close()
        return t

    def get(self):
        """Get current PWM value"""
        return int(self._read(self._pwm))

    def set(self, pwm):
        """Set current PWM value (range 0~255)"""
        self._write(self._pwm, str(int(pwm)))

    def setFullSpeed(self):
        self.set(self.MAX_PWM)

    def enable(self):
        """Enable PWM control for this fan"""
        # fancontrol way of doing it
        if os.path.isfile(self._pwm + "_enable"):
            self._write(self._pwm + "_enable", "1")
        self._write(self._pwm, str(self.MAX_PWM))

    def disable(self):
        """Disable PWM control for this fan"""
        # fancontrol way of doing it
        pwm_enable = self._pwm + "_enable"
        if not os.path.isfile(pwm_enable):
            self._write(self._pwm, str(self.MAX_PWM))
            return

        self._write(pwm_enable, "0")
        if self._read(pwm_enable) == "0":
            return

        self._write(pwm_enable, "1")
        self._write(self._pwm, str(self.MAX_PWM))

        if (
            self._read(pwm_enable) == "1" and int(self._read(self._pwm)) == self.MAX_PWM
        ):  # >= 190
            return

        raise Exception("Out of luck disabling PWM on that fan.")

    def getSpeed(self):
        """Get current RPM for this fan"""
        return int(self._read(self._fan_input))


class afancontrol_fantest:
    def __init__(self, step, interval, pwm, fan_input, outf, desctest):
        self._step = step
        self._interval = interval
        self._i = afancontrol_pwmfan({"pwm": pwm, "fan_input": fan_input})
        self._outf = outf
        self._desctest = desctest

    def test(self):
        self._i.enable()
        if self._desctest:
            print("Testing descrease with step %s. Please be patient." % self._step)
            self._test(255, (-1) * self._step, True)
            print("Descrease test done.")

        print("Testing increase with step %s. Please be patient." % self._step)
        self._test(0, self._step, False)
        print("Increase test done.")
        self._i.disable()

    def interrupt(self):
        self._i.disable()
        print("Fan have been successfully set to full speed")

    def _test(self, st, step, stop):
        intr = RESET_INTERVAL
        prev = None
        while True:
            if st < 0:
                st = 0
            if st > 255:
                st = 255

            self._i.set(st)
            sleep(intr)
            intr = self._interval
            s = self._i.getSpeed()
            self._print_test(str(st), str(s), "n/a" if prev == None else str(s - prev))
            if stop and (s <= 0):
                break

            if stop and (st == 0):
                break
            if (not stop) and (st == 255):
                break

            prev = s
            st += step

    def _print_test(self, pwm, speed, delta):
        if self._outf == "human":
            print(
                "PWM %s RPM %s DELTA %s"
                % (pwm.rjust(3), speed.rjust(4), delta.rjust(4))
            )
        elif self._outf == "csv":
            print("%s;%s;%s" % (pwm, speed, delta))


def read_stdin(prompt, values=None, default=None):
    if values == None:
        v = ""
    else:
        v = " (%s)" % ", ".join(values)

    if default == None:
        d = ""
    else:
        d = " [%s]" % default

    p = "%s%s%s: " % (prompt, v, d)

    while True:
        r = input(p)

        if r == "":
            if default != None:
                r = default
            else:
                continue

        if values == None:
            break
        else:
            if r in values:
                break

    return r


def main():
    print("This program tests control of your PWM fan")
    print("Using output of this program you can examine your fan")
    print(
        "If you want to make a chart, select csv output format in questions below and put csv data in MS Excel, LibreOffice Spreadsheet, etc."
    )
    print("")
    print("Keep in mind that your fan is going to be stopped for some time")
    print("If you'll fill nervous, press Ctrl+C and your fan will run full speed again")
    print("")
    print(
        "Please make sure that all fan controlling software is not affecting this fan"
    )
    print("")

    try:
        pwm = read_stdin("PWM file of the fan")
        fan_input = read_stdin("fan_input file of the fan")
        outf = read_stdin("Output format", ["human", "csv"], "human")
        dt = read_stdin(
            "Do you want to test speed descrease? Usually this doesn't makes sense.",
            ["y", "n"],
            "n",
        )
        qd = read_stdin(
            "Quick and dirty (q) or slow and accurate (s)?", ["q", "s"], "s"
        )
    except KeyboardInterrupt:
        print("")
        exit(130)

    if qd == "q":
        step = 25
    else:
        step = 5

    aft = afancontrol_fantest(step, 2, pwm, fan_input, outf, (dt == "y"))
    try:
        aft.test()
    except Exception as ex:
        print("Failed: %s" % ex, file=sys.stderr)
    except KeyboardInterrupt:
        aft.interrupt()
        exit(130)


if __name__ == "__main__":
    main()