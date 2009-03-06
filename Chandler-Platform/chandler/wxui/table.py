#   Copyright (c) 2003-2007 Open Source Applications Foundation
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.


import sys
import logging
import wx
import wx.grid as wxGrid

import peak.events.trellis as trellis
import peak.util.plugins as plugins
import chandler.core as core

#import Styles
#import DragAndDrop
#import PimBlocks
import chandler.wxui.multi_state as multi_state
import chandler.wxui.drawing as drawing
from chandler.wxui.image import get_image, get_raw_image

#
# Chandler1's version of wxPython has some enhancements
# (especially to wx.grid.Grid) that aren't present in
# the wxPythons that ship on many systems. So, we use
# the following global to check for this (until Chandler1's
# changes get accepted upstream).
#
EXTENDED_WX = hasattr(wxGrid.Grid, 'ScaleWidthToFit')

logger = logging.getLogger(__name__)

if __debug__:
    evtNames = {
        wx.wxEVT_ENTER_WINDOW: 'ENTER_WINDOW',
        wx.wxEVT_LEAVE_WINDOW: 'LEAVE_WINDOW',
        wx.wxEVT_LEFT_DOWN: 'LEFT_DOWN',
        wx.wxEVT_LEFT_UP: 'LEFT_UP',
        wx.wxEVT_LEFT_DCLICK: 'LEFT_DCLICK',
        wx.wxEVT_MIDDLE_DOWN: 'MIDDLE_DOWN',
        wx.wxEVT_MIDDLE_UP: 'MIDDLE_UP',
        wx.wxEVT_MIDDLE_DCLICK: 'MIDDLE_DCLICK',
        wx.wxEVT_RIGHT_DOWN: 'RIGHT_DOWN',
        wx.wxEVT_RIGHT_UP: 'RIGHT_UP',
        wx.wxEVT_RIGHT_DCLICK: 'RIGHT_DCLICK',
        wx.wxEVT_MOTION: 'MOTION',
        wx.wxEVT_MOUSEWHEEL: 'MOUSEWHEEL',
    }

def GetRectFromOffsets(rect, offsets):
    def GetEdge(rect, offset):
        if offset >= 0:
            edge = rect.GetLeft()
        else:
            edge = rect.GetRight()
        return edge + offset

    top = rect.GetTop()
    height = offsets[2]
    if height == 0:
        height = rect.GetHeight()
    else:
        top = top + (rect.GetHeight() - height) / 2.0
    left = GetEdge(rect, offsets[0])
    return wx.Rect(left,
                    top,
                    GetEdge(rect, offsets[1]) - left,
                    height)


