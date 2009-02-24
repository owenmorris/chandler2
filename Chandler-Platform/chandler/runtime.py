"""Start up an application/event loop"""

__all__ = [
    'use_wx_twisted', 'use_twisted', 'Application',
    'APP_START', 'REACTOR_INIT', 'WXUI_START',
]
from peak.events import trellis, activity
from peak.util import plugins
import peak.context as context

APP_START    = plugins.Hook('chandler.launch.app')
REACTOR_INIT = plugins.Hook('chandler.launch.reactor')
WXUI_START   = plugins.Hook('chandler.launch.wxui')
APP_SHUTDOWN = plugins.Hook('chandler.shutdown.app')

class Application(plugins.Extensible, trellis.Component, context.Service):
    """Base class for applications"""

    extend_with = APP_START

    def run(self, before=(), after=()):
        """Run app, loading `before` and `after` hooks around ``APP_START``"""
        self.extend_with = before, self.extend_with, after
        self.load_extensions()
        try:
            activity.EventLoop.run()
        finally:
            APP_SHUTDOWN.notify()

def use_wx_twisted(app):
    """Run `app` with a wx+Twisted event loop"""
    import wx, sys

    # ugh, Twisted is kinda borken for wx; it uses old-style names exclusively
    sys.modules['wxPython'] = sys.modules['wxPython.wx'] = wx
    wx.wxApp = wx.App
    wx.wxCallAfter = wx.CallAfter
    wx.wxEventLoop = wx.EventLoop
    wx.NULL = None
    wx.wxFrame = wx.Frame

    from twisted.internet import wxreactor
    wxreactor.install().registerWxApp(wx.GetApp() or wx.PySimpleApp())
    use_twisted(app)
    WXUI_START.notify(app)

def use_twisted(app):
    """Run `app` with a Twisted event loop"""
    activity.EventLoop <<= activity.TwistedEventLoop
    REACTOR_INIT.notify(app)





































