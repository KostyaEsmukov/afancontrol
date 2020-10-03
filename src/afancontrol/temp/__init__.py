from typing import Mapping, NamedTuple, NewType

from afancontrol.configparser import ConfigParserSection
from afancontrol.exec import Programs
from afancontrol.filters import FilterName, NullFilter, TempFilter
from afancontrol.temp.base import Temp, TempCelsius, TempStatus
from afancontrol.temp.command import CommandTemp
from afancontrol.temp.file import FileTemp
from afancontrol.temp.hdd import HDDTemp

__all__ = (
    "CommandTemp",
    "FileTemp",
    "HDDTemp",
    "Temp",
    "TempCelsius",
    "TempStatus",
)

TempName = NewType("TempName", str)


class FilteredTemp(NamedTuple):
    temp: Temp
    filter: TempFilter

    @classmethod
    def from_configparser(
        cls,
        section: ConfigParserSection[TempName],
        filters: Mapping[FilterName, TempFilter],
        programs: Programs,
    ) -> "FilteredTemp":

        type = section["type"]

        if type == "file":
            temp: Temp = FileTemp.from_configparser(section)
        elif type == "hdd":
            temp = HDDTemp.from_configparser(section, programs)
        elif type == "exec":
            temp = CommandTemp.from_configparser(section)
        else:
            raise RuntimeError(
                "Unsupported temp type '%s' for temp '%s'" % (type, section.name)
            )

        filter_name = section.get("filter", fallback=None)

        if filter_name is None:
            filter: TempFilter = NullFilter()
        else:
            filter = filters[FilterName(filter_name.strip())].copy()

        return cls(temp=temp, filter=filter)
