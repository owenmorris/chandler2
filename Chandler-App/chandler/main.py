import optparse
import peak.events.trellis as trellis
import peak.context as context
from chandler import runtime, core, keyword
import chandler.sidebar as sidebar
from chandler.sharing import eim

class ChandlerApplication(runtime.Application):
    """The Chandler Application"""
    context.replaces(runtime.Application)
    sidebar_entries = trellis.make(trellis.Set, writable=True)

    top_level = trellis.make(trellis.Set)

runtime.Application <<= ChandlerApplication

class ChandlerFrame(core.Frame):
    model = trellis.make(trellis.Set, writable=True)

    @trellis.maintain
    def sidebar(self):
        return sidebar.Sidebar(scope=self, model=self.model)

def load_domain():
    """Load up the domain model for ChandlerApplication"""
    ChandlerApplication.sidebar_entries = trellis.Set(
            sidebar.SidebarEntry(collection=keyword.Keyword(name))
            for name in (u"Home", u"Work")
        )

def load_interaction(app):
    load_domain()

    # IM-specific stuff here
    app.top_level.add(ChandlerFrame(model=app.sidebar_entries,
                                    label=u'Chandler2 Demo'))

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
        ChandlerApplication.run(after=_headless)
    else:
        ChandlerApplication.run(after=runtime.use_wx_twisted)
