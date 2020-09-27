import subprocess
from unittest.mock import patch

import pytest

from afancontrol.temp import HDDTemp, TempCelsius, TempStatus


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
