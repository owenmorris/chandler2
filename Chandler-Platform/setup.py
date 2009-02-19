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
    name="Chandler-Platform",
    version="0.0.2",
    description="Chandler Application Platform (Pilot Project)",
    long_description = open('README.txt').read(), # get_description(),
    install_requires=[
        'DecoratorTools>=1.6', #'Presentable>=0.1a1dev-r2439',
        'Trellis>=0.7a3dev-r2595,==dev',
        'Plugins>=0.5a1dev-r2404,>=0.5a1dev,==dev',
        'Importing>=1.9.2',
        'AddOns==dev,>=0.7dev-r2409',
        'vobject>=0.7.1,==dev',
    ],
    dependency_links=[
        'http://peak.telecommunity.com/snapshots/',
        'svn://svn.eby-sarna.com/svnroot/Trellis#egg=Trellis-dev',
        'svn://svn.eby-sarna.com/svnroot/AddOns#egg=AddOns-dev',
    ],
    test_suite = 'test_suite',
    test_loader = 'test_suite:TestLoader',
    packages = find_packages(),
    namespace_packages = ['chandler', 'chandler.sharing', 'chandler.wxui'   ],
)
