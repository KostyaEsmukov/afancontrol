import configparser
from pathlib import Path
from typing import (
    Dict,
    Mapping,
    NamedTuple,
    NewType,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
)

from afancontrol.arduino import (
    DEFAULT_BAUDRATE,
    DEFAULT_STATUS_TTL,
    ArduinoConnection,
    ArduinoName,
    ArduinoPin,
    ArduinoPWMFan,
)
from afancontrol.pwmfan import (
    BasePWMFan,
    FanInputDevice,
    LinuxPWMFan,
    PWMDevice,
    PWMFanNorm,
    PWMValue,
)
from afancontrol.temp import CommandTemp, FileTemp, HDDTemp, Temp, TempCelsius

DEFAULT_CONFIG = "/etc/afancontrol/afancontrol.conf"
DEFAULT_PIDFILE = "/var/run/afancontrol.pid"
DEFAULT_INTERVAL = 5
DEFAULT_FANS_SPEED_CHECK_INTERVAL = 3
DEFAULT_HDDTEMP = "hddtemp"
DEFAULT_REPORT_CMD = (
    'printf "Subject: %s\nTo: %s\n\n%b"'
    ' "afancontrol daemon report: %REASON%" root "%MESSAGE%"'
    " | sendmail -t"
)

DEFAULT_FAN_TYPE = "linux"
DEFAULT_PWM_LINE_START = 100
DEFAULT_PWM_LINE_END = 240

DEFAULT_NEVER_STOP = True

TempName = NewType("TempName", str)
FanName = NewType("FanName", str)
MappingName = NewType("MappingName", str)

T = TypeVar("T")


FanSpeedModifier = NamedTuple(
    "FanSpeedModifier",
    # fmt: off
    [
        ("fan", FanName),
        ("modifier", float),  # [0..1]
    ]
    # fmt: on
)

FansTempsRelation = NamedTuple(
    "FansTempsRelation",
    # fmt: off
    [
        ("temps", Sequence[TempName]),
        ("fans", Sequence[FanSpeedModifier]),
    ]
    # fmt: on
)

AlertCommands = NamedTuple(
    "AlertCommands",
    # fmt: off
    [
        ("enter_cmd", Optional[str]),
        ("leave_cmd", Optional[str]),
    ]
    # fmt: on
)


Actions = NamedTuple(
    "Actions",
    # fmt: off
    [
        ("panic", AlertCommands),
        ("threshold", AlertCommands),
    ]
    # fmt: on
)


TriggerConfig = NamedTuple(
    "TriggerConfig",
    # fmt: off
    [
        ("global_commands", Actions),
        ("temp_commands", Mapping[TempName, Actions]),
    ]
    # fmt: on
)


DaemonCLIConfig = NamedTuple(
    "DaemonCLIConfig",
    # fmt: off
    [
        ("pidfile", Optional[str]),
        ("logfile", Optional[str]),
        ("exporter_listen_host", Optional[str]),
    ]
    # fmt: on
)

DaemonConfig = NamedTuple(
    "DaemonConfig",
    # fmt: off
    [
        ("pidfile", Optional[str]),
        ("logfile", Optional[str]),
        ("interval", int),
        ("exporter_listen_host", Optional[str]),
    ]
    # fmt: on
)

ParsedConfig = NamedTuple(
    "ParsedConfig",
    # fmt: off
    [
        ("daemon", DaemonConfig),
        ("report_cmd", str),
        ("triggers", TriggerConfig),
        ("fans", Mapping[FanName, PWMFanNorm]),
        ("temps", Mapping[TempName, Temp]),
        ("mappings", Mapping[MappingName, FansTempsRelation]),
    ]
    # fmt: on
)


def parse_config(config_path: Path, daemon_cli_config: DaemonCLIConfig) -> ParsedConfig:
    config = configparser.ConfigParser(interpolation=None)
    try:
        config.read_string(config_path.read_text(), source=str(config_path))
    except Exception as e:
        raise RuntimeError("Unable to parse %s:\n%s" % (config_path, e))

    daemon, hddtemp = _parse_daemon(config, daemon_cli_config)
    report_cmd, global_commands = _parse_actions(config)
    arduino_connections = _parse_arduino_connections(config)
    temps, temp_commands = _parse_temps(config, hddtemp)
    fans = _parse_fans(config, arduino_connections)
    mappings = _parse_mappings(config, fans, temps)

    return ParsedConfig(
        daemon=daemon,
        report_cmd=report_cmd,
        triggers=TriggerConfig(
            global_commands=global_commands, temp_commands=temp_commands
        ),
        fans=fans,
        temps=temps,
        mappings=mappings,
    )


