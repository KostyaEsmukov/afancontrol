from afancontrol.temp import CommandTemp, TempCelsius, TempStatus


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
