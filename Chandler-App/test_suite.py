import doctest, unittest
import sys, os.path
import pkg_resources

from test_event import *
from test_recurrence import *
from test_chex import *

from chandler.main import useChandlerApplication

from chandler.test_helper import AbstractTestLoader, setUp, tearDown

def setUpApp(test_case):
    setUp(test_case)
    useChandlerApplication()

def additional_tests():
    files = [f for f in pkg_resources.resource_listdir(__name__, '.') if f.endswith(".txt")]
    return doctest.DocFileSuite(setUp=setUpApp, tearDown=tearDown,
                                optionflags=doctest.ELLIPSIS, *files)

def single_test(filename):
    return doctest.DocFileSuite(filename, optionflags=doctest.ELLIPSIS)

class TestLoader(AbstractTestLoader):
    single_test = staticmethod(single_test)
    additional_tests = staticmethod(additional_tests)

if __name__ == "__main__":
    unittest.main(testLoader=TestLoader())