def first_not_none(*parts: Optional[T]) -> Optional[T]:
    for part in parts:
        if part is not None:
            return part
    return parts[-1]  # None


def _parse_daemon(
    config: configparser.ConfigParser, daemon_cli_config: DaemonCLIConfig
) -> Tuple[DaemonConfig, str]:
    daemon = config["daemon"]
    keys = set(daemon.keys())

    pidfile = first_not_none(
        daemon_cli_config.pidfile, daemon.get("pidfile"), DEFAULT_PIDFILE
    )
    if pidfile is not None and not pidfile.strip():
        pidfile = None
    keys.discard("pidfile")

    logfile = first_not_none(daemon_cli_config.logfile, daemon.get("logfile"))
    keys.discard("logfile")

    interval = daemon.getint("interval", fallback=DEFAULT_INTERVAL)
    keys.discard("interval")

    exporter_listen_host = first_not_none(
        daemon_cli_config.exporter_listen_host, daemon.get("exporter_listen_host")
    )
    keys.discard("exporter_listen_host")

    hddtemp = daemon.get("hddtemp") or DEFAULT_HDDTEMP
    keys.discard("hddtemp")

    if keys:
        raise RuntimeError("Unknown options in the [daemon] section: %s" % (keys,))

    return (
        DaemonConfig(
            pidfile=pidfile,
            logfile=logfile,
            interval=interval,
            exporter_listen_host=exporter_listen_host,
        ),
        hddtemp,
    )


def _parse_actions(config: configparser.ConfigParser) -> Tuple[str, Actions]:
    actions = config["actions"]
    keys = set(actions.keys())

    report_cmd = first_not_none(actions.get("report_cmd"), DEFAULT_REPORT_CMD)
    assert report_cmd is not None
    keys.discard("report_cmd")

    panic = AlertCommands(
        enter_cmd=first_not_none(actions.get("panic_enter_cmd")),
        leave_cmd=first_not_none(actions.get("panic_leave_cmd")),
    )
    keys.discard("panic_enter_cmd")
    keys.discard("panic_leave_cmd")

    threshold = AlertCommands(
        enter_cmd=first_not_none(actions.get("threshold_enter_cmd")),
        leave_cmd=first_not_none(actions.get("threshold_leave_cmd")),
    )
    keys.discard("threshold_enter_cmd")
    keys.discard("threshold_leave_cmd")

    if keys:
        raise RuntimeError("Unknown options in the [actions] section: %s" % (keys,))

    return report_cmd, Actions(panic=panic, threshold=threshold)


def _parse_arduino_connections(
    config: configparser.ConfigParser
) -> Mapping[ArduinoName, ArduinoConnection]:
    arduino_connections = {}  # type: Dict[ArduinoName, ArduinoConnection]
    for section_name in config.sections():
        section_name_parts = section_name.split(":", 1)

        if section_name_parts[0].strip().lower() != "arduino":
            continue

        arduino_name = ArduinoName(section_name_parts[1].strip())
        arduino = config[section_name]
        keys = set(arduino.keys())

        serial_url = arduino["serial_url"]
        keys.discard("serial_url")

        baudrate = arduino.getint("baudrate", fallback=DEFAULT_BAUDRATE)
        keys.discard("baudrate")
        status_ttl = arduino.getint("status_ttl", fallback=DEFAULT_STATUS_TTL)
        keys.discard("status_ttl")

        if keys:
            raise RuntimeError(
                "Unknown options in the [%s] section: %s" % (section_name, keys)
            )

        if arduino_name in arduino_connections:
            raise RuntimeError(
                "Duplicate arduino section declaration for '%s'" % arduino_name
            )
        arduino_connections[arduino_name] = ArduinoConnection(
            name=arduino_name,
            serial_url=serial_url,
            baudrate=baudrate,
            status_ttl=status_ttl,
        )

    # Empty arduino_connections is ok
    return arduino_connections


