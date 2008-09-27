import doctest, unittest
from glob import glob

def additional_tests():

    return doctest.DocFileSuite(optionflags=doctest.ELLIPSIS, *glob("*.txt"))

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(additional_tests())
