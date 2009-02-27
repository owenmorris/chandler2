import optparse
import peak.events.trellis as trellis
import peak.context as context
from peak.util import plugins
from chandler import runtime, core, keyword
import chandler.sidebar as sidebar
import chandler.dashboard as dashboard
from os.path import isfile, expanduser

EIM_PERSISTENCE_FILE = expanduser("~/chandler2.chex.gz")

class ChandlerApplication(runtime.Application):
    """The Chandler Application"""
    context.replaces(runtime.Application)
    sidebar_entries = trellis.make(trellis.Set, writable=True)

    top_level = trellis.make(trellis.Set)

def useChandlerApplication():
    runtime.Application <<= ChandlerApplication

useChandlerApplication()

class ChandlerFrame(core.Frame):
    model = trellis.make(trellis.Set, writable=True)

    @trellis.maintain
    def sidebar(self):
        return sidebar.Sidebar(scope=self, model=self.model)

    @trellis.maintain
    def dashboard(self):
        return dashboard.Dashboard(scope=self, model=dashboard.AppEntryAggregate(input=self.sidebar.filtered_items))

def load_domain():
    """Load up the domain model for ChandlerApplication"""
    if not isfile(EIM_PERSISTENCE_FILE):
        ChandlerApplication.sidebar_entries = trellis.Set(
                sidebar.SidebarEntry(collection=keyword.Keyword(name))
                for name in (u"Home", u"Work")
            )
    else:
        from chandler.sharing import dumpreload
        dumpreload.reload(EIM_PERSISTENCE_FILE, gzip=True)

def load_interaction(app):
    load_domain()

    # IM-specific stuff here
    app.top_level.add(ChandlerFrame(model=app.sidebar_entries,
                                    label=u'Chandler2 Demo'))

def uuids_to_export():
    """Add the EIM extension to sidebar_entries, return uuids to export."""
    from chandler.sharing import eim
    uuids = []
    for entry in ChandlerApplication.sidebar_entries:
        eim_entry = eim.EIM(entry.collection)
        if not eim.EIM.installed_on(entry.collection):
            eim_entry.add()
        uuids.append(eim_entry.well_known_name or eim_entry.uuid)
        for item in entry.collection.items:
            # this exports items in the collections, but not modifications
            eim_item = eim.EIM(item)
            if not eim.EIM.installed_on(eim_item):
                eim_item.add()
            uuids.append(eim_item.uuid)
    return uuids

def save_all(*args):
    from chandler.sharing import dumpreload
    if isfile(EIM_PERSISTENCE_FILE):
        dumpreload.overwrite_rename(EIM_PERSISTENCE_FILE,
                                    EIM_PERSISTENCE_FILE + '~')
    dumpreload.dump_to_path(EIM_PERSISTENCE_FILE, uuids_to_export(), gzip=True)

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
    parser.add_option("-s", "--save",     action="store_true", dest="save",
                      help="Save data on quit to %s" % EIM_PERSISTENCE_FILE)

    options, arguments = parser.parse_args()
    if options.save:
        plugins.Hook('chandler.shutdown.app').register(save_all)

    if options.headless:
        ChandlerApplication.run(after=_headless)
    else:
        ChandlerApplication.run(after=runtime.use_wx_twisted)