def _parse_temps(
    config: configparser.ConfigParser, hddtemp: str
) -> Tuple[Mapping[TempName, Temp], Mapping[TempName, Actions]]:
    temps = {}  # type: Dict[TempName, Temp]
    temp_commands = {}  # type: Dict[TempName, Actions]
    for section_name in config.sections():
        section_name_parts = section_name.split(":", 1)

        if section_name_parts[0].strip().lower() != "temp":
            continue

        temp_name = TempName(section_name_parts[1].strip())
        temp = config[section_name]
        keys = set(temp.keys())

        actions_panic = AlertCommands(
            enter_cmd=first_not_none(temp.get("panic_enter_cmd")),
            leave_cmd=first_not_none(temp.get("panic_leave_cmd")),
        )
        keys.discard("panic_enter_cmd")
        keys.discard("panic_leave_cmd")

        actions_threshold = AlertCommands(
            enter_cmd=first_not_none(temp.get("threshold_enter_cmd")),
            leave_cmd=first_not_none(temp.get("threshold_leave_cmd")),
        )
        keys.discard("threshold_enter_cmd")
        keys.discard("threshold_leave_cmd")

        panic = TempCelsius(temp.getfloat("panic"))
        threshold = TempCelsius(temp.getfloat("threshold"))
        min = TempCelsius(temp.getfloat("min"))
        max = TempCelsius(temp.getfloat("max"))
        keys.discard("panic")
        keys.discard("threshold")
        keys.discard("min")
        keys.discard("max")

        type = temp["type"]
        keys.discard("type")

        if type == "file":
            t = FileTemp(
                temp["path"], min=min, max=max, panic=panic, threshold=threshold
            )  # type: Temp
            keys.discard("path")
        elif type == "hdd":
            if min is None or max is None:
                raise RuntimeError(
                    "hdd temp '%s' doesn't define the mandatory `min` and `max` temps"
                    % temp_name
                )
            t = HDDTemp(
                temp["path"],
                min=min,
                max=max,
                panic=panic,
                threshold=threshold,
                hddtemp_bin=hddtemp,
            )
            keys.discard("path")
        elif type == "exec":
            t = CommandTemp(
                temp["command"], min=min, max=max, panic=panic, threshold=threshold
            )
            keys.discard("command")
        else:
            raise RuntimeError(
                "Unsupported temp type '%s' for temp '%s'" % (type, temp_name)
            )

        if keys:
            raise RuntimeError(
                "Unknown options in the [%s] section: %s" % (section_name, keys)
            )

        if temp_name in temps:
            raise RuntimeError(
                "Duplicate temp section declaration for '%s'" % temp_name
            )
        temps[temp_name] = t
        temp_commands[temp_name] = Actions(
            panic=actions_panic, threshold=actions_threshold
        )

    if not temps:
        raise RuntimeError("No temps found in the config, at least 1 must be specified")
    return temps, temp_commands


def _parse_fans(
    config: configparser.ConfigParser,
    arduino_connections: Mapping[ArduinoName, ArduinoConnection],
) -> Mapping[FanName, PWMFanNorm]:
    fans = {}  # type: Dict[FanName, PWMFanNorm]
    for section_name in config.sections():
        section_name_parts = section_name.split(":", 1)

        if section_name_parts[0].strip().lower() != "fan":
            continue

        fan_name = FanName(section_name_parts[1].strip())
        fan = config[section_name]
        keys = set(fan.keys())

        fan_type = fan.get("type", fallback=DEFAULT_FAN_TYPE)
        keys.discard("type")

        if fan_type == "linux":
            pwm = PWMDevice(fan["pwm"])
            fan_input = FanInputDevice(fan["fan_input"])
            keys.discard("pwm")
            keys.discard("fan_input")

            pwmfan = LinuxPWMFan(pwm=pwm, fan_input=fan_input)  # type: BasePWMFan
        elif fan_type == "arduino":
            arduino_name = ArduinoName(fan["arduino_name"])
            keys.discard("arduino_name")
            pwm_pin = ArduinoPin(fan.getint("pwm_pin"))
            keys.discard("pwm_pin")
            tacho_pin = ArduinoPin(fan.getint("tacho_pin"))
            keys.discard("tacho_pin")

            if arduino_name not in arduino_connections:
                raise ValueError("[arduino:%s] section is missing" % arduino_name)

            pwmfan = ArduinoPWMFan(
                arduino_connections[arduino_name], pwm_pin=pwm_pin, tacho_pin=tacho_pin
            )
        else:
            raise ValueError(
                "Unsupported FAN type %s. Supported ones are "
                "`linux` and `arduino`." % fan_type
            )

        never_stop = fan.getboolean("never_stop", fallback=DEFAULT_NEVER_STOP)
        keys.discard("never_stop")

        pwm_line_start = PWMValue(
            fan.getint("pwm_line_start", fallback=DEFAULT_PWM_LINE_START)
        )
        keys.discard("pwm_line_start")

        pwm_line_end = PWMValue(
            fan.getint("pwm_line_end", fallback=DEFAULT_PWM_LINE_END)
        )
        keys.discard("pwm_line_end")

        for pwm_value in (pwm_line_start, pwm_line_end):
            if not (pwmfan.min_pwm <= pwm_value <= pwmfan.max_pwm):
                raise RuntimeError(
                    "Incorrect PWM value '%s' for fan '%s': it must be within [%s;%s]"
                    % (pwm_value, fan_name, pwmfan.min_pwm, pwmfan.max_pwm)
                )
        if pwm_line_start >= pwm_line_end:
            raise RuntimeError(
                "`pwm_line_start` PWM value must be less than `pwm_line_end` for fan '%s'"
                % (fan_name,)
            )

        if keys:
            raise RuntimeError(
                "Unknown options in the [%s] section: %s" % (section_name, keys)
            )

        if fan_name in fans:
            raise RuntimeError("Duplicate fan section declaration for '%s'" % fan_name)
        fans[fan_name] = PWMFanNorm(
            pwmfan,
            pwm_line_start=pwm_line_start,
            pwm_line_end=pwm_line_end,
            never_stop=never_stop,
        )

    if not fans:
        raise RuntimeError("No fans found in the config, at least 1 must be specified")
    return fans


