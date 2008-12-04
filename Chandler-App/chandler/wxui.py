def load_wxui(app):
    """Code to hook up a wx UI to app's interaction model"""

    # Display a GUI python shell with extra development features
    # (PyShell), where the 'app' variable is bound to the Chandler
    # application.
    # XXX: Move this dev feature into Chandler-Development plugin

    from wx import py

    frame = py.shell.ShellFrame(locals=locals(), title="Chandler PyShell")
    frame.Show(True)
