import subprocess

from afancontrol.logger import logger


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
