=============================
Chandler Application Platform
=============================

---------------
The Runtime API
---------------

The Runtime API (``chandler.runtime``) provides services for application startup
and shutdown hooks, and wx/Twisted main loops.


Startup Hook Names
==================

chandler.launch.reactor
    Called after the Twisted reactor is initialized

chandler.launch.wxui
    Called after the ``wx.App`` and Twisted reactor are initialized

chandler.launch.app
    Called after all environment-specific services are initialized

Implementations registered for these hooks should be 1-argument callables
accepting a ``runtime.Application`` instance.

These names and the loading order are subject to change.


Application Object
==================

``runtime.Application`` is an extensible component with a ``run()`` method
that accepts optional extensions to run before and after the
``chandler.launch.app`` hook.

This allows you to do something like this::

    Application().run(
        before = runtime.use_wx_twisted,
        after = plugins.Hook('myapp.launch')
    )
    
...to set up a wx+Twisted main loop before the ``chandler.launch.app`` hook
is run, and to run the ``myapp.launch`` hook after it.  The `before`
and `after` arguments can be 1-argument callables or (optionally nested)
sequences of 1-argument callables.  (Which means they can be
``plugins.Hook`` objects).

The ``runtime.use_twisted`` and ``runtime.use_wx_twisted`` functions
are 1-argument callables that set up the operating environment for
using either Twisted or wx+Twisted, respectively.  If you want to use
a custom reactor, you should set it up before ``use_twisted`` is called,
since it invokes the ``chandler.launch.reactor`` hook, which may cause
the import of modules that use the reactor directly.  (And once the
reactor has been imported, it can't be replaced.)


