import pytest

from afancontrol.temp import FileTemp, TempCelsius, TempStatus


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


def test_file_temp_glob(file_temp_path):
    temp = FileTemp(
        temp_path=str(file_temp_path).replace("/temp1", "/temp?"),
        min=TempCelsius(40.0),
        max=None,
        panic=None,
        threshold=None,
    )
    assert temp.get() == TempStatus(
        temp=TempCelsius(34.0),
        min=TempCelsius(40.0),
        max=TempCelsius(127.0),
        panic=None,
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
