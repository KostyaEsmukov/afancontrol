from pkg_resources import get_distribution

_distribution = get_distribution("afancontrol")

__version__ = _distribution.version
