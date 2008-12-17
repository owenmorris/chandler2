import optparse
import peak.events.trellis as trellis
from chandler import runtime, keyword

class ChandlerApplication(runtime.Application, trellis.Component):
    """The Chandler Application"""

    trellis.attrs(
        collections=(),
    )

def load_domain(app):
    """Load up the interaction layer for ChandlerApplication"""
    app.collections = trellis.List(keyword.Keyword(name) for name in (u"Home", u"Work"))

def load_interaction(app):
    load_domain(app)

    # IM-specific stuff here
    from chandler.sidebar import load_interaction
    load_interaction(app)

def _headless(app):
    banner = """
Welcome!This is the headless (no wx) version of Chandler,
which will shut down once you exit this Python session.

The variable 'app' is set to the ChandlerApplication instance.
"""

    try:
        from IPython.Shell import IPShellEmbed
        argv = ['-pi1', 'In [\\#]: ','-pi2','   .\\D.:','-po','Out[\\#]: ']
        ipshell = IPShellEmbed(argv, banner=banner)
        ipshell()
    except ImportError:
        from code import interact
        interact(local=dict(app=app))

    print "Shutting down..."

def main():
    parser = optparse.OptionParser()
    parser.add_option("-H", "--headless", action="store_true", dest="headless")

    options, arguments = parser.parse_args()
    if options.headless:
        ChandlerApplication().run(after=_headless)
    else:
        ChandlerApplication().run(after=runtime.use_wx_twisted)
