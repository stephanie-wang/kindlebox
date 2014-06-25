from Queue import Queue

class SetQueue(Queue):
    def __init__(self, maxsize=0):
        #super(UserQueue, self).__init__(maxsize=maxsize)
        Queue.__init__(self, maxsize)
        self.maxsize = maxsize
        self.items = set()
    
    def _put(self, item):
        if item not in self.items and (len(self.items) < self.maxsize or 
                self.maxsize == 0):
            self.items.add(item)
            return Queue._put(self, item)
    
    def _get(self):
        item = Queue._get(self)
        self.items.remove(item)
        return item
