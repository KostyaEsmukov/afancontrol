import configparser
from typing import Generic, TypeVar, Union, overload

T = TypeVar("T")
F = TypeVar("F")

_UNSET = object()


class ConfigParserSection(Generic[T]):
    def __init__(self, name: T, section: configparser.SectionProxy) -> None:
        self.__name = name
        self.__section = section
        self.__unused_keys = set(section.keys())

    @property
    def name(self) -> T:
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
        return self.__section.get(option, **kwargs)

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
        return self.__section.getint(option, **kwargs)

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
        return self.__section.getfloat(option, **kwargs)

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
        return self.__section.getboolean(option, **kwargs)
