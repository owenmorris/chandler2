#!/usr/bin/env python
"""Distutils setup file"""

#import ez_setup
#ez_setup.use_setuptools()

from setuptools import setup, find_packages

def get_description():
    # Get our long description from the documentation
    f = file('README.txt')
    lines = []
    for line in f:
        if not line.strip():
            break     # skip to first blank line
    for line in f:
        if line.startswith('.. contents::'):
            break     # read to table of contents
        lines.append(line)
    f.close()
    return ''.join(lines)

setup(
    name="Chandler-Development",
    version="0.0.2",
    description="Chandler Application Development Plugin",
    long_description = open('README.txt').read(), # get_description(),
    install_requires=['Chandler-Platform'],
    namespace_packages=['chandler', 'chandler.debug'],
    test_suite = 'chandler.debug',
    packages = find_packages(),
    entry_points = """
    [chandler.launch.wxui]
    PyCrust = chandler.debug.py_crust:LaunchPyCrust
    [console_scripts]
    chandler-debug = chandler.debug.py_crust:debug_main
    """
),