class TablePresentation(trellis.Component, wxGrid.PyGridTableBase):
    table = trellis.make(core.Table, writable=True)

    @trellis.perform
    def update_column_selection(self):
        for index, column in enumerate(self.table.columns):
            if column is self.table.sort_column:
                show_arrows = column.hints.get('sort_arrows', True)
                self.View.SetSelectedCol(index)
                self.View.SetUseColSortArrows(show_arrows)
                self.View.SetColSortAscending(self.table.items.reverse)
                break

    @trellis.perform
    def update_grid(self):
        view = self.GetView()

        view.BeginBatch()
        for start, end, newLen in self.table.items.changes:
            oldLen = end - start
            if newLen == oldLen:
                view.ProcessTableMessage(wxGrid.GridTableMessage(self,
                                  wxGrid.GRIDTABLE_REQUEST_VIEW_GET_VALUES,
                                  start, oldLen))
            elif newLen > oldLen:
                if oldLen > 0:
                    view.ProcessTableMessage(wxGrid.GridTableMessage(self,
                                      wxGrid.GRIDTABLE_REQUEST_VIEW_GET_VALUES,
                                      start, oldLen))
                view.ProcessTableMessage(wxGrid.GridTableMessage(self,
                                  wxGrid.GRIDTABLE_NOTIFY_ROWS_INSERTED,
                                  start + oldLen, newLen - oldLen))
            else:
                view.ProcessTableMessage(wxGrid.GridTableMessage(self,
                                  wxGrid.GRIDTABLE_NOTIFY_ROWS_DELETED,
                                  start + newLen, oldLen - newLen))
                if newLen > 0:
                    view.ProcessTableMessage(wxGrid.GridTableMessage(self,
                                      wxGrid.GRIDTABLE_REQUEST_VIEW_GET_VALUES,
                                      start, newLen))
        view.EndBatch()

        for row in view.GetSelectedRows():
            index = self.RowToIndex(row)
            if not self.table.items[index] in self.table.selection:
                trellis.on_commit(view.DeselectRow, index)

        for index, item in enumerate(self.table.items):
            row = self.IndexToRow(index)
            if item in self.table.selection:
                trellis.on_commit(view.SelectRow, index, True)

    defaultRWAttribute = wxGrid.GridCellAttr()
    defaultROAttribute = wxGrid.GridCellAttr()
    defaultROAttribute.SetReadOnly(True)

    def __init__(self, grid, **kw):
        wxGrid.PyGridTableBase.__init__(self)
        trellis.Component.__init__(self, **kw)

        grid.SetTable(self, selmode=wxGrid.Grid.SelectRows)
        self.SetView(grid)

        if self.table.hints.get('column_headers'):
            grid.SetColLabelSize(wxGrid.GRID_DEFAULT_COL_LABEL_HEIGHT)
        else:
            grid.SetColLabelSize(0)

        for index, column in enumerate(self.table.columns or ()):
            grid.SetColLabelValue(index, column.label)
            grid.SetColSize(index, column.hints.get('width', 120))

            if EXTENDED_WX:
                scaleColumn = grid.GRID_COLUMN_SCALABLE if column.hints.get('scalable') else grid.GRID_COLUMN_NON_SCALABLE
                grid.ScaleColumn(index, scaleColumn)

        grid.Bind(wxGrid.EVT_GRID_RANGE_SELECT, self.OnRangeSelect)
        grid.Bind(wxGrid.EVT_GRID_LABEL_LEFT_CLICK, self.OnLabelLeftClicked)
        grid.Bind(wxGrid.EVT_GRID_SELECT_CELL, lambda event: None)

    def GetNumberRows(self):
        return len(self.table.items)

    def GetNumberCols(self):
        return len(self.table.columns)

    def RowToIndex(self, row):
        return row

    def IndexToRow(self, index):
        return index

    def RangeToIndex(self, startRow, endRow):
        """
        Translasted a row range in the grid to a row range in the collection
        """
        return self.RowToIndex(startRow), self.RowToIndex(endRow)

    def IsEmptyCell(self, row, col):
        return False

    def CanClick(self, row, col):
        column = self.table.columns[col]
        return column.action is not None

    def OnClick(self, row, col):
        selection = [self.table.items[self.RowToIndex(row)]]
        self.table.columns[col].action(selection)

    def TrackMouse(self, row, col):
        return False

    def GetToolTipString(self, row, col):
        pass

    def ReadOnly(self, row, col):
        return False

    def GetValue(self, row, col):
        return self.table.get_cell_value((row, col))

    def SetValue(self, row, col, value):
        self.table.items[self.RowToIndex(row)].displayName = value

    def GetColLabelValue(self, col):
        return self.table.columns[col].label

    def GetColLabelBitmap(self, col):
        return getattr(self.table.columns[col], 'bitmap', None)

    _deselected_all = False

    def OnRangeSelect(self, event):
        """
        Synchronize the grid's selection back into the Table
        """
        firstRow = event.TopRow
        lastRow = event.BottomRow
        indexStart, indexEnd = self.RangeToIndex(firstRow, lastRow)
        selecting = event.Selecting()

        if (not selecting and firstRow == 0 and lastRow != 0
            and lastRow == self.GetNumberRows() - 1):
            # this is a special "deselection" event that the
            # grid sends us just before selecting another
            # single item. This happens just before a user
            # simply clicks from one item to another.
            self._deselected_all = True

            # [@@@] grant: Need to avoid broadcasting a
            # selection change in this case.
            return

        if selecting and self.table.single_item_selection:
            new_selection = self.table.items[indexEnd]
            if self.table.selected_item != new_selection:
                self.table.selected_item = new_selection
        else:
            items = set(self.table.items[index]
                        for index in xrange(indexStart, indexEnd + 1))

            if selecting:
                if self._deselected_all:
                    self.table.new_selection = items
                else:
                    items.difference_update(self.table.selection)
                    self.table.selection.update(items)
            else:
                self.table.selection.difference_update(items)

        if self._deselected_all:
            del self._deselected_all

        event.Skip()

    def SelectedRowRanges(self):
        # @@@ [grant] Move this (or something similar) to Table
        """
        Uses IndexRangeToRowRange to convert the selected indexes to
        selected rows
        """
        lastRow = None
        # This is O(N) tsk
        for index, item in enumerate(self.table.items):
            itemSelected = (item in self.table.selection)

            if itemSelected:
                if lastRow is None:
                    lastRow = self.IndexToRow(index)
                else:
                    pass
            elif lastRow is not None:
                yield lastRow, self.IndexToRow(index-1)
                lastRow = None

        if lastRow is not None:
            yield lastRow, self.IndexToRow(len(self.table.items) - 1)

    def OnLabelLeftClicked(self, event):
        assert (event.GetRow() == -1) # Currently Table only supports column headers
        column = self.table.columns[event.GetCol()]
        # A "receiver" style cell: it will take care of toggling
        # the sort, etc.
        self.table.select_column = column

    def GetTypeName(self, row, column):
        return self.table.columns[column].hints.get('type', 'String')

    def GetAttr(self, row, column, kind):
        attribute = super(TablePresentation, self).GetAttr(row, column, kind)
        if attribute is None:
            attribute = self.defaultROAttribute
            grid = self.GetView()

            if (not self.table.columns[column].hints.get('readonly', False) and
                not self.ReadOnly(row, column)):
                attribute = self.defaultRWAttribute
            attribute.IncRef()
        return attribute

