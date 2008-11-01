import peak.events.trellis as trellis
import unittest

from chandler.core import One, Many

class Node(trellis.Component):
    title = trellis.attr("")
    
    def __repr__(self):
        return "<%s(%s)>" % (type(self).__name__, self.title)
    
    children = Many()
    parent = One(inverse=children)


class BirefTestCase(unittest.TestCase):
    def testSimple(self):
    
        parent = Node(title="parent")
        child = Node(title="child")
    
        child.parent = parent
        self.failUnlessEqual(
            set(parent.children),
            set([child])
        )
        
    def testAssignAtInit(self):
        parent = Node(title="parent")
        child = Node(title="child", parent=parent)
    
        self.failUnlessEqual(
            set(parent.children),
            set([child])
        )
    
    def testSecondChild(self):
        parent = Node(title="parent")
        child1 = Node(title="child1", parent=parent)
        child2 = Node(title="child2", parent=parent)
        
        self.failUnlessEqual(
            set(parent.children),
            set([child1, child2])
        )
        

    def testSetParent(self):
        parent1 = Node(title="parent1")
        child1 = Node(title="child1", parent=parent1)
        child2 = Node(title="child2", parent=parent1)
        
        parent2 = Node(title="parent2")

        child2.parent = parent2
        
        self.failUnlessEqual(
            set(parent1.children),
            set([child1])
        )
        self.failUnlessEqual(
            set(parent2.children),
            set([child2])
        )

    def testChangeChildren(self):
        parent = Node(title="parent")
        child1 = Node(title="child1", parent=parent)
        child2 = Node(title="child2")
        parent.children.add(child2)
        self.failUnlessEqual(child2.parent, parent)


    def testDelChildren(self):
        parent = Node(title="parent")
        child1 = Node(title="child1", parent=parent)
        child2 = Node(title="child2", parent=parent)
        
        del parent.children
        self.failUnlessEqual(
            set(parent.children),
            set([])
        )
        self.failUnlessEqual(
            child1.parent,
            None
        )
        self.failUnlessEqual(
            child2.parent,
            None
        )

    def testAssignChildren(self):
        parent = Node(title="parent")
        child1 = Node(title="child1", parent=parent)
        child2 = Node(title="child2")
        child3 = Node(title="child3")
        
        self.failUnlessEqual(
            set(parent.children),
            set([child1])
        )

        parent.children = (child1, child2)
        self.failUnlessEqual(
            set(parent.children),
            set([child1, child2])
        )
        
        parent.children = (child3,)
        self.failUnlessEqual(
            set(parent.children),
            set([child3])
        )
        self.failUnlessEqual(child1.parent, None)
        self.failUnlessEqual(child2.parent, None)
        self.failUnlessEqual(child3.parent, parent)

    def testChangeParent(self):
        parent = Node(title="parent")
        child1 = Node(title="child1", parent=parent)
        child2 = Node(title="child2", parent=parent)

        del child2.parent
        self.failUnlessEqual(child2.parent, None)
        self.failUnlessEqual(set(parent.children), set([child1]))
        
        child1.parent = child2
        self.failUnlessEqual(set(child2.children), set([child1]))
            

class TwoBirefsTestCase(unittest.TestCase):
    def testTwoBirefs(self):
        
        class A(trellis.Component):
            bees = Many()
            ayes = Many()
            a = One(inverse=ayes)

        class B(trellis.Component):
            a = One(inverse=A.bees)
            
        b = B()
        a1 = A(bees=[b])
        a2 = A()
        
        b.a = a2
        self.failUnlessEqual(set(a2.bees), set([b]))

class A(trellis.Component):
    bees = Many()

class B(trellis.Component):
    ayes = Many(inverse=A.bees)

class ManyToManyTestCase(unittest.TestCase):

    def testSimple(self):
        a = A()
        b = B()
        b.ayes.add(a)
        
        self.failUnlessEqual(set(a.bees), set([b]))
        self.failUnlessEqual(set(b.ayes), set([a]))

    def testInitValue(self):
        a = A()
        b = B(ayes=[a])
        
        self.failUnlessEqual(set(b.ayes), set([a]))
        self.failUnlessEqual(set(a.bees), set([b]))


    def testInitInverse(self):
        b1 = B()
        b2 = B()
        a = A(bees=(b1, b2))
        
        self.failUnlessEqual(set(a.bees), set([b1, b2]))
        self.failUnlessEqual(set(b1.ayes), set([a]))
        self.failUnlessEqual(set(b2.ayes), set([a]))

    def testDelete(self):
        b1 = B()
        b2 = B()
        a = A(bees=(b1, b2))
        
        del b2.ayes
        self.failUnlessEqual(set(b2.ayes), set())
        self.failUnlessEqual(set(b1.ayes), set([a]))
        self.failUnlessEqual(set(a.bees), set([b1]))

    def testRemove(self):
        a1 = A()
        a2 = A()
        b = B()
        b.ayes = (a1, a2)
        b.ayes.remove(a1)
        
        self.failUnlessEqual(set(a1.bees), set())
        self.failUnlessEqual(set(b.ayes), set([a2]))

    def testObserve(self):
        a1 = A()
        a2 = A()
        b = B()
        ops = []
        
        def rule():
            for value in b.ayes.added:
                ops.append(('added', value))
            for value in b.ayes.removed:
                ops.append(('removed', value))

        p = trellis.Performer(rule)
        a1.bees = (b,)
        
        self.failUnlessEqual(set(b.ayes), set([a1]))
        
        self.failUnlessEqual(ops, [('added', a1)])
        
        a2.bees.add(b)
        self.failUnlessEqual(ops, [('added', a1), ('added', a2)])
        
        a2.bees.remove(b)
        self.failUnlessEqual(ops, [('added', a1), ('added', a2),
                                   ('removed', a2)])

if __name__ == "__main__":
    unittest.main()
