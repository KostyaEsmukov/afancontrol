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


@pytest.mark.parametrize("aggregation", ["avg", "median"])
def test_hddtemp_nonfinite(aggregation):
    temp = HDDTemp(
        disk_path="/dev/sd?",
        min=TempCelsius(30.0),
        max=TempCelsius(70.0),
        panic=TempCelsius(60.0),
        threshold=TempCelsius(55.0),
        aggregation=aggregation,
    )
    with patch.object(HDDTemp, "_call_hddtemp", return_value="65\nnan\ninf\n-inf\n"):
        status = temp.get()
        assert status.temp == TempCelsius(65.0)
        assert status.is_panic
        assert status.is_threshold

    with patch.object(HDDTemp, "_call_hddtemp", return_value="nan\ninf\n-inf\n"):
        with pytest.raises(
            RuntimeError, match="empty list of valid temperature values"
        ):
            temp.get()


@pytest.mark.parametrize(
    "aggregation, expected",
    [
        ("max", 39.0),
        ("min", 30.0),
        ("avg", 35.75),
        ("median", 37.0),
    ],
)
def test_hddtemp_aggregation(hddtemp_output_many, aggregation, expected):
    with patch.object(HDDTemp, "_call_hddtemp") as mock_call_hddtemp:
        mock_call_hddtemp.return_value = hddtemp_output_many
        t = HDDTemp(
            disk_path="/dev/sd?",
            min=TempCelsius(38.0),
            max=TempCelsius(45.0),
            panic=TempCelsius(50.0),
            threshold=None,
            hddtemp_bin="testbin",
            aggregation=aggregation,
        )

        assert t.get().temp == TempCelsius(expected)
        print(repr(t))


def test_hddtemp_aggregation_bad_value(hddtemp_output_many):
    with patch.object(HDDTemp, "_call_hddtemp") as mock_call_hddtemp:
        mock_call_hddtemp.return_value = hddtemp_output_many
        with pytest.raises(ValueError):
            HDDTemp(
                disk_path="/dev/sd?",
                min=TempCelsius(38.0),
                max=TempCelsius(45.0),
                panic=TempCelsius(50.0),
                threshold=None,
                hddtemp_bin="testbin",
                aggregation="bogus",
            )


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
