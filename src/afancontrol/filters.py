import abc
import collections
from typing import Deque, Optional, TypeVar

from afancontrol.temp import TempStatus

T = TypeVar("T")


class TempFilter(abc.ABC):
    @abc.abstractmethod
    def copy(self: T) -> T:
        pass

    @abc.abstractmethod
    def apply(self, status: Optional[TempStatus]) -> Optional[TempStatus]:
        pass

    def __enter__(self):  # reusable
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        pass


class NullFilter(TempFilter):
    def copy(self: T) -> T:
        return type(self)()

    def apply(self, status: Optional[TempStatus]) -> Optional[TempStatus]:
        return status

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return True

        return NotImplemented

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return "%s()" % (type(self).__name__,)


def _temp_status_sorting_key(status: Optional[TempStatus]) -> float:
    if status is None:
        return float("+inf")
    return status.temp


class MovingQuantileFilter(TempFilter):
    def __init__(self, quantile: float, *, window_size: int) -> None:
        self.quantile = quantile
        self.window_size = window_size
        self.history = None  # type: Optional[Deque[Optional[TempStatus]]]

    def copy(self: T) -> T:
        return type(self)(  # type: ignore
            quantile=self.quantile, window_size=self.window_size  # type: ignore
        )

    def apply(self, status: Optional[TempStatus]) -> Optional[TempStatus]:
        assert self.history is not None
        self.history.append(status)

        observations = sorted(self.history, key=_temp_status_sorting_key)
        target_idx = int(len(observations) * self.quantile)
        return observations[target_idx]

    def __enter__(self):  # reusable
        assert self.history is None
        self.history = collections.deque(maxlen=self.window_size)
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        assert self.history is not None
        self.history = None

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return (
                self.quantile == other.quantile
                and self.window_size == other.window_size
            )

        return NotImplemented

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return "%s(quantile=%r, window_size=%r)" % (
            type(self).__name__,
            self.quantile,
            self.window_size,
        )


class MovingMedianFilter(MovingQuantileFilter):
    def __init__(self, window_size: int) -> None:
        super().__init__(quantile=0.5, window_size=window_size)

    def copy(self: T) -> T:
        return type(self)(window_size=self.window_size)  # type: ignore
