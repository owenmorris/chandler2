===========================================
 The New Chandler Project (rearchitecture)
===========================================

Chandler is a PIM, with support for notes, reminders, events, and the concept of
:mod:`~chandler.triage`.

Chandler is also a platform for building a PIM.  Chandler aims to
allow application builders to build different PIMs by reusing
different pieces of Chandler.

Core Chandler Sub-Projects
==========================

Chandler-Platform
-----------------

The basic unit of data in Chandler is an Item.  The Platform project
provides tools for building applications that create and extend Items.

.. toctree::
   :maxdepth: 2

   Chandler-Platform/README


Chandler-App
------------

Chandler application-specific code.

XXX This is a catch-all project for now; as it grows we will likely
    split it into separate projects, perhaps e.g.  Chandler-PIM,
    Chandler-wx, etc.

.. toctree::
   :maxdepth: 3

   Chandler-App/README

Sharing
-------

Sharing doctests are more focused on testing and less on being
instructive, so they're separated out from the main Chandler-Platform
and Chandler-App documents.

.. toctree::
   :maxdepth: 2

   Chandler-Platform/EIM
   Chandler-App/Sharing
   Chandler-App/Translator


Chandler-Development
--------------------

Tools for developing and debugging Chandler. For the moment, this
containts a PyShell window you can use for debugging.

.. toctree::
   :maxdepth: 3

   Chandler-Development/README

Hooks
=====

Because Chandler makes extensive use of entry points, any entry points
used should be documented in Hooks.txt.

.. toctree::
   :maxdepth: 1

   Hooks

Testing
=======

Each Chandler Sub-Project should have a README.txt, a collection of
test_*.py tests, and a test_suite.py which runs all tests and doctests
all .txt files.