class Table(wxGrid.Grid):

    overRowCol = None
    clickRowCol = None

    if wx.Platform == "__WXMAC__":
        defaultStyle = wx.BORDER_SIMPLE
    else:
        defaultStyle = wx.BORDER_STATIC

    TABLE_EXTENSIONS = plugins.Hook('chandler.wxui.table.extensions')

    def __init__(self, parent, tableData, *arguments, **keywords):
        super(Table, self).__init__(parent, style=self.defaultStyle, *arguments, **keywords)

        # Register extensions
        self.RegisterDataType('String', StringRenderer(), None)
        self.TABLE_EXTENSIONS.notify(self)
        # Generic table setup
        self.SetColLabelAlignment(wx.ALIGN_CENTRE, wx.ALIGN_CENTRE)
        self.SetRowLabelSize(0)
        self.SetColLabelSize(0)
        self.AutoSizeRows()
        self.DisableDragRowSize()
        self.SetDefaultCellBackgroundColour(wx.WHITE)
        if EXTENDED_WX:
            self.ScaleWidthToFit(True)
            self.EnableCursor(False)
        # The following disables drawing a black box around the
        # last-clicked cell.
        self.SetCellHighlightPenWidth(0)
        self.SetLightSelectionBackground()
        self.SetUseVisibleColHeaderSelection(True)
        self.SetScrollLineY(self.GetDefaultRowSize())
        self.EnableGridLines(False) # should customize based on hints
        # wxSidebar is subclassed from wxTable and depends on the binding of
        # OnLoseFocus so it can override OnLoseFocus in wxTable
        self.Bind(wx.EVT_KILL_FOCUS, self.OnLoseFocus)
        self.Bind(wx.EVT_SET_FOCUS, self.OnGainFocus)
        # @@@ [grant] Not sure we need to support [Enter] to edit, which
        # is what the following binding is for
        #self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind(wxGrid.EVT_GRID_CELL_BEGIN_DRAG, self.OnItemDrag)

        gridWindow = self.GetGridWindow()
        # wxSidebar is subclassed from wxTable and depends on the binding of
        # OnMouseEvents so it can override OnMouseEvents in wxTable
        gridWindow.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouseEvents)
        gridWindow.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self.OnMouseCaptureLost)
        # It appears that wxGrid gobbles all the mouse events so we never get
        # context menu events. So bind right down to the context menu handler
        #gridWindow.Bind(wx.EVT_RIGHT_DOWN, wx.GetApp().OnContextMenu)

        if not EXTENDED_WX:
            # Use of GetGridColLabelWindow() and triangle drawing code below
            # from:
            #    <http://wiki.wxpython.org/index.cgi/DrawingOnGridColumnLabel>
            # trap the column label's paint event:
            columnLabelWindow = self.GetGridColLabelWindow()
            columnLabelWindow.Bind(wx.EVT_PAINT, self.OnColumnHeaderPaint)

    if not EXTENDED_WX:
        _use_visible_col_header = False
        _selected_col = -1
        _ascending_arrows = False

        def GetUseVisibleColHeaderSelection(self, use):
            return self._use_visible_col_header

        def SetUseVisibleColHeaderSelection(self, use):
            self._use_visible_col_header = use
            self.GetGridColLabelWindow().Refresh()

        def GetSelectedCol(self):
            return self._selected_col

        def SetSelectedCol(self, colnum):
            self._selected_col = colnum
            self.GetGridColLabelWindow().Refresh()

        def GetColSortDescending(self):
            return self._ascending_arrows

        def SetColSortAscending(self, ascending):
            self._ascending_arrows = ascending
            self.GetGridColLabelWindow().Refresh()

        def GetUseColSortArrows(self):
            return self._use_sort_arrows

        def SetUseColSortArrows(self, useArrows):
            self._use_sort_arrows = useArrows
            self.GetGridColLabelWindow().Refresh()

        def OnColumnHeaderPaint(self, event):
            event.Skip() # Let the regular paint handler do its thing

            if self._use_visible_col_header or self._use_sort_arrows:

                w = event.EventObject
                dc = wx.PaintDC(w)
                clientRect = w.GetClientRect()
                font = dc.GetFont()

                # For each column, draw its rectangle, its column name,
                # and its sort indicator, if appropriate:
                totColSize = -self.GetViewStart()[0]*self.GetScrollPixelsPerUnit()[0] # Thanks Roger Binns
                for col in range(self.GetNumberCols()):
                    colSize = self.GetColSize(col)
                    rect = (totColSize, 0, colSize, w.GetSize().height)
                    totColSize += colSize

                    if col == self._selected_col:
                        # draw a triangle, pointed up or down, at the
                        # top left of the column.
                        if self._use_sort_arrows:
                            left = rect[0] + 3
                            top = rect[1] + 3

                            dc.SetBrush(wx.Brush(wx.BLACK, wx.SOLID))
                            if self._ascending_arrows:
                                dc.DrawPolygon([(left,top), (left+6,top), (left+3,top+4)])
                            else:
                                dc.DrawPolygon([(left+3,top), (left+6, top+4), (left, top+4)])
                        if self._use_visible_col_header:
                            dc.SetBrush(wx.Brush(wx.BLACK, wx.SOLID))
                            dc.DrawRectangle(rect[0] + 4, rect[3] - 4, colSize - 8, 2)

    def Destroy(self):
        # Release the mouse capture, if we had it
        if getattr(self, 'mouseCaptured', False):
            delattr(self, 'mouseCaptured')
            gridWindow = self.GetGridWindow()
            if gridWindow.HasCapture():
                #logger.debug("wxDashboard.Destroy: ReleaseMouse")
                gridWindow.ReleaseMouse()
            #else:
                #logger.debug("wxDashboard.Destroy: would ReleaseMouse, but not HasCapture.")

        return super(Table, self).Destroy()

    def displayContextMenu(self, event):
        """
        (column, row) = self.__eventToCell(event)
        selectedItemIndex = self.RowToIndex(row)
        blockItem = self.blockItem
        if selectedItemIndex != -1:
            # if the row in question is already selected, don't change selection
            itemRange = (selectedItemIndex, selectedItemIndex)
            if not blockItem.contents.isSelected(itemRange):
                blockItem.contents.setSelectionRanges([itemRange])
                blockItem.PostSelectItems()
            # Update the screen before showing the context menu
            theApp = wx.GetApp()
            theApp.propagateAsynchronousNotifications()
            theApp.Yield(True)
        """
        super(Table, self).displayContextMenu(event)

    def OnGainFocus(self, event):
        self.SetSelectionBackground(wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT))
        self.InvalidateSelection()

    def OnLoseFocus(self, event):
        self.SetLightSelectionBackground()
        self.InvalidateSelection()

    def OnKeyDown(self, event):

        # default grid behavior is to move to the "next" cell,
        # whatever that may be. We want to edit instead.
        if event.GetKeyCode() == wx.WXK_RETURN:
            defaultEditableAttribute = self.defaultEditableAttribute
            if defaultEditableAttribute is not None:
                self.EditAttribute(defaultEditableAttribute)
                return

        # other keys should just get propagated up
        event.Skip()

    def SetLightSelectionBackground(self):
        background = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
        background.Set((background.Red() + 255) / 2,
                        (background.Green() + 255) / 2,
                         (background.Blue() + 255) / 2)
        self.SetSelectionBackground(background)

    def InvalidateSelection(self):
        numColumns = self.GetNumberCols()

        for rowStart, rowEnd in self.Table.SelectedRowRanges():
            dirtyRect = self.GetRectForCellRange(rowStart, 0,
                                                 rowEnd - rowStart + 1, numColumns)
            self.RefreshRect(dirtyRect)

    def GetRectForCellRange(self, startRow, startCol, numRows=1, numCols=1):
        resultRect = self.CellToRect(startRow, startCol)

        if numRows > 1 or numCols > 1:
            endRect = self.CellToRect(startRow + numRows - 1,
                                      startCol + numCols - 1)
            resultRect.SetTopRight(endRect.GetTopRight())

        resultRect.OffsetXY(self.GetRowLabelSize(), self.GetColLabelSize())
        left, top = self.CalcScrolledPosition(resultRect.GetLeft(), resultRect.GetTop())
        resultRect.SetLeft(left)
        resultRect.SetTop(top)
        return resultRect

    def __eventToRowCol(self, event):
        """ return the cell coordinates for the X & Y in this event """
        x = event.GetX()
        y = event.GetY()
        unscrolledX, unscrolledY = self.CalcUnscrolledPosition(x, y)
        row = self.YToRow(unscrolledY)
        col = self.XToCol(unscrolledX)
        return (row, col)

    def RebuildSections(self):
        # If sections change, forget that we were over a cell.
        self.overRowCol = None

    def OnMouseEvents(self, event):
        """
          This code is tricky, tread with care -- DJA
        """
        event.Skip() #Let the grid also handle the event by default

        gridWindow = self.GetGridWindow()

        x = event.GetX()
        y = event.GetY()

        unscrolledX, unscrolledY = self.CalcUnscrolledPosition(x, y)
        row = self.YToRow(unscrolledY)
        col = self.XToCol(unscrolledX)
        toolTipString = None
        oldOverRowCol = self.overRowCol
        outsideGrid = (-1 in (row, col))

        refreshRowCols = set()

        if outsideGrid:
            self.overRowCol = None

        if event.LeftUp():
            refreshRowCols.add(self.clickRowCol)
            refreshRowCols.add(oldOverRowCol)

            if self.clickRowCol == (row, col):
                self.Table.OnClick(row, col)
            self.overRowCol = None
            self.clickRowCol = None

        elif event.LeftDClick():
            # Stop hover if we're going to edit
            self.overRowCol = None

        elif event.LeftDown() and not outsideGrid:
            refreshRowCols.add(oldOverRowCol)
            if self.Table.CanClick(row, col):
                self.clickRowCol = self.overRowCol = row, col
                event.Skip(False) # Gobble the event
                refreshRowCols.add(self.clickRowCol)
                if not gridWindow.HasCapture():
                    gridWindow.CaptureMouse()
                self.SetFocus()
            else:
                self.overRowCol = None

        elif self.clickRowCol is not None:
            if not outsideGrid:
                self.overRowCol = row, col
            event.Skip(False) # Gobble the event


        elif not event.LeftIsDown() and (self.overRowCol != row, col):
            toolTipString = self.Table.GetToolTipString(row, col)
            if self.GetTable().TrackMouse(row, col):
                self.overRowCol = row, col
            else:
                self.overRowCol = None

        if toolTipString:
            gridWindow.SetToolTipString(toolTipString)
            gridWindow.GetToolTip().Enable(True)
        else:
            toolTip = gridWindow.GetToolTip()
            if toolTip:
                toolTip.Enable(False)
                gridWindow.SetToolTip(None)

        if self.overRowCol != oldOverRowCol:
            refreshRowCols.add(oldOverRowCol)
            refreshRowCols.add(self.overRowCol)

            if (self.overRowCol, self.clickRowCol) == (None, None):
                if (gridWindow.HasCapture()):
                    gridWindow.ReleaseMouse()

        for cell in refreshRowCols:
            if cell is not None:
                self.RefreshRect(self.GetRectForCellRange(*cell))

    def OnMouseCaptureLost(self, event):
        if hasattr(self, 'mouseCaptured'):
            #logger.debug("OnMouseCaptureLost: forgetting captured.")
            del self.mouseCaptured


    def OnItemDrag(self, event):

        # To fix bug 2159, tell the grid to release the mouse now because the
        # grid object may get destroyed before it has a chance to later on:
        gridWindow = self.GetGridWindow()
        if gridWindow.HasCapture():
            gridWindow.ReleaseMouse()

        event.Skip()

    def IndexRangeToRowRange(self, indexRanges):
        """
        Given a list of index ranges, [(a,b), (c,d), ...], generate
        corresponding row ranges[(w,x), (y, z),..]

        Eventually this will need to get more complex when
        IndexToRow() returns multiple rows
        """
        for (indexStart, indexEnd) in indexRanges:
            topRow = self.IndexToRow(indexStart)
            bottomRow = self.IndexToRow(indexEnd)

            # not sure when the -1 case would happen?
            if -1 not in (topRow, bottomRow):
                yield (topRow, bottomRow)

