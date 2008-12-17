import doctest, unittest
import sys, os.path
import pkg_resources

from test_birefs import *
from test_filtered_subset import *

from setuptools.command.test import ScanningLoader

class TestLoader(ScanningLoader):
    """
    Loader that supports running individual doctests. For example:

    Run all doctests:
        python test_suite.py doctests

    Run the Blurdy.txt doctest:
        python test_suite.py doctests:Blurdy

    The setup.py forms of these work, too, e.g
        python setup.py test -s doctests

    """
    def loadTestsFromName(self, name, module=None):
        if name in ("doctests", __name__ + ".doctests"):
            result = additional_tests()
        elif name.startswith("doctests:"):
            filename = name[len("doctests:"):] + ".txt"
            result = doctest.DocFileSuite(filename, optionflags=doctest.ELLIPSIS)
        else:
            result = super(TestLoader, self).loadTestsFromName(name, module)
        return result

def additional_tests():
    files = [f for f in pkg_resources.resource_listdir(__name__, '.') if f.endswith(".txt")]
    return doctest.DocFileSuite(optionflags=doctest.ELLIPSIS, *files)

if __name__ == "__main__":
    unittest.main(testLoader=TestLoader())
