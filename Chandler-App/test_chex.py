import unittest
import datetime
import os
from chandler.core import Item, Collection
from chandler.event import Event
from chandler.time_services import TimeZone
from chandler.sharing.dumpreload import reload, dump
from chandler.sharing.eim import _items_by_uuid, get_item_for_uuid
from chandler.sharing.translator import str_uuid_for
import pkg_resources

class ChexTestCase(unittest.TestCase):
    """Extra tests beyond what's useful in the doctests."""

    def setUp(self):
        _items_by_uuid.clear()

    event_uuid = 'a70c4ba4-dddb-11dd-9dd8-001b63a98e6f'
    work_collection_uuid = 'a675af96-dddb-11dd-9dd8-001b63a98e6f'
    jan_ninth = datetime.datetime(2009, 1, 9, tzinfo=TimeZone.floating)
    tmp_path = 'test_output.tmp'

    def _load(self, name):
        return pkg_resources.resource_stream(__name__, name)

    def _after_import_tests(self):
        item = get_item_for_uuid(self.event_uuid)
        work_collection = get_item_for_uuid(self.work_collection_uuid)
        self.assertEqual(len(work_collection.items), 3)
        self.assertEqual(tuple(item.collections), (work_collection,) )
        self.assertNotEqual(item, None)
        self.assertEqual(item.title, 'Office supplies order')
        self.assert_(Event.installed_on(item))
        self.assertEqual(Event(item).start, self.jan_ninth)
        self.assert_(Event(item).any_time)
        self.failIf(Event(item).all_day)

    def test_old_chex_import(self):
        """Success when importing old style chex files."""
        self.assertEqual(len(_items_by_uuid), 0)
        reload(self._load('chex_chandler1.gz'), gzip=True)
        self.assertEqual(len(_items_by_uuid), 49)
        self._after_import_tests()

    def test_new_chex_import(self):
        """Success when importing new style chex files."""
        self.assertEqual(len(_items_by_uuid), 0)
        reload(self._load('chex_chandler2.gz'), gzip=True)
        self.assertEqual(len(_items_by_uuid), 49)
        self._after_import_tests()

    def test_chex_export(self):
        """Export a simple Event and collection."""
        collection = Collection(title="Fun")
        item = Item(title="OK")
        collection.add(item)
        Event(item).add(base_start=self.jan_ninth)
        uuids = [str_uuid_for(x) for x in (collection, item)]
        try:
            handle = file(self.tmp_path, 'wb')
            dump(handle, uuids)
        finally:
            handle.close()
            try:
                os.remove(self.tmp_path)
            except:
                pass


if __name__ == "__main__":
    unittest.main()
