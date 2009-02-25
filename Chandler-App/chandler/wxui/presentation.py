import chandler.core as core
import chandler.wxui.image as image
from simplegeneric import generic
import wx
import peak.events.trellis as trellis
import peak.util.addons as addons

def load_wxui(app):
    """Code to hook up a wx UI to app's interaction model"""
    import chandler.wxui.table # big cheat
    for frame in app.top_level:
        core.present(frame, None)

class WxAddOn(addons.AddOn):
    widget = None

def _bind_to_choice(choice, tool):
    def handle_tool_event(event):
        choice.value = tool.ClientData.value
    WxAddOn(choice).widget.Bind(wx.EVT_TOOL, handle_tool_event, tool)

def _push_to_tool(choice):
    def set_value():
        value_id = WxAddOn(choice.chosen_item).widget.GetId()
        toolbar = WxAddOn(choice).widget
        toolbar.ToggleTool(value_id, True)

    return trellis.Performer(set_value)

@core.present.when_type(core.Choice)
def present_choice(choice_component, ui_parent=None):
    if isinstance(ui_parent, wx.ToolBar):
        WxAddOn(choice_component).widget = ui_parent
        for choice in choice_component.choices:
            icon_name = choice.hints.get('icon', 'ChandlerLogo')
            icon = image.get_image(icon_name, 'Chandler_App')
            tool = ui_parent.AddRadioLabelTool(-1, choice.label, icon, clientData=choice, shortHelp=choice.help)
            if tool is not None:
                WxAddOn(choice).widget = tool
                _bind_to_choice(choice_component, tool)
        choice_component.__performer__ = _push_to_tool(choice_component)

@core.present.when_type(core.Frame)
def present_frame(frame, ui_parent=None):
    wxframe = wx.Frame(None, -1, title=frame.label)
    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.SetMinSize((500, 300))
    
    splitter = wx.SplitterWindow(wxframe, -1, style=wx.SP_LIVE_UPDATE | wx.NO_BORDER | wx.SP_3DSASH)
    core.present(frame.sidebar, splitter)
    core.present(frame.dashboard, splitter)

    # Find all actions that want to be included in
    # the toolbar
    toolbar = None
    for cmd in frame:
        if cmd.hints.get('toolbar'):
            if toolbar is None:
                style = (wx.TB_HORIZONTAL |
                         getattr(wx, 'TB_MAC_NATIVE_SELECT', 0) |
                         wx.TB_3DBUTTONS | wx.TB_TEXT)
                toolbar = wxframe.CreateToolBar(style=style)
            core.present(cmd, toolbar)
    if toolbar is not None:
        toolbar.Realize()

    sizer.Add(splitter, 1, wx.EXPAND|wx.BOTTOM|wx.TOP)
    splitter.SplitVertically(splitter.Children[0], splitter.Children[1], 0.3 * sizer.MinSize.width)
    wxframe.SetSizer(sizer)
    wxframe.SetAutoLayout(True)
    sizer.Fit(wxframe)
    wxframe.Show()
    return frame