class StringRenderer(wxGrid.PyGridCellRenderer):
    def Draw(self, grid, attr, dc, rect, row, col, isSelected):
        drawing.SetTextColorsAndFont(grid, attr, dc, isSelected)

        dc.SetBackgroundMode(wx.SOLID)
        dc.SetPen(wx.TRANSPARENT_PEN)

        dc.DrawRectangleRect(rect)

        dc.SetFont(attr.GetFont())
        text = unicode(grid.Table.GetValue(row, col))
        dc.SetClippingRect(rect.Get())
        drawing.DrawClippedTextWithDots(dc, text, rect)
        dc.DestroyClippingRegion()

class IconRenderer(wxGrid.PyGridCellRenderer):
    """
    Utility class for displaying an icon in a table column. It's
    loosely based on the old IconAttributeEditor.
    """
    bitmapCache = None
    bitmapProvider = staticmethod(get_image)

    def __init__(self, **kw):
        super(IconRenderer, self).__init__()
        bitmapCache = kw.pop('bitmapCache', None)

        if bitmapCache is not None:
            self.bitmapCache = bitmapCache

        if self.bitmapCache is None:
            cls = type(self)
            cls.bitmapCache = multi_state.MultiStateBitmapCache()
            cls.bitmapCache.AddStates(multibitmaps=list(self.getStateInfos()),
                                      bitmapProvider=self.bitmapProvider)

    ROLLED_OVER = 1
    SELECTED = 2
    MOUSE_DOWN = 4
    READ_ONLY = 8
    VARIATION_MAP = {
        0 : 'normal',
        ROLLED_OVER: 'rollover',
        SELECTED: 'selected',
        SELECTED | ROLLED_OVER: 'rolloverselected',
        MOUSE_DOWN: 'normal', # note, this is the not-rollover case: mouse out
        MOUSE_DOWN | ROLLED_OVER: 'mousedown', # mouse in
        MOUSE_DOWN | SELECTED: 'selected',
        MOUSE_DOWN | SELECTED | ROLLED_OVER: 'mousedownselected',
        # @@@ Change these if we need special read/only icons
        READ_ONLY: "normal",
        READ_ONLY | ROLLED_OVER: "normal",
        READ_ONLY | SELECTED: "selected",
        READ_ONLY | SELECTED | ROLLED_OVER: 'selected',
        READ_ONLY | MOUSE_DOWN: 'normal',
        READ_ONLY | MOUSE_DOWN | ROLLED_OVER: 'normal',
        READ_ONLY | MOUSE_DOWN | SELECTED: 'selected',
        READ_ONLY | MOUSE_DOWN | SELECTED | ROLLED_OVER: 'selected',
    }

    def getStateInfos(self):
        """
        Return an iterable of all the multi_state.BitmapInfos you
        want to use for your icon states.
        """
        return ()

    def getVariation(self, readOnly, isSelected, mouseDown, mouseOver):
        bits = ((self.READ_ONLY if readOnly else 0) |
                (self.MOUSE_DOWN if mouseDown else 0) |
                (self.ROLLED_OVER if mouseOver else 0) |
                (self.SELECTED if isSelected else 0))
        return self.VARIATION_MAP[bits]

    def mapValueToIconState(self, value):
        """
        """
        # By default, we use the value as the icon state as-is.
        return value

    def advanceValue(self, value):
        return value

    def Draw(self, grid, attr, dc, rect, row, col, isSelected):
        drawing.SetTextColorsAndFont(grid, attr, dc, isSelected)

        dc.SetBackgroundMode(wx.SOLID)
        dc.SetPen(wx.TRANSPARENT_PEN)

        dc.DrawRectangleRect(rect)

        dc.SetBackgroundMode(wx.TRANSPARENT)

        value = grid.Table.GetValue(row, col)

        mouseDown = (row, col) == grid.clickRowCol
        if mouseDown:
            value = self.advanceValue(value)

        state = self.mapValueToIconState(value)

        mouseOver = mouseDown or (row, col) == grid.overRowCol
        variation = self.getVariation(False, isSelected, mouseDown, mouseOver)

        imageSet = self.bitmapCache[state]

        image = getattr(imageSet, variation, None)

        assert image is not None, "Bogus image for state %s variation %s" % (
                                  state, variation)

        x, y, w, h = rect.Get()
        x += (w - image.GetWidth()) / 2
        y += (h - image.GetHeight()) / 2
        dc.DrawBitmap(image, x, y, True)

#
# This should be handled via some kind of hook. Otherwise,
# you need to import chandler.wxui.table if you want to
# render a Table as a wx grid!
#

@core.present.when_type(core.Table)
def render_table(table, parent=None):
    wxobj = Table(parent, -1)
    data_source = TablePresentation(wxobj, table=table)
    return wxobj
