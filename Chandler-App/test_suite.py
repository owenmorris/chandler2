import doctest, unittest
import sys, os.path
import pkg_resources

from test_birefs import *

from setuptools.command.test import ScanningLoader

class TestLoader(ScanningLoader):
    def loadTestsFromName(self, name, module=None):
        if name in ("doctests", __name__ + ".doctests"):
            return additional_tests()
        if name.startswith("doctests:"):
            filename = name[len("doctests:"):] + ".txt"
            return doctest.DocFileSuite(filename, optionflags=doctest.ELLIPSIS)
        else:
            return super(TestLoader, self).loadTestsFromName(name, module)

from peak.events import activity
from peak.util import plugins
from copy import deepcopy

# silence annoying logger warnings
import logging
logging.raiseExceptions = 0

def setUp(test_case):
    # use a different Time for each test, so time changes don't
    # trigger unnecessary recalculations in previous tests
    test_case.time_context = activity.Time.new()
    test_case.time_context.__enter__()
    # don't let a test's registered hooks affect other tests
    test_case._implementations = deepcopy(plugins._implementations)

def tearDown(test_case):
    test_case.time_context.__exit__(None, None, None)
    plugins._implementations = test_case._implementations

def additional_tests():
    files = [f for f in pkg_resources.resource_listdir(__name__, '.') if f.endswith(".txt")]
    return doctest.DocFileSuite(setUp=setUp, tearDown=tearDown,
                                optionflags=doctest.ELLIPSIS, *files)

if __name__ == "__main__":
    unittest.main(testLoader=TestLoader())
