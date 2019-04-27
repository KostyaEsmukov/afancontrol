import click

import afancontrol
from afancontrol.daemon import daemon
from afancontrol.fantest import fantest


@click.group()
@click.version_option(version=afancontrol.__version__)
def main():
    """afancontrol is an Advanced Fan Control program, which controls PWM
    fans according to the current temperatures of the system components.
    """
    pass


main.add_command(daemon)
main.add_command(fantest)

if __name__ == "__main__":
    main(prog_name="afancontrol")
