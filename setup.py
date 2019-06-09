#!/usr/bin/env python3

import re

from setuptools import setup

with open("src/afancontrol/__init__.py", "rt") as f:
    version = re.search(r'^__version__ = "(.*?)"$', f.read()).group(1)

setup(
    version=version,
    data_files=[
        ("etc/afancontrol", ["pkg/afancontrol.conf"]),
        ("etc/systemd/system", ["pkg/afancontrol.service"]),
    ],
)
