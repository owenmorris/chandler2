import doctest

def additional_tests():

    return doctest.DocFileSuite('Core.txt', optionflags=doctest.ELLIPSIS)
