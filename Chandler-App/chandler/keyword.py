import peak.events.trellis as trellis
from peak.util.addons import AddOn
from weakref import ref

_keywords = {}

class _Keyword(trellis.Component):
    word = trellis.attr()
    items = trellis.make(trellis.Set)

    def __init__(self, word, **kwds):
        self.word = word
        super(_Keyword, self).__init__(**kwds)

    def __repr__(self):
        return "<Keyword: %s>" % self.word

    def add(self, item):
        self.items.add(item)
        ItemKeywords(item).keyword_strings.add(self)

    def remove(self, item):
        self.items.remove(item)
        ItemKeywords(item).keyword_strings.remove(self)

    @trellis.compute
    def title(self):
        return "Tag: %s" % self.word

# factory to produce _Keyword objects since strings aren't
# weak-referencable and thus AddOns won't work cleanly
def Keyword(word):
    try:
        return _keywords[word]()
    except KeyError:
        keyword = _Keyword(word)
        def del_keyword_ref(weak):
            del _keywords[word]
        _keywords[word] = ref(keyword, del_keyword_ref)
        return keyword

class ItemKeywords(AddOn, trellis.Component):
    trellis.attrs(
        _item=None,
    )

    keyword_strings = trellis.make(trellis.Set)

    def __init__(self, item, **kwargs):
        self._item = item

