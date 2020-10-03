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

import afancontrol.filters
from afancontrol.arduino import ArduinoConnection, ArduinoName
from afancontrol.configparser import ConfigParserSection, iter_sections
from afancontrol.exec import Programs
from afancontrol.filters import FilterName, TempFilter
from afancontrol.logger import logger
from afancontrol.pwmfan import FanName, ReadonlyFanName
from afancontrol.pwmfannorm import PWMFanNorm, ReadonlyPWMFanNorm
from afancontrol.temp import FilteredTemp, TempName

DEFAULT_CONFIG = "/etc/afancontrol/afancontrol.conf"
DEFAULT_PIDFILE = "/run/afancontrol.pid"
DEFAULT_REPORT_CMD = (
    'printf "Subject: %s\nTo: %s\n\n%b"'
    ' "afancontrol daemon report: %REASON%" root "%MESSAGE%"'
    " | sendmail -t"
)

MappingName = NewType("MappingName", str)

T = TypeVar("T")


class FanSpeedModifier(NamedTuple):
    fan: FanName
    modifier: float  # [0..1]


class FansTempsRelation(NamedTuple):
    temps: Sequence[TempName]
    fans: Sequence[FanSpeedModifier]


class AlertCommands(NamedTuple):
    enter_cmd: Optional[str]
    leave_cmd: Optional[str]


class Actions(NamedTuple):
    panic: AlertCommands
    threshold: AlertCommands

    @classmethod
    def from_configparser(cls, section: ConfigParserSection) -> "Actions":
        panic = AlertCommands(
            enter_cmd=section.get("panic_enter_cmd", fallback=None),
            leave_cmd=section.get("panic_leave_cmd", fallback=None),
        )

        threshold = AlertCommands(
            enter_cmd=section.get("threshold_enter_cmd", fallback=None),
            leave_cmd=section.get("threshold_leave_cmd", fallback=None),
        )

        return cls(panic=panic, threshold=threshold)


class TriggerConfig(NamedTuple):
    global_commands: Actions
    temp_commands: Mapping[TempName, Actions]


class DaemonCLIConfig(NamedTuple):
    pidfile: Optional[str]
    logfile: Optional[str]
    exporter_listen_host: Optional[str]


class DaemonConfig(NamedTuple):
    pidfile: Optional[str]
    logfile: Optional[str]
    interval: int
    exporter_listen_host: Optional[str]

    @classmethod
    def from_configparser(
        cls, section: ConfigParserSection, daemon_cli_config: DaemonCLIConfig
    ) -> "DaemonConfig":
        pidfile = first_not_none(
            daemon_cli_config.pidfile, section.get("pidfile", fallback=DEFAULT_PIDFILE)
        )
        if pidfile is not None and not pidfile.strip():
            pidfile = None

        logfile = first_not_none(
            daemon_cli_config.logfile, section.get("logfile", fallback=None)
        )

        interval = section.getint("interval", fallback=5)

        exporter_listen_host = first_not_none(
            daemon_cli_config.exporter_listen_host,
            section.get("exporter_listen_host", fallback=None),
        )

        return cls(
            pidfile=pidfile,
            logfile=logfile,
            interval=interval,
            exporter_listen_host=exporter_listen_host,
        )


class ParsedConfig(NamedTuple):
    daemon: DaemonConfig
    report_cmd: str
    triggers: TriggerConfig
    arduino_connections: Mapping[ArduinoName, ArduinoConnection]
    fans: Mapping[FanName, PWMFanNorm]
    readonly_fans: Mapping[ReadonlyFanName, ReadonlyPWMFanNorm]
    temps: Mapping[TempName, FilteredTemp]
    mappings: Mapping[MappingName, FansTempsRelation]


