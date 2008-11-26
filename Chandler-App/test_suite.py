import doctest, unittest, sys
import pkg_resources
from test_event import *
from test_recurrence import *

def additional_tests():
    files = [f for f in pkg_resources.resource_listdir(__name__, '.') if f.endswith(".txt")]
    return doctest.DocFileSuite(optionflags=doctest.ELLIPSIS, *files)

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    suite.addTest(additional_tests())
    unittest.TextTestRunner(verbosity=2).run(suite)
