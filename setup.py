#!/usr/bin/env python3

from setuptools import setup

import afancontrol

setup(
    version=afancontrol.__version__,
    data_files={
        # XXX systemd unit?
    }.items(),
)
