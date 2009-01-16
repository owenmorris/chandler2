===========================
Chandler Development Plugin
===========================

Right now, this plugin just launches a PyCrust window at application startup.
Later, it'll put things on the Tools menu.  (When there is a Tools menu, and
a main window to put it in!)

The way this works is that an entry point is registered in ``setup.py``, viz::

    [chandler.launch.wxui]
    PyCrust = chandler.debug.py_crust:LaunchPyCrust

Thereby registering an implementation for the ``chandler.launch.wxui`` hook, which
runs after Twisted and wx are initialized, but before the general application
startup hooks.

(Note that we are currently *abusing* ``chandler.launch.wxui`` to do this, until
there is an application-specific wx/ui startup hook that runs *after* general
application startup.)


Debugging Widgets
-----------------

The ``chandler-debug`` script that's installed by this plugin can be used to
specify extensions on the command line, that will be loaded at application
start.  Your extension should take a single argument, which will be a
``ChandlerApplication`` instance.  You can use this to access `the debugger`_
(as seen in the next section).

As for what to do with the application object in your function, see the
next section...


The Debugger
------------

There is also now a ``Debugger`` class, that you can use to make variables
available to the PyCrust window (or in future, the "headless" tool)::

    >>> from chandler.debug import Debugger
    >>> from chandler.runtime import Application
    >>> app = Application()
    >>> dbg = Debugger(app)

    >>> sorted(dbg.variables.keys())    # default variables
    ['app', 'chandler', 'peak', 'wx']

    >>> dbg.variables['app'] is app     # 'app' is whatever the debugger wraps
    True

    >>> dbg.variables['demo'] = 42      # we can add stuff
    >>> dbg.variables['demo']
    42

The ``Debugger`` is an "add-on" class, which means that no matter how many
times you call ``Debugger(app)`` you will get the same instance each time
(as long as you pass in the same ``app``, of course).

Thus, you can write a startup hook like this::

    def MyHook(app):
        frame = wx.Frame(...)
        # set it up, add controls, show it, etc.
        Debugger(app).variables['my_frame'] = frame

Then, you can either run it with ``chandler-debug some.module:MyHook``, or you can
register it in your ``setup.py`` like this::

    [chandler.launch.wxui]
    My Hook = some.module:MyHook

Then it will be started whenever a ``chandler.runtime``-based application starts,
and the frame will be accessible as the 'my_frame' local variable in the
PyCrust window.