def _parse_mappings(
    config: configparser.ConfigParser,
    fans: Mapping[FanName, PWMFanNorm],
    temps: Mapping[TempName, Temp],
) -> Mapping[MappingName, FansTempsRelation]:

    mappings = {}  # type: Dict[MappingName, FansTempsRelation]
    for section_name in config.sections():
        section_name_parts = section_name.split(":", 1)

        if section_name_parts[0].lower() != "mapping":
            continue

        mapping_name = MappingName(section_name_parts[1])
        mapping = config[section_name]
        keys = set(mapping.keys())

        # temps:

        mapping_temps = [
            TempName(temp_name.strip()) for temp_name in mapping["temps"].split(",")
        ]
        mapping_temps = [s for s in mapping_temps if s]
        keys.discard("temps")
        if not mapping_temps:
            raise RuntimeError(
                "Temps must not be empty in the '%s' mapping" % mapping_name
            )
        for temp_name in mapping_temps:
            if temp_name not in temps:
                raise RuntimeError(
                    "Unknown temp '%s' in mapping '%s'" % (temp_name, mapping_name)
                )
        if len(mapping_temps) != len(set(mapping_temps)):
            raise RuntimeError(
                "There are duplicate temps in mapping '%s'" % mapping_name
            )

        # fans:

        fans_with_speed = [
            fan_with_speed.strip() for fan_with_speed in mapping["fans"].split(",")
        ]
        fans_with_speed = [s for s in fans_with_speed if s]
        keys.discard("fans")

        fan_speed_pairs = [
            fan_with_speed.split("*") for fan_with_speed in fans_with_speed
        ]
        for fan_speed_pair in fan_speed_pairs:
            if len(fan_speed_pair) not in (1, 2):
                raise RuntimeError(
                    "Invalid fan specification '%s' in mapping '%s'"
                    % (fan_speed_pair, mapping_name)
                )
        mapping_fans = [
            FanSpeedModifier(
                fan=FanName(fan_speed_pair[0].strip()),
                modifier=(
                    float(
                        fan_speed_pair[1].strip() if len(fan_speed_pair) == 2 else 1.0
                    )
                ),
            )
            for fan_speed_pair in fan_speed_pairs
        ]
        for fan_speed_modifier in mapping_fans:
            if fan_speed_modifier.fan not in fans:
                raise RuntimeError(
                    "Unknown fan '%s' in mapping '%s'"
                    % (fan_speed_modifier.fan, mapping_name)
                )
            if not (0 < fan_speed_modifier.modifier <= 1.0):
                raise RuntimeError(
                    "Invalid fan modifier '%s' in mapping '%s' for fan '%s': "
                    "the allowed range is (0.0;1.0]."
                    % (
                        fan_speed_modifier.modifier,
                        mapping_name,
                        fan_speed_modifier.fan,
                    )
                )
        if len(mapping_fans) != len(
            set(fan_speed_modifier.fan for fan_speed_modifier in mapping_fans)
        ):
            raise RuntimeError(
                "There are duplicate fans in mapping '%s'" % mapping_name
            )

        if keys:
            raise RuntimeError(
                "Unknown options in the [%s] section: %s" % (section_name, keys)
            )

        if mapping_name in fans:
            raise RuntimeError(
                "Duplicate mapping section declaration for '%s'" % mapping_name
            )
        mappings[mapping_name] = FansTempsRelation(
            temps=mapping_temps, fans=mapping_fans
        )

    unused_temps = set(temps.keys())
    unused_fans = set(fans.keys())
    for relation in mappings.values():
        unused_temps -= set(relation.temps)
        unused_fans -= set(
            fan_speed_modifier.fan for fan_speed_modifier in relation.fans
        )
    if unused_temps:
        raise RuntimeError(
            "The following temps are defined but not used in any mapping: %s"
            % unused_temps
        )
    if unused_fans:
        raise RuntimeError(
            "The following fans are defined but not used in any mapping: %s"
            % unused_fans
        )
    return mappings