def parse_config(config_path: Path, daemon_cli_config: DaemonCLIConfig) -> ParsedConfig:
    config = configparser.ConfigParser(interpolation=None)
    try:
        config.read_string(config_path.read_text(), source=str(config_path))
    except Exception as e:
        raise RuntimeError("Unable to parse %s:\n%s" % (config_path, e))

    daemon, programs = _parse_daemon(config, daemon_cli_config)
    report_cmd, global_commands = _parse_actions(config)
    arduino_connections = _parse_arduino_connections(config)
    filters = _parse_filters(config)
    temps, temp_commands = _parse_temps(config, programs, filters)
    fans = _parse_fans(config, arduino_connections)
    readonly_fans = _parse_readonly_fans(config, arduino_connections, programs)
    _check_fans_namespace(fans, readonly_fans)
    mappings = _parse_mappings(config, fans, temps)

    return ParsedConfig(
        daemon=daemon,
        report_cmd=report_cmd,
        triggers=TriggerConfig(
            global_commands=global_commands, temp_commands=temp_commands
        ),
        arduino_connections=arduino_connections,
        fans=fans,
        readonly_fans=readonly_fans,
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
) -> Tuple[DaemonConfig, Programs]:
    section: ConfigParserSection[str] = ConfigParserSection(config["daemon"])
    daemon_config = DaemonConfig.from_configparser(section, daemon_cli_config)
    programs = Programs.from_configparser(section)
    section.ensure_no_unused_keys()

    return daemon_config, programs


def _parse_actions(config: configparser.ConfigParser) -> Tuple[str, Actions]:
    section: ConfigParserSection[str] = ConfigParserSection(config["actions"])
    report_cmd = section.get("report_cmd", fallback=DEFAULT_REPORT_CMD)
    actions = Actions.from_configparser(section)
    section.ensure_no_unused_keys()

    return report_cmd, actions


def _parse_arduino_connections(
    config: configparser.ConfigParser,
) -> Mapping[ArduinoName, ArduinoConnection]:
    arduino_connections: Dict[ArduinoName, ArduinoConnection] = {}
    for section in iter_sections(config, "arduino", ArduinoName):
        if section.name in arduino_connections:
            raise RuntimeError(
                "Duplicate arduino section declaration for '%s'" % section.name
            )
        arduino_connections[section.name] = ArduinoConnection.from_configparser(section)
        section.ensure_no_unused_keys()

    # Empty arduino_connections is ok
    return arduino_connections


def _parse_filters(
    config: configparser.ConfigParser,
) -> Mapping[FilterName, TempFilter]:
    filters: Dict[FilterName, TempFilter] = {}
    for section in iter_sections(config, "filter", FilterName):
        if section.name in filters:
            raise RuntimeError(
                "Duplicate filter section declaration for '%s'" % section.name
            )
        filters[section.name] = afancontrol.filters.from_configparser(section)
        section.ensure_no_unused_keys()

    # Empty filters is ok
    return filters


def _parse_temps(
    config: configparser.ConfigParser,
    programs: Programs,
    filters: Mapping[FilterName, TempFilter],
) -> Tuple[Mapping[TempName, FilteredTemp], Mapping[TempName, Actions]]:
    temps: Dict[TempName, FilteredTemp] = {}
    temp_commands: Dict[TempName, Actions] = {}
    for section in iter_sections(config, "temp", TempName):
        if section.name in temps:
            raise RuntimeError(
                "Duplicate temp section declaration for '%s'" % section.name
            )
        temps[section.name] = FilteredTemp.from_configparser(section, filters, programs)
        temp_commands[section.name] = Actions.from_configparser(section)
        section.ensure_no_unused_keys()

    return temps, temp_commands


def _parse_fans(
    config: configparser.ConfigParser,
    arduino_connections: Mapping[ArduinoName, ArduinoConnection],
) -> Mapping[FanName, PWMFanNorm]:
    fans: Dict[FanName, PWMFanNorm] = {}
    for section in iter_sections(config, "fan", FanName):
        if section.name in fans:
            raise RuntimeError(
                "Duplicate fan section declaration for '%s'" % section.name
            )
        fans[section.name] = PWMFanNorm.from_configparser(section, arduino_connections)
        section.ensure_no_unused_keys()

    return fans


