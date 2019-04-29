import subprocess
from typing import Optional
from unittest.mock import patch

import pytest

from afancontrol.temp import (
    CommandTemp,
    FileTemp,
    HDDTemp,
    Temp,
    TempCelsius,
    TempStatus,
)


@pytest.fixture
def file_temp_path(temp_path):
    # /sys/class/hwmon/hwmon0/temp1_input
    temp_input_path = temp_path / "temp1_input"
    temp_input_path.write_text("34000\n")

    temp_max_path = temp_path / "temp1_max"
    temp_max_path.write_text("127000\n")

    temp_min_path = temp_path / "temp1_min"
    # My mobo actually returns this as min:
    temp_min_path.write_text("127000\n")

    return temp_input_path


@pytest.fixture
def hddtemp_output_many():
    return (
        "/dev/sda: Adaptec XXXXX:  drive supported,"
        " but it doesn't have a temperature sensor.\n"
        "/dev/sdb: Adaptec XXXXX:  drive supported,"
        " but it doesn't have a temperature sensor.\n"
        "38\n"
        "39\n"
        "30\n"
        "36\n"
    )


@pytest.fixture
def hddtemp_output_bad():
    return (
        "/dev/sda: Adaptec XXXXX:  drive supported,"
        " but it doesn't have a temperature sensor.\n"
    )


class DummyTemp(Temp):
    def _get_temp(self):
        pass


@pytest.mark.parametrize(
    "temp, threshold, panic, is_threshold, is_panic",
    [
        (34.0, None, 60.0, False, False),
        (42.0, None, 60.0, False, False),
        (57.0, 55.0, 60.0, True, False),
        (61.0, 55.0, 61.0, True, True),
        (61.0, None, 61.0, False, True),
    ],
)
def test_temp(
    temp: TempCelsius,
    threshold: Optional[TempCelsius],
    panic: TempCelsius,
    is_threshold,
    is_panic,
):
    min = TempCelsius(40.0)
    max = TempCelsius(50.0)

    with patch.object(DummyTemp, "_get_temp") as mock_get_temp:
        t = DummyTemp(panic=panic, threshold=threshold)
        mock_get_temp.return_value = [temp, min, max]

        assert t.get() == TempStatus(
            temp=temp,
            min=min,
            max=max,
            panic=panic,
            threshold=threshold,
            is_panic=is_panic,
            is_threshold=is_threshold,
        )


def test_file_temp_min_max_numbers(file_temp_path):
    temp = FileTemp(
        temp_path=str(file_temp_path),
        min=TempCelsius(40.0),
        max=TempCelsius(50.0),
        panic=TempCelsius(60.0),
        threshold=None,
    )
    assert temp.get() == TempStatus(
        temp=TempCelsius(34.0),
        min=TempCelsius(40.0),
        max=TempCelsius(50.0),
        panic=TempCelsius(60.0),
        threshold=None,
        is_panic=False,
        is_threshold=False,
    )
    print(repr(temp))


def test_file_temp_min_max_files(temp_path, file_temp_path):
    with pytest.raises(RuntimeError):
        # min == max is an error
        FileTemp(
            temp_path=str(file_temp_path),
            min=None,
            max=None,
            panic=TempCelsius(60.0),
            threshold=None,
        ).get()

    temp = FileTemp(
        temp_path=str(file_temp_path),
        min=TempCelsius(50.0),
        max=None,
        panic=TempCelsius(60.0),
        threshold=None,
    )
    assert temp.get() == TempStatus(
        temp=TempCelsius(34.0),
        min=TempCelsius(50.0),
        max=TempCelsius(127.0),
        panic=TempCelsius(60.0),
        threshold=None,
        is_panic=False,
        is_threshold=False,
    )


def test_hddtemp_many(hddtemp_output_many):
    with patch.object(HDDTemp, "_call_hddtemp") as mock_call_hddtemp:
        mock_call_hddtemp.return_value = hddtemp_output_many
        t = HDDTemp(
            disk_path="/dev/sd?",
            min=TempCelsius(38.0),
            max=TempCelsius(45.0),
            panic=TempCelsius(50.0),
            threshold=None,
            hddtemp_bin="testbin",
        )

        assert t.get() == TempStatus(
            temp=TempCelsius(39.0),
            min=TempCelsius(38.0),
            max=TempCelsius(45.0),
            panic=TempCelsius(50.0),
            threshold=None,
            is_panic=False,
            is_threshold=False,
        )
        print(repr(t))


def test_hddtemp_bad(hddtemp_output_bad):
    with patch.object(HDDTemp, "_call_hddtemp") as mock_call_hddtemp:
        mock_call_hddtemp.return_value = hddtemp_output_bad
        t = HDDTemp(
            disk_path="/dev/sda",
            min=TempCelsius(38.0),
            max=TempCelsius(45.0),
            panic=TempCelsius(50.0),
            threshold=None,
            hddtemp_bin="testbin",
        )
        with pytest.raises(RuntimeError):
            t.get()


def test_hddtemp_exec_successful(temp_path):
    (temp_path / "sda").write_text("")
    (temp_path / "sdz").write_text("")
    t = HDDTemp(
        disk_path=str(temp_path / "sd") + "?",
        min=TempCelsius(38.0),
        max=TempCelsius(45.0),
        panic=TempCelsius(50.0),
        threshold=None,
        hddtemp_bin="printf '@%s'",
    )
    expected_out = "@-n@-u@C@--@{0}/sda@{0}/sdz".format(temp_path)
    assert expected_out == t._call_hddtemp()


def test_hddtemp_exec_failed():
    t = HDDTemp(
        disk_path="/dev/sd?",
        min=TempCelsius(38.0),
        max=TempCelsius(45.0),
        panic=TempCelsius(50.0),
        threshold=None,
        hddtemp_bin="false",
    )
    with pytest.raises(subprocess.CalledProcessError):
        t._call_hddtemp()


def test_command_temp_with_minmax():
    t = CommandTemp(
        shell_command=r"printf '%s\n' 35 30 40",
        min=TempCelsius(31.0),
        max=TempCelsius(39.0),
        panic=TempCelsius(50.0),
        threshold=None,
    )
    assert t.get() == TempStatus(
        temp=TempCelsius(35.0),
        min=TempCelsius(31.0),
        max=TempCelsius(39.0),
        panic=TempCelsius(50.0),
        threshold=None,
        is_panic=False,
        is_threshold=False,
    )
    print(repr(t))


def test_command_temp_without_minmax():
    t = CommandTemp(
        shell_command=r"printf '%s\n' 35 30 40",
        min=None,
        max=None,
        panic=TempCelsius(50.0),
        threshold=None,
    )
    assert t.get() == TempStatus(
        temp=TempCelsius(35.0),
        min=TempCelsius(30.0),
        max=TempCelsius(40.0),
        panic=TempCelsius(50.0),
        threshold=None,
        is_panic=False,
        is_threshold=False,
    )
