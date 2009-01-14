from __future__ import with_statement
import peak.events.trellis as trellis
import chandler.core as core
import unittest

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
    """
    Test correct contents of a FilteredSubset when the input elements
    are mutable
    """

    def testOnce(self):

        input = trellis.Set(Component(value=i) for i in xrange(10))
        subset = core.FilteredSubset(input=input, predicate=lambda comp:comp.value>6)

        self.failUnlessEqual(sorted(x.value for x in subset), [7, 8, 9])

        special = Component(value=-3)
        input.add(special)

        self.failIf(special in subset)
        self.failUnlessEqual(sorted(x.value for x in subset), [7, 8, 9])

        special.value = 31
        self.failUnless(special in subset)
        self.failUnlessEqual(sorted(x.value for x in subset), [7, 8, 9, 31])

    def testChangePredicate(self):
        input = trellis.Set(Component(value=i) for i in xrange(10))
        subset = core.FilteredSubset(input=input, predicate=lambda comp:comp.value>6)

        self.failUnlessEqual(sorted(x.value for x in subset), [7, 8, 9])

        subset.predicate = lambda comp: comp.value % 2
        self.failUnlessEqual(sorted(x.value for x in subset), [1, 3, 5, 7, 9])

class MFSFuturesTestCase(unittest.TestCase):
    """Test that 'added' and 'removed' cells work ok with mutable set elements"""

    def setUp(self):
        super(MFSFuturesTestCase, self).setUp()
        input = trellis.Set(Component(value=i) for i in xrange(10))
        self.subset = core.FilteredSubset(input=input, predicate=lambda comp:comp.value>6)

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
        self.subset.input.add(nonMember)
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
        self.subset.input.add(member)
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
        self.subset.input.add(member)
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
        subset.input.update((21, 22))

        r = repr(subset)
        self.failUnless(r == "FilteredSubset([21, 22])" or
                        r == "FilteredSubset([22, 21])")

        subset.predicate = lambda i: i<=21

        self.failUnlessEqual(repr(subset),"FilteredSubset([21])")


class set_wrapper(object):
    def __init__(self, set):
        self.set = set

    def __eq__(self, other):
        return self.set is getattr(other, 'set', None)

    def __ne__(self, other):
        return self.set is not getattr(other, 'set', None)

    def __hash__(self):
        return id(self.set)

    def __getattr__(self, attr): # unnecessary probably
        return getattr(self.set, attr)

class ComputedUnion(core.AggregatedSet):
    get_values = staticmethod(lambda wrapper: tuple(x for x in wrapper.set))

