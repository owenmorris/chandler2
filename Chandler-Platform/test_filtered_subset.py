import unittest
import peak.events.trellis as trellis
import chandler.core as core

class Component(trellis.Component):
    value = trellis.attr(None)

class Observer(trellis.Component):
    observee = trellis.make(trellis.Set, writable=True)
    observations = trellis.make(list)

    @trellis.perform
    def observer(self):
        def map(iterable):
            return sorted(x.value for x in iterable)
        self.observations.append(map(self.observee))
        if self.observee.added:
            self.observations.append(("added", map(self.observee.added)))
        if self.observee.removed:
            self.observations.append(("removed", map(self.observee.removed)))

class MFSSTestCase(unittest.TestCase):
    """Test correct contents of a FilteredSubset when the items are mutable"""

    def testOnce(self):

        base = trellis.Set(Component(value=i) for i in xrange(10))
        subset = core.FilteredSubset(base=base, predicate=lambda comp:comp.value>6)

        self.failUnlessEqual(sorted(x.value for x in subset), [7, 8, 9])

        special = Component(value=-3)
        base.add(special)

        self.failIf(special in subset)
        self.failUnlessEqual(sorted(x.value for x in subset), [7, 8, 9])

        special.value = 31
        self.failUnless(special in subset)
        self.failUnlessEqual(sorted(x.value for x in subset), [7, 8, 9, 31])

    def testChangePredicate(self):
        base = trellis.Set(Component(value=i) for i in xrange(10))
        subset = core.FilteredSubset(base=base, predicate=lambda comp:comp.value>6)

        self.failUnlessEqual(sorted(x.value for x in subset), [7, 8, 9])

        subset.predicate = lambda comp: comp.value % 2
        self.failUnlessEqual(sorted(x.value for x in subset), [1, 3, 5, 7, 9])

class MFSFuturesTestCase(unittest.TestCase):
    """Test that 'added' and 'removed' cells work ok with mutable set elements"""

    def setUp(self):
        super(MFSFuturesTestCase, self).setUp()
        base = trellis.Set(Component(value=i) for i in xrange(10))
        self.subset = core.FilteredSubset(base=base, predicate=lambda comp:comp.value>6)

    def tearDown(self):
        del self.subset
        super(MFSFuturesTestCase, self).tearDown()

    def testInit(self):
        observer = Observer(observee=self.subset)
        self.failUnlessEqual(list(observer.observations),
                             [[7, 8, 9]])
        observer.observations[:] = []

    def testMutableNonMember(self):
        nonMember = Component(value=-10)
        self.subset.base.add(nonMember)
        observer = Observer(observee=self.subset)
        observer.observations[:] = []

        nonMember.value = -15
        self.failIf(observer.observations)

        nonMember.value = 27
        self.failUnlessEqual(
            list(observer.observations),
            [[7, 8, 9, 27], ("added", [27]), [7, 8, 9, 27]]
        )

    def testMutableMember(self):
        member = Component(value=191)
        self.subset.base.add(member)
        observer = Observer(observee=self.subset)
        observer.observations[:] = []

        member.value += 1 # still in set
        self.failUnlessEqual(list(observer.observations),
                             [[7, 8, 9, 192]])

        observer.observations[:] = []
        member.value = 0
        self.failUnlessEqual(list(observer.observations),
                             [[7, 8, 9], ("removed", [0]), [7, 8, 9]])

    def testChangePredicate(self):
        member = Component(value=191)
        self.subset.base.add(member)
        observer = Observer(observee=self.subset)
        observer.observations[:] = []

        self.subset.predicate = lambda component: (component.value %2 == 0)
        self.failUnlessEqual(list(observer.observations),
                             [[0, 2, 4, 6, 8],
                              ("added", [0, 2, 4, 6]),
                              ("removed", [7, 9, 191]),
                              [0, 2, 4, 6, 8]])
        observer.observations[:] = []

        member.value += 1
        self.failUnlessEqual(list(observer.observations),
                             [[0, 2, 4, 6, 8, 192],
                              ("added", [192]),
                              [0, 2, 4, 6, 8, 192]])

class ReprTestCase(unittest.TestCase):
    """A couple of cases for __repr__, which up to now was only tested in Sidebar.txt"""

    def testEmpty(self):
        self.failUnlessEqual(repr(core.FilteredSubset()), "FilteredSubset([])")

    def testTwo(self):
        subset = core.FilteredSubset()
        subset.base.update((21, 22))

        r = repr(subset)
        self.failUnless(r == "FilteredSubset([21, 22])" or
                        r == "FilteredSubset([22, 21])")

        subset.predicate = lambda i: i<=21

        self.failUnlessEqual(repr(subset),"FilteredSubset([21])")

if __name__ == "__main__":
    unittest.main()
