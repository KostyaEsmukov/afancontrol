import configparser
from typing import Any, Generic, Iterator, Optional, Type, TypeVar, Union, overload

T = TypeVar("T", bound=str)
F = TypeVar("F", None, Any)

_UNSET = object()


def iter_sections(
    config: configparser.ConfigParser, section_type: str, name_typevar: Type[T]
) -> Iterator["ConfigParserSection[T]"]:
    for section_name in config.sections():
        section_name_parts = section_name.split(":", 1)

        if section_name_parts[0].strip().lower() != section_type:
            continue

        name = name_typevar(section_name_parts[1].strip())
        section = ConfigParserSection(config[section_name], name)
        yield section


class ConfigParserSection(Generic[T]):
    def __init__(
        self, section: configparser.SectionProxy, name: Optional[T] = None
    ) -> None:
        self.__name = name
        self.__section = section
        self.__unused_keys = set(section.keys())

    @property
    def name(self) -> T:
        assert self.__name is not None
        return self.__name

    def ensure_no_unused_keys(self) -> None:
        if self.__unused_keys:
            raise RuntimeError(
                "Unknown options in the [%s] section: %s"
                % (self.__section.name, self.__unused_keys)
            )

    def __contains__(self, key):
        return self.__section.__contains__(key)

    def __getitem__(self, key):
        self.__unused_keys.discard(key)
        return self.__section.__getitem__(key)

    @overload
    def get(self, option: str) -> str:
        ...

    @overload
    def get(self, option: str, *, fallback: F) -> Union[str, F]:
        ...

    def get(self, option: str, *, fallback=_UNSET) -> Union[str, F]:
        kwargs = {}
        if fallback is not _UNSET:
            kwargs["fallback"] = fallback
        self.__unused_keys.discard(option)
        res = self.__section.get(option, **kwargs)
        if res is None and fallback is _UNSET:
            raise ValueError(
                "[%s] %r option is expected to be set" % (self.__section.name, option)
            )
        return res

    @overload
    def getint(self, option: str) -> int:
        ...

    @overload
    def getint(self, option: str, *, fallback: F) -> Union[int, F]:
        ...

    def getint(self, option: str, *, fallback=_UNSET) -> Union[int, F]:
        kwargs = {}
        if fallback is not _UNSET:
            kwargs["fallback"] = fallback
        self.__unused_keys.discard(option)
        res = self.__section.getint(option, **kwargs)
        if res is None and fallback is _UNSET:
            raise ValueError(
                "[%s] %r option is expected to be set" % (self.__section.name, option)
            )
        return res

    @overload
    def getfloat(self, option: str) -> float:
        ...

    @overload
    def getfloat(self, option: str, *, fallback: F) -> Union[float, F]:
        ...

    def getfloat(self, option: str, *, fallback=_UNSET) -> Union[float, F]:
        kwargs = {}
        if fallback is not _UNSET:
            kwargs["fallback"] = fallback
        self.__unused_keys.discard(option)
        res = self.__section.getfloat(option, **kwargs)
        if res is None and fallback is _UNSET:
            raise ValueError(
                "[%s] %r option is expected to be set" % (self.__section.name, option)
            )
        return res

    @overload
    def getboolean(self, option: str) -> bool:
        ...

    @overload
    def getboolean(self, option: str, *, fallback: F) -> Union[bool, F]:
        ...

    def getboolean(self, option: str, *, fallback=_UNSET) -> Union[bool, F]:
        kwargs = {}
        if fallback is not _UNSET:
            kwargs["fallback"] = fallback
        self.__unused_keys.discard(option)
        res = self.__section.getboolean(option, **kwargs)
        if res is None and fallback is _UNSET:
            raise ValueError(
                "[%s] %r option is expected to be set" % (self.__section.name, option)
            )
        return res
