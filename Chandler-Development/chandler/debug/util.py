import peak.events.trellis as trellis

class Viewer(trellis.Component):
    """
    A utility class, usually used to observe changes to a cell during
    doctests. This should probably eventually move to a Chandler-Debug
    plugin.
    """
    component = trellis.attr(None)
    cell_name = trellis.attr(None)

    @trellis.compute
    def formatted_name(self):
        return self.cell_name

    @trellis.perform
    def view_it(self):
        value = getattr(self.component, self.cell_name, None)
        if None not in (self.component, self.cell_name, value):
            print "%s changed to: %s" % (self.formatted_name, value)

