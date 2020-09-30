import abc
from typing import NamedTuple, NewType, Optional, Tuple

TempCelsius = NewType("TempCelsius", float)


class TempStatus(NamedTuple):
    temp: TempCelsius
    min: TempCelsius
    max: TempCelsius
    panic: Optional[TempCelsius]
    threshold: Optional[TempCelsius]
    is_panic: bool
    is_threshold: bool


class Temp(abc.ABC):
    def __init__(
        self, *, panic: Optional[TempCelsius], threshold: Optional[TempCelsius]
    ) -> None:
        self._panic = panic
        self._threshold = threshold

    def get(self) -> TempStatus:
        temp, min_t, max_t = self._get_temp()

        if not (min_t < max_t):
            raise RuntimeError(
                "Min temperature must be less than max. %s < %s" % (min_t, max_t)
            )

        return TempStatus(
            temp=temp,
            min=min_t,
            max=max_t,
            panic=self._panic,
            threshold=self._threshold,
            is_panic=self._panic is not None and temp >= self._panic,
            is_threshold=self._threshold is not None and temp >= self._threshold,
        )

    @abc.abstractmethod
    def _get_temp(self) -> Tuple[TempCelsius, TempCelsius, TempCelsius]:
        pass
