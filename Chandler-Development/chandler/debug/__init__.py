__import__('pkg_resources').declare_namespace(__name__)

"""Debugging Tools"""

from peak.util import addons, imports
import peak, chandler

class Debugger(addons.AddOn):
    """Application add-on that lets you publish variables to debug tools"""

    def __init__(self, app):
        self.variables = dict(
            app=app,
            chandler=chandler,
            peak=peak,
            wx=imports.lazyModule('wx'),
        )
                        

def additional_tests():
    import doctest
    return doctest.DocFileSuite(
        'README.txt', package='__main__',
        optionflags=doctest.ELLIPSIS|doctest.NORMALIZE_WHITESPACE
    )

