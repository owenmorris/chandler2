import unittest
import datetime
from chandler.core import Item
from chandler.event import *

class EventTestCase(unittest.TestCase):
    """Extra tests beyond what's useful in the doctests."""

    def setUp(self):
        self.item = Item()
        self.event = Event(self.item).add()
        self.event.start

    def test_none_start(self):
        """start should be None if base_start is"""
        self.assertEquals(self.event.start, None)
        self.event.all_day = True
        self.assertEquals(self.event.start, None)

if __name__ == "__main__":
    unittest.main()