def _parse_readonly_fans(
    config: configparser.ConfigParser,
    arduino_connections: Mapping[ArduinoName, ArduinoConnection],
    programs: Programs,
) -> Mapping[ReadonlyFanName, ReadonlyPWMFanNorm]:
    readonly_fans: Dict[ReadonlyFanName, ReadonlyPWMFanNorm] = {}
    for section in iter_sections(config, "readonly_fan", ReadonlyFanName):
        if section.name in readonly_fans:
            raise RuntimeError(
                "Duplicate readonly_fan section declaration for '%s'" % section.name
            )
        readonly_fans[section.name] = ReadonlyPWMFanNorm.from_configparser(
            section, arduino_connections, programs
        )
        section.ensure_no_unused_keys()

    return readonly_fans


def _check_fans_namespace(
    fans: Mapping[FanName, PWMFanNorm],
    readonly_fans: Mapping[ReadonlyFanName, ReadonlyPWMFanNorm],
) -> None:
    common_keys = fans.keys() & readonly_fans.keys()
    if common_keys:
        raise RuntimeError(
            "Duplicate fan names has been found between `fan` "
            "and `readonly_fan` sections: %r" % (list(common_keys),)
        )


def _parse_mappings(
    config: configparser.ConfigParser,
    fans: Mapping[FanName, PWMFanNorm],
    temps: Mapping[TempName, FilteredTemp],
) -> Mapping[MappingName, FansTempsRelation]:

    mappings: Dict[MappingName, FansTempsRelation] = {}
    for section in iter_sections(config, "mapping", MappingName):

        # temps:

        mapping_temps = [
            TempName(temp_name.strip()) for temp_name in section["temps"].split(",")
        ]
        mapping_temps = [s for s in mapping_temps if s]
        if not mapping_temps:
            raise RuntimeError(
                "Temps must not be empty in the '%s' mapping" % section.name
            )
        for temp_name in mapping_temps:
            if temp_name not in temps:
                raise RuntimeError(
                    "Unknown temp '%s' in mapping '%s'" % (temp_name, section.name)
                )
        if len(mapping_temps) != len(set(mapping_temps)):
            raise RuntimeError(
                "There are duplicate temps in mapping '%s'" % section.name
            )

        # fans:

        fans_with_speed = [
            fan_with_speed.strip() for fan_with_speed in section["fans"].split(",")
        ]
        fans_with_speed = [s for s in fans_with_speed if s]

        fan_speed_pairs = [
            fan_with_speed.split("*") for fan_with_speed in fans_with_speed
        ]
        for fan_speed_pair in fan_speed_pairs:
            if len(fan_speed_pair) not in (1, 2):
                raise RuntimeError(
                    "Invalid fan specification '%s' in mapping '%s'"
                    % (fan_speed_pair, section.name)
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
                    % (fan_speed_modifier.fan, section.name)
                )
            if not (0 < fan_speed_modifier.modifier <= 1.0):
                raise RuntimeError(
                    "Invalid fan modifier '%s' in mapping '%s' for fan '%s': "
                    "the allowed range is (0.0;1.0]."
                    % (
                        fan_speed_modifier.modifier,
                        section.name,
                        fan_speed_modifier.fan,
                    )
                )
        if len(mapping_fans) != len(
            set(fan_speed_modifier.fan for fan_speed_modifier in mapping_fans)
        ):
            raise RuntimeError(
                "There are duplicate fans in mapping '%s'" % section.name
            )

        if section.name in mappings:
            raise RuntimeError(
                "Duplicate mapping section declaration for '%s'" % section.name
            )
        mappings[section.name] = FansTempsRelation(
            temps=mapping_temps, fans=mapping_fans
        )
        section.ensure_no_unused_keys()

    unused_temps = set(temps.keys())
    unused_fans = set(fans.keys())
    for relation in mappings.values():
        unused_temps -= set(relation.temps)
        unused_fans -= set(
            fan_speed_modifier.fan for fan_speed_modifier in relation.fans
        )
    if unused_temps:
        logger.warning(
            "The following temps are defined but not used in any mapping: %s",
            unused_temps,
        )
    if unused_fans:
        raise RuntimeError(
            "The following fans are defined but not used in any mapping: %s"
            % unused_fans
        )
    return mappings
