
import time
from cache import LRUCache

def test_basic():
    c = LRUCache(1024*1024)
    c.set("a", b"1")
    assert c.get("a") == b"1"
    assert c.delete("a") == 1
    assert c.get("a") is None

def test_ttl():
    c = LRUCache(1024*1024)
    c.set("k", b"v", ttl_sec=0.05)
    assert c.get("k") == b"v"
    time.sleep(0.06)
    assert c.get("k") is None  # expired

def test_eviction():
    c = LRUCache(32)  # tiny
    c.set("a", b"1234")   # ~5 bytes
    c.set("b", b"123456") # push over capacity
    # One should be evicted (LRU). Access 'a' before inserting 'b' to make 'a' MRU.
    c = LRUCache(16)
    c.set("a", b"x")
    c.set("b", b"x")
    c.get("a")  # make a MRU
    c.set("c", b"xxxxxxxxxxxx")  # force evict LRU ('b')
    assert c.get("b") is None

if __name__ == "__main__":
    test_basic()
    test_ttl()
    test_eviction()
    print("OK")
