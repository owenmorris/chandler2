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

def additional_tests():
    files = [f for f in pkg_resources.resource_listdir(__name__, '.') if f.endswith(".txt")]
    return doctest.DocFileSuite(optionflags=doctest.ELLIPSIS, *files)

if __name__ == "__main__":
    unittest.main(testLoader=TestLoader())
