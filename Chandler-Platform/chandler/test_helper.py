import doctest
from peak.events import activity
from peak.util import plugins
from copy import deepcopy

import pkg_resources
from setuptools.command.test import ScanningLoader

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

# silence annoying logger warnings
import logging
logging.raiseExceptions = 0

class AbstractTestLoader(ScanningLoader):
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
            result = self.additional_tests()
        elif name.startswith("doctests:"):
            filename = name[len("doctests:"):] + ".txt"
            result = self.single_test(filename)
        else:
            result = super(AbstractTestLoader, self).loadTestsFromName(name, module)
        return result

    def additional_tests(self):
        pass

    def single_test(self, filename):
        pass
