from core.vector_memory import VectorMemory


def test_safe_metadata_is_never_empty():
    vm = object.__new__(VectorMemory)
    metadata = vm._safe_metadata({})
    assert metadata["source"] == "eustathius"
    assert metadata["kind"] == "memory"
    assert metadata["created_at"]


def test_memory_id_is_stable_and_prefixed():
    vm = object.__new__(VectorMemory)
    assert vm._memory_id("hello") == vm._memory_id("hello")
    assert vm._memory_id("hello").startswith("mem-")
