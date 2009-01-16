"""PyCrust utilities"""

import sys, wx
from chandler.debug import Debugger
from chandler import runtime
import peak.events.trellis as trellis

def LaunchPyCrust(app):
    """Launch a PyCrust window, putting `app` in its locals"""
    from wx.py.crust import CrustFrame
    frame = CrustFrame()
    frame.Show(True)

    # Link the PyCrust's locals to the debugger's variables
    from chandler.debug import Debugger
    debug = Debugger(app)
    interp = frame.shell.interp
    interp.locals.update(debug.variables)
    debug.variables.update(interp.locals)
    interp.locals = debug.variables


def debug_main():
    """Run the application, adding hooks specified on the command line"""
    from peak.util.imports import importSequence
    runtime.Application().run(
        before=runtime.use_wx_twisted, # LaunchPyCrust will go here too, later
        after=importSequence(sys.argv[1:])
    )
