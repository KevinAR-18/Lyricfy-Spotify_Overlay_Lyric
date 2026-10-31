"""LRU byte cache with explicit entry and payload budgets."""
from collections import OrderedDict


class ByteCache(OrderedDict):
    def __init__(self, max_entries: int = 8, max_bytes: int = 8 * 1024 * 1024):
        super().__init__()
        self.max_entries = max(1, max_entries)
        self.max_bytes = max(0, max_bytes)
        self.total_bytes = 0

    def get(self, key, default=None):
        if key not in self:
            return default
        self.move_to_end(key)
        return self[key]

    def __setitem__(self, key, value):
        if key in self:
            self.total_bytes -= len(super().pop(key) or b"")
        size = len(value or b"")
        if size > self.max_bytes:
            return
        super().__setitem__(key, value)
        self.total_bytes += size
        while len(self) > self.max_entries or self.total_bytes > self.max_bytes:
            self.popitem(last=False)

    def popitem(self, last=True):
        key, value = super().popitem(last=last)
        self.total_bytes -= len(value or b"")
        return key, value

    def clear(self):
        super().clear()
        self.total_bytes = 0
