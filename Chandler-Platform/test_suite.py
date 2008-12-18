import doctest, unittest
import sys, os.path
import pkg_resources
from chandler.test_helper import AbstractTestLoader, setUp, tearDown

from test_birefs import *
from test_filtered_subset import *


def additional_tests():
    files = [f for f in pkg_resources.resource_listdir(__name__, '.') if f.endswith(".txt")]
    return doctest.DocFileSuite(setUp=setUp, tearDown=tearDown,
                                optionflags=doctest.ELLIPSIS, *files)

def single_test(filename):
    return doctest.DocFileSuite(filename, optionflags=doctest.ELLIPSIS)

class TestLoader(AbstractTestLoader):
    single_test = staticmethod(single_test)
    additional_tests = staticmethod(additional_tests)

if __name__ == "__main__":
    unittest.main(testLoader=TestLoader())
