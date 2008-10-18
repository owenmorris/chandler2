#!/usr/bin/env python
"""Distutils setup file"""

from setuptools import setup, find_packages

setup(
    name="Chandler-App",
    version="0.0.2",
    description="Chandler Application (Pilot Project)",
    long_description = open('README.txt').read(),
    install_requires=['Chandler-Platform'],
    test_suite = 'test_suite',
    packages = find_packages(),
    namespace_packages = ['chandler'],
    entry_points = """
    [chandler.domain.triage]
    event = chandler.event:event_triage

    [chandler.domain.item_addon]
    triage = chandler.triage:Triage
    triage_position = chandler.triage:TriagePosition
    reminder = chandler.reminder:ReminderList
    """
),
