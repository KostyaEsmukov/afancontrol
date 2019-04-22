from afancontrol.exec import exec_shell_command
from afancontrol.logger import logger


class Report:
    def __init__(self, report_command: str) -> None:
        self._report_command = report_command

    def report(self, reason: str, message: str) -> None:
        logger.info("[REPORT] Reason: %s. Message: %s", reason, message)
        try:
            rc = self._report_command
            rc = rc.replace("%REASON%", reason)
            rc = rc.replace("%MESSAGE%", message)
            exec_shell_command(rc)
        except Exception as ex:
            logger.warning("Report failed: %s", ex, exc_info=True)
