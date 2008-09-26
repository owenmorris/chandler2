===========================================
 The New Chandler Project (rearchitecture)
===========================================

Chandler is a PIM, with support for notes, events, and the concept of
"Triage".  Triage separates notes and events into NOW, DONE, and LATER.

Chandler is also a platform for building a PIM.  Chandler aims to
allow application builders to build different PIMs by reusing
different pieces of Chandler.

Core Chandler Sub-Projects
=================

Chandler-Platform
    Platform services such as startups, plugin management, Twisted,
    "Headless" and wx-based shells, etc., that could be used to create
    applications like Chandler.  Modules here will include:

Chandler-App
    Chandler application-specific code.  This is a catch-all project for now;
    as it grows we will likely split it into separate projects, perhaps e.g.
    Chandler-PIM, Chandler-wx, etc.

Testing
=======

Each Chandler Sub-Project should have a README.txt, a collection of
test_*.py tests, and a test_suite.py which runs all tests and doctests
all .txt files.

Entry Points
============

Because Chandler makes extensive use of entry points, any entry points
used should be documented in Entry-Points.txt
