import subprocess
from typing import NamedTuple

from afancontrol.configparser import ConfigParserSection
from afancontrol.logger import logger


class Programs(NamedTuple):
    hddtemp: str
    ipmi_sensors: str

    @classmethod
    def from_configparser(cls, section: ConfigParserSection) -> "Programs":
        return cls(
            hddtemp=section.get("hddtemp", fallback="hddtemp"),
            ipmi_sensors=section.get("ipmi_sensors", fallback="ipmi-sensors"),
        )


def exec_shell_command(shell_command: str, timeout: int = 5) -> str:
    try:
        p = subprocess.run(
            shell_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            check=True,
            timeout=timeout,
        )
        out = p.stdout.decode("ascii")
        err = p.stderr.decode().strip()
        if err:
            logger.warning(
                "Shell command '%s' executed successfully, but printed to stderr:\n%s",
                shell_command,
                err,
            )
        return out
    except subprocess.CalledProcessError as e:
        ec = e.returncode
        out = e.stdout.decode().strip()
        err = e.stderr.decode().strip()
        logger.error(
            "Shell command '%s' failed (exit code %s):\nstdout:\n%s\nstderr:\n%s\n",
            shell_command,
            ec,
            out,
            err,
        )
        raise
