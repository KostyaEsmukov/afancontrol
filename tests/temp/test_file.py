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


@pytest.fixture
def file_temp_many_path(temp_path):
    # e.g. /sys/class/hwmon/hwmon*/temp?_input — three files
    # (also matched by the `temp?` glob via the `_input` fallback)
    (temp_path / "temp1_input").write_text("34000\n")
    (temp_path / "temp2_input").write_text("39000\n")
    (temp_path / "temp3_input").write_text("30000\n")
    return temp_path


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


@pytest.mark.parametrize("pattern", ["temp?_input", "temp*", "temp?_inpu[t]"])
def test_file_temp_glob(file_temp_path, pattern):
    temp = FileTemp(
        temp_path=str(file_temp_path.with_name(pattern)),
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
    with pytest.raises(ValueError, match="Min temperature must be less than max"):
        # min == max is an error
        FileTemp(
            temp_path=str(file_temp_path),
            min=None,
            max=None,
            panic=TempCelsius(60.0),
            threshold=None,
        )

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


def test_file_temp_single_input_resolves_bounds_at_startup(tmp_path):
    input_path = tmp_path / "temp1_input"
    min_path = tmp_path / "temp1_min"
    max_path = tmp_path / "temp1_max"
    input_path.write_text("34000\n")
    with pytest.raises(
        RuntimeError, match="Please specify `min` and `max` temperatures"
    ):
        FileTemp(str(input_path), min=None, max=None, panic=None, threshold=None)

    min_path.write_text("20000\n")
    max_path.write_text("50000\n")
    temp = FileTemp(str(input_path), min=None, max=None, panic=None, threshold=None)

    min_path.unlink()
    max_path.write_text("60000\n")
    status = temp.get()
    assert (status.min, status.max) == (20.0, 50.0)


@pytest.mark.parametrize(
    "aggregation, expected",
    [
        ("max", 39.0),
        ("min", 30.0),
        ("avg", (34.0 + 39.0 + 30.0) / 3),
        ("median", 34.0),
    ],
)
def test_file_temp_aggregation(file_temp_many_path, aggregation, expected):
    temp = FileTemp(
        temp_path=str(file_temp_many_path / "temp?_input"),
        min=TempCelsius(40.0),
        max=TempCelsius(50.0),
        panic=None,
        threshold=None,
        aggregation=aggregation,
    )
    assert temp.get() == TempStatus(
        temp=TempCelsius(expected),
        min=TempCelsius(40.0),
        max=TempCelsius(50.0),
        panic=None,
        threshold=None,
        is_panic=False,
        is_threshold=False,
    )
    print(repr(temp))


def test_file_temp_default_aggregation(file_temp_many_path):
    temp = FileTemp(
        temp_path=str(file_temp_many_path / "temp?"),
        min=TempCelsius(30.0),
        max=TempCelsius(50.0),
        panic=None,
        threshold=None,
    )
    assert temp.get().temp == TempCelsius(39.0)


def test_file_temp_aggregation_config_min_max_override(temp_path):
    (temp_path / "temp1_input").write_text("34000\n")
    (temp_path / "temp1_min").write_text("20000\n")
    (temp_path / "temp1_max").write_text("120000\n")
    (temp_path / "temp2_input").write_text("39000\n")
    (temp_path / "temp2_min").write_text("15000\n")
    (temp_path / "temp2_max").write_text("130000\n")
    temp = FileTemp(
        temp_path=str(temp_path / "temp?"),
        min=TempCelsius(40.0),
        max=TempCelsius(50.0),
        panic=None,
        threshold=None,
        aggregation="max",
    )
    status = temp.get()
    assert status.min == TempCelsius(40.0)
    assert status.max == TempCelsius(50.0)


def test_file_temp_aggregation_min_max_resolved_once(temp_path):
    (temp_path / "temp1_input").write_text("34000\n")
    (temp_path / "temp1_min").write_text("20000\n")
    (temp_path / "temp1_max").write_text("120000\n")
    (temp_path / "temp2_input").write_text("39000\n")
    (temp_path / "temp2_min").write_text("15000\n")
    (temp_path / "temp2_max").write_text("110000\n")
    temp = FileTemp(
        temp_path=str(temp_path / "temp?"),
        min=None,
        max=None,
        panic=None,
        threshold=None,
        aggregation="max",
    )
    # The bounds were already resolved at construction time, so
    # removing the min/max files does not affect the observations.
    (temp_path / "temp1_min").unlink()
    (temp_path / "temp2_max").unlink()
    assert temp.get() == TempStatus(
        temp=TempCelsius(39.0),
        min=TempCelsius(20.0),
        max=TempCelsius(110.0),
        panic=None,
        threshold=None,
        is_panic=False,
        is_threshold=False,
    )


@pytest.mark.parametrize("missing_bound", ["min", "max"])
def test_file_temp_aggregation_missing_bound_file(temp_path, missing_bound):
    (temp_path / "temp1_input").write_text("34000\n")
    (temp_path / "temp1_min").write_text("20000\n")
    (temp_path / "temp1_max").write_text("120000\n")
    (temp_path / "temp2_input").write_text("39000\n")
    (temp_path / "temp2_min").write_text("15000\n")
    (temp_path / "temp2_max").write_text("130000\n")
    (temp_path / f"temp1_{missing_bound}").unlink()
    with pytest.raises(RuntimeError):
        FileTemp(
            temp_path=str(temp_path / "temp?"),
            min=None,
            max=None,
            panic=None,
            threshold=None,
            aggregation="max",
        )


def test_file_temp_aggregation_missing_input(temp_path):
    (temp_path / "temp1_input").write_text("34000\n")
    (temp_path / "temp2_input").write_text("39000\n")
    temp = FileTemp(
        temp_path=str(temp_path / "temp?"),
        min=TempCelsius(30.0),
        max=TempCelsius(60.0),
        panic=None,
        threshold=None,
        aggregation="max",
    )
    (temp_path / "temp1_input").unlink()
    with pytest.raises(FileNotFoundError):
        temp.get()


def test_file_temp_aggregation_non_numeric_input(temp_path):
    (temp_path / "temp1_input").write_text("34000\n")
    (temp_path / "temp2_input").write_text("N/A\n")
    temp = FileTemp(
        temp_path=str(temp_path / "temp?"),
        min=TempCelsius(30.0),
        max=TempCelsius(60.0),
        panic=None,
        threshold=None,
        aggregation="max",
    )
    with pytest.raises(ValueError):
        temp.get()


@pytest.mark.parametrize("base_exists", [False, True])
def test_file_temp_hwmon_base_name(temp_path, base_exists):
    base_path = temp_path / "temp1"
    if base_exists:
        base_path.write_text("25000\n")
    input_path = temp_path / "temp1_input"
    input_path.write_text("34000\n")
    temp = FileTemp(
        temp_path=str(base_path),
        min=TempCelsius(40.0),
        max=TempCelsius(50.0),
        panic=None,
        threshold=None,
    )
    assert temp == FileTemp(
        temp_path=str(input_path),
        min=TempCelsius(40.0),
        max=TempCelsius(50.0),
        panic=None,
        threshold=None,
    )
    assert temp.get() == TempStatus(
        temp=TempCelsius(34.0),
        min=TempCelsius(40.0),
        max=TempCelsius(50.0),
        panic=None,
        threshold=None,
        is_panic=False,
        is_threshold=False,
    )


def test_file_temp_path_without_input_suffix(temp_path):
    # A path which doesn't end with `_input` and matches an existing file
    # is the temperature file itself.
    (temp_path / "temperature").write_text("34000\n")
    temp = FileTemp(
        temp_path=str(temp_path / "temperature"),
        min=TempCelsius(40.0),
        max=TempCelsius(50.0),
        panic=None,
        threshold=None,
    )
    assert temp.get() == TempStatus(
        temp=TempCelsius(34.0),
        min=TempCelsius(40.0),
        max=TempCelsius(50.0),
        panic=None,
        threshold=None,
        is_panic=False,
        is_threshold=False,
    )
    print(repr(temp))


def test_file_temp_path_without_input_suffix_missing_min_max(temp_path):
    # The `*_min`/`*_max` files can't be derived from such a path,
    # so the `min` and `max` temperatures must be specified.
    (temp_path / "temperature").write_text("34000\n")
    with pytest.raises(RuntimeError):
        FileTemp(
            temp_path=str(temp_path / "temperature"),
            min=None,
            max=None,
            panic=None,
            threshold=None,
        )


def test_file_temp_path_without_input_suffix_aggregation(temp_path):
    (temp_path / "temperature1").write_text("34000\n")
    (temp_path / "temperature2").write_text("39000\n")
    (temp_path / "temperature3").write_text("30000\n")
    (temp_path / "temperature4").mkdir()
    temp = FileTemp(
        temp_path=str(temp_path / "temperature?"),
        min=TempCelsius(40.0),
        max=TempCelsius(50.0),
        panic=None,
        threshold=None,
        aggregation="max",
    )
    assert temp.get() == TempStatus(
        temp=TempCelsius(39.0),
        min=TempCelsius(40.0),
        max=TempCelsius(50.0),
        panic=None,
        threshold=None,
        is_panic=False,
        is_threshold=False,
    )
    print(repr(temp))