class ComputedSetTestCase(unittest.TestCase):

    class record_changes(trellis.Component):
        target = trellis.attr(None)

        def __init__(self, target):
            self.changes = []
            trellis.Component.__init__(self, target=target)

        @trellis.perform
        def watch_target(self):
            self.changes.append((set(self.target),
                                 set(self.target.added),
                                 set(self.target.removed)))

        def __enter__(self):
            self.changes[:] = []
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    def failUnlessRecordMatches(self, record, *expected):
        self.failUnlessEqual(len(record.changes), len(expected))
        for recorded, actual in zip(record.changes, expected):
            self.failUnlessEqual(recorded, actual)

    def testComputedSet(self):
        s1 = trellis.Set([1, 4, 5])
        s2 = trellis.Set([1, 5, 6, 10])

        union = ComputedUnion(map(set_wrapper, (s1, s2)))

        self.failUnlessEqual(set(union), set([1, 4, 5, 6, 10]))

    def testRemoveNoop(self):
        s1 = trellis.Set([1, 4, 5])
        s2 = trellis.Set([1, 5, 6, 10])

        union = ComputedUnion(map(set_wrapper, (s1, s2)))

        with self.record_changes(union) as record:
            s2.remove(5)

        # make sure there are no changes posted if we add
        # an element to one of our items that's already
        # in another source
        self.failUnlessRecordMatches(record,
                                     (set([1, 4, 5, 6, 10]), set(), set()),
                                    )

    def testRemoveOne(self):
        s1 = trellis.Set([1, 4, 5])
        s2 = trellis.Set([1, 5, 6, 10])

        union = ComputedUnion(map(set_wrapper, (s1, s2)))

        with self.record_changes(union) as record:
            s2.remove(6)

        self.failUnlessRecordMatches(record,
                                     (set([1, 4, 5, 10]), set(), set([6])),
                                     (set([1, 4, 5, 10]), set(), set()),
                                     )

    def testAddNoop(self):
        s1 = trellis.Set([1, 4, 5])
        s2 = trellis.Set([1, 5, 6, 10])

        union = ComputedUnion(map(set_wrapper, (s1, s2)))

        with self.record_changes(union) as record:
            s1.add(10)

        self.failUnlessRecordMatches(record,
                                     (set([1, 4, 5, 6, 10]), set(), set()),
                                     )

    def testAddOne(self):
        s1 = trellis.Set([1, 4, 5])
        s2 = trellis.Set([1, 5, 6, 10])

        union = ComputedUnion(map(set_wrapper, (s1, s2)))

        with self.record_changes(union) as record:
            s1.add(2)

        self.failUnlessRecordMatches(record,
                                     (set([1, 2, 4, 5, 6, 10]), set([2]), set()),
                                     (set([1, 2, 4, 5, 6, 10]), set(), set()),
                                     )

    def testAddAndRemove(self):
        s1 = trellis.Set([101, 103])
        s2 = trellis.Set([102])
        union = ComputedUnion(map(set_wrapper, (s1, s2)))

        def addAndRemove():
            s1.add(102)
            s2.remove(102)

        with self.record_changes(union) as record:
            trellis.modifier(addAndRemove)()

        self.failUnlessRecordMatches(record,
                                     (set([101, 102, 103]), set(), set()),
                                     )


    def testAddTwice(self):
        s1 = trellis.Set([101, 103])
        s2 = trellis.Set([102])
        union = ComputedUnion(map(set_wrapper, (s1, s2)))

        def addTwice():
            s1.add(104)
            s2.add(104)

        with self.record_changes(union) as record:
            trellis.modifier(addTwice)()

        self.failUnlessRecordMatches(record,
                                     (set([101, 102, 103, 104]), set([104]), set()),
                                     (set([101, 102, 103, 104]), set(), set()),
                                     )

    def testRemoveTwice(self):
        s1 = trellis.Set([101, 103])
        s2 = trellis.Set([101])
        union = ComputedUnion(map(set_wrapper, (s1, s2)))

        def removeTwice():
            s1.remove(101)
            s2.remove(101)

        with self.record_changes(union) as record:
            trellis.modifier(removeTwice)()

        self.failUnlessRecordMatches(record,
                                     (set([103]), set(), set([101])),
                                     (set([103]), set(), set()),
                                     )

    def testChangeSources(self):
        s1 = trellis.Set([0, 2, 4])
        s2 = trellis.Set([4, 6])
        s3 = trellis.Set([2])

        union = ComputedUnion([set_wrapper(s1)])
        with self.record_changes(union) as record:
            union.input.add(set_wrapper(s2))

        self.failUnlessEqual(set(union), set([0, 2, 4, 6]))
        self.failUnlessRecordMatches(record,
                                     (set([0, 2, 4, 6]), set([6]), set()),
                                     (set([0, 2, 4, 6]), set(), set()),
                                     )

        with self.record_changes(union) as record:
            union.input.add(set_wrapper(s3))

        self.failUnlessEqual(set(union), set([0, 2, 4, 6]))
        self.failUnlessRecordMatches(record)

        with self.record_changes(union) as record:
            union.input = trellis.Set([set_wrapper(s2)])

        self.failUnlessRecordMatches(record,
                                     (set([4, 6]), set(), set([0, 2])),
                                     (set([4, 6]), set(), set()),
                                     )

    def testLength(self):
        s1 = trellis.Set([0, 2, 4])
        s2 = trellis.Set([4, 6])
        s3 = trellis.Set([2])

        union = ComputedUnion([set_wrapper(s1)])
        self.failUnlessEqual(len(union), 3)
        
        union.input.add(set_wrapper(s2))
        self.failUnlessEqual(len(union), 4)
        
        union.input.add(set_wrapper(s3))
        self.failUnlessEqual(len(union), 4)
        
        union.input.clear()
        self.failUnlessEqual(len(union), 0)


if __name__ == "__main__":
    unittest.main()
