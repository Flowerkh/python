# Write a Python program to search a specific item in a given WSU linked list
# Then return true if the item is found otherwise return false.

# Class Node wich will generate Node for Linked List
class Node(object):
    # Singly linked node which make you to step forward and step backward
    # Thus you need to link of data
    def __init__(self, data=None, next=None, prev=None):
        self.data = data
        self.next = next
        self.prev = prev


# Class for
class WSU_linked_list(object):
    def __init__(self):
        # pre: Node object which has data
        # Method: add data in the linked List
        # Output: None
        self.head = None
        self.tail = None


    def append_item(self, data):
        # Append an item
        # disconnect Link and setup new_item
        # check linked list if there are value that is looked by object
        new_item = Node(data)
        if self.head is None:
            self.head = new_item
            self.tail = new_item
            self.head.prev = None
            self.tail.next = None
        else:
            self.tail.next = new_item
            new_item.prev = self.tail
            self.tail = new_item
            self.tail.next = None


    def iter(self):
        current = self.head
        while current:
            itemval = current.data
            current = current.next
            yield itemval

    # print each elements
    def print_foward(self):
        for node in self.iter():
            print(node)

    # search by end of linked list
    def search_item(self, val):
        current = self.head
        print(val)
        if (self.head == None):
            return False
        while (current != None):
            if (current.data == val):
                return True
            current = current.next

# set Program Language Linked List for set Node
items = WSU_linked_list()  # Instance linked List of Node Object
items.append_item('PHP')  # input program language
items.append_item('Python')
items.append_item('C#')
items.append_item('C++')
items.append_item('Java')
items.append_item('SQL')

print("Original list:")
items.print_foward()
print("\n")

if items.search_item('SQL'):
    print("True")
else:
    print("False")

if items.search_item('C+'):
    print("True")
else:
    print("False")

