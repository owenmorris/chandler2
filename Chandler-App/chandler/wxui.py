import chandler.core as core
from simplegeneric import generic
import wx

def load_wxui(app):
    """Code to hook up a wx UI to app's interaction model"""
    import chandler.wxui.table # big cheat
    for frame in app.top_level:
        core.present(frame, None)

@core.present.when_type(core.Frame)
def present_frame(frame, ui_parent=None):
    wxframe = wx.Frame(None, -1, title=frame.label)
    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.AddSpacer((0, 3))
    sizer.SetMinSize((200, 400))
    core.present_scope(frame, wxframe)
    for child in wxframe.Children:
        sizer.Add(child, 1, wx.EXPAND|wx.BOTTOM|wx.TOP)
    wxframe.SetSizer(sizer)
    wxframe.SetAutoLayout(True)
    sizer.Fit(wxframe)
    wxframe.Show()
    return frame
