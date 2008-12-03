from peak.events import trellis
import sys

__all__ = ['inherited_attrs']

def inherited_attrs(**attrs):
    """Like trellis.attrs, but creates maintain rules that handle recurrence."""
    frame = sys._getframe(1)
    for k, v in attrs.items():
        if k in frame.f_locals:
            raise TypeError("%s is already defined in this class" % (k,))
        rule = get_inherit_rule(k)
        frame.f_locals[k] = trellis.CellAttribute.mkattr(v, __name__=k, rule=rule)

def get_inherit_rule(name):
    def func(add_on):
        return inherited_value(add_on, name)
    func.__name__ = name
    return func


def inherited_value(add_on, name):
    from chandler.event import Event
    from chandler.recurrence import Occurrence
    if isinstance(add_on, Occurrence):
        cls = None
        item = add_on
    else:
        cls = type(add_on)
        item = add_on._item

    if not isinstance(item, Occurrence):
        return getattr(add_on, name)
    else:
        recipe = item.modification_recipe
        key = cls, name
        if recipe and key in recipe.changes:
            return recipe.changes[key].value
        if cls == Event and name == 'base_start':
            return item.recurrence_id
        else:
            master = item.master if cls is None else cls(item.master)
            return getattr(master, name)
