import peak.events.trellis as trellis
import chandler.core as core
import chandler.event as event
import itertools

class SidebarEntry(trellis.Component):
    _ITER_HUES = itertools.cycle((210, 120, 0, 30, 50, 300, 170, 330, 270))
    _ITER_SORT_KEY = itertools.count(1)

    @trellis.make(writable=True, optional=False)
    def sort_key(self):
        return self._ITER_SORT_KEY.next()

    @trellis.make(writable=True, optional=False)
    def hsv_color(self):
        return (self._ITER_HUES.next(), 0, 0)

    @trellis.make(writable=True)
    def collection(self):
        return core.Collection()

    checked = trellis.attr(False)

    def __repr__(self):
        return u"<%s(%s) at 0x%x>" % (type(self).__name__,
                                      self.collection.title,
                                      id(self))

    def __cmp__(self, other):
        if isinstance(other, SidebarEntry):
            return cmp(self.sort_key, other.sort_key)
        else:
            return super(SidebarEntry, self).__cmp__(other)

class Sidebar(core.Table):
    @trellis.maintain
    def icon_column(self):
        return core.TableColumn(scope=self, label=u'Icon',
            get_value=lambda entry: (entry.hsv_color, entry.checked),
            hints={'type':'SidebarIcon', 'width':20})

    @trellis.maintain
    def name_column(self):
        return core.TableColumn(scope=self, label=u'Name',
            get_value=lambda entry:entry.collection.title)

    @trellis.make
    def columns(self):
        return trellis.List([self.icon_column, self.name_column])

    @trellis.make
    def filtered_items(self):
        return core.FilteredSubset(
            input=trellis.Cell(lambda: self.selected_item.collection.items),
            predicate=trellis.Cell(lambda:self.filters.value))

    @trellis.maintain
    def filters(self):
        # need to add a hook for the choices
        return core.Choice(
            scope=self,
            choices=trellis.List([
                core.ChoiceItem(
                    label=u'All',
                    help=u'View all items',
                    value=lambda item: True),
                core.ChoiceItem(
                    label=u'Calendar',
                    help=u'View events',
                    value=event.Event.installed_on),
            ])
        )


def load_interaction(app):
    app.sidebar = Sidebar(model=app.collections)

import wx
import chandler.wxui.table as table
import chandler.wxui.drawing as drawing
from chandler.wxui.image import get_raw_image

class SidebarIconRenderer(table.wxGrid.PyGridCellRenderer):
    def Draw(self, grid, attr, dc, rect, row, col, isSelected):
        drawing.SetTextColorsAndFont(grid, attr, dc, isSelected)

        dc.SetBackgroundMode(wx.SOLID)
        dc.SetPen(wx.TRANSPARENT_PEN)

        dc.DrawRectangleRect(rect)

        dc.SetBackgroundMode(wx.TRANSPARENT)

        """
        Find the image to draw, and draw it!
        """
        #(imagePrefix, iconName, checked,
        # mouseOver, mouseDown, hue, deactive) = grid.Table.GetValue(row, col)

        hsv, checked = grid.Table.GetValue(row, col)
        imagePrefix = "SidebarIcon"
        iconName = ""
        hue = hsv[0]
        deactive = False

        mouseDown = (row, col) == grid.clickRowCol
        mouseOver = not mouseDown and ((row, col) == grid.overRowCol)

        if mouseDown:
            mouseState = "MouseDown"
        elif mouseOver:
            mouseState = "MouseOver"
        else:
            mouseState = ""

        imageFilename = "%s%s%s%s%s.png" % (
                            imagePrefix,
                            "Checked" if checked else "",
                            iconName,
                            mouseState,
                            "Deactive" if deactive else "")

        image = get_raw_image(imageFilename, "Chandler_App")

        if not None in (image, hue):
            image.RotateHue(float(hue) / 360.0)


        if image is not None:
            image = wx.BitmapFromImage(image)
            imageRect = table.GetRectFromOffsets(rect, [0,21,19])
            dc.DrawBitmap(image, imageRect.GetLeft(), imageRect.GetTop(), True)
        
    def Clone():
        return type(self)()
        
    def GetBestSize(self, grid, attr, dc, row, col):
        return wx.Size(20, 20) # @@@ [grant]

def extend_table(table):
    table.RegisterDataType("SidebarIcon", SidebarIconRenderer(), None)
