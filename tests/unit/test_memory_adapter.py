"""Unit tests for PersistentMemory adapter."""

import os
import sys
from datetime import datetime
from typing import Any, Dict, List

import pytest

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hermeswith.runtime.memory_adapter import Memory, PersistentMemory


class TestMemory:
    """Tests for the Memory dataclass."""

    def test_memory_creation_defaults(self):
        """Test Memory creation with default values."""
        memory = Memory(key="test-key", value="test-value")

        assert memory.key == "test-key"
        assert memory.value == "test-value"
        assert memory.importance == 0.5
        assert isinstance(memory.created_at, datetime)

    def test_memory_creation_custom_importance(self):
        """Test Memory creation with custom importance."""
        memory = Memory(key="important", value="critical data", importance=0.9)

        assert memory.importance == 0.9
        assert memory.key == "important"
        assert memory.value == "critical data"

    def test_memory_with_complex_value(self):
        """Test Memory with complex value types."""
        complex_value: Dict[str, Any] = {
            "nested": {"deep": "value"},
            "list": [1, 2, 3],
            "number": 42,
        }
        memory = Memory(key="complex", value=complex_value, importance=0.7)

        assert memory.value == complex_value
        assert memory.value["nested"]["deep"] == "value"
        assert memory.value["list"] == [1, 2, 3]

    def test_memory_custom_timestamp(self):
        """Test Memory with custom timestamp."""
        custom_time = datetime(2024, 1, 15, 10, 30, 0)
        memory = Memory(key="dated", value="old news", created_at=custom_time)

        assert memory.created_at == custom_time


class TestPersistentMemory:
    """Tests for the PersistentMemory class."""

    @pytest.fixture
    def memory_store(self):
        """Create a fresh PersistentMemory instance."""
        return PersistentMemory()

    def test_initialization(self):
        """Test PersistentMemory initialization."""
        store = PersistentMemory()

        assert isinstance(store._store, dict)
        assert len(store._store) == 0

    def test_save_single_memory(self, memory_store):
        """Test saving a single memory."""
        memory_store.save("key1", "value1")

        assert "key1" in memory_store._store
        assert memory_store._store["key1"].value == "value1"
        assert memory_store._store["key1"].importance == 0.5

    def test_save_with_importance(self, memory_store):
        """Test saving with custom importance."""
        memory_store.save("important-key", "important-value", importance=0.9)

        memory = memory_store._store["important-key"]
        assert memory.importance == 0.9

    def test_save_overwrites_existing(self, memory_store):
        """Test that save overwrites existing keys."""
        memory_store.save("key", "original")
        original_time = memory_store._store["key"].created_at

        memory_store.save("key", "updated", importance=0.8)

        assert memory_store._store["key"].value == "updated"
        assert memory_store._store["key"].importance == 0.8
        # Should have updated timestamp
        assert memory_store._store["key"].created_at >= original_time

    def test_recall_empty_store(self, memory_store):
        """Test recall with empty store."""
        results = memory_store.recall("anything")

        assert isinstance(results, list)
        assert len(results) == 0

    def test_recall_by_key_match(self, memory_store):
        """Test recall matching by key."""
        memory_store.save("python-code", "import os")
        memory_store.save("javascript-code", "console.log()")
        memory_store.save("documentation", "readme")

        results = memory_store.recall("python")

        assert len(results) == 1
        assert results[0].key == "python-code"

    def test_recall_by_value_match(self, memory_store):
        """Test recall matching by value."""
        memory_store.save("key1", "This is about machine learning")
        memory_store.save("key2", "Deep learning is a subset")
        memory_store.save("key3", "Unrelated topic")

        results = memory_store.recall("learning")

        assert len(results) == 2
        keys = [r.key for r in results]
        assert "key1" in keys
        assert "key2" in keys

    def test_recall_case_insensitive(self, memory_store):
        """Test recall is case insensitive."""
        memory_store.save("upper", "PYTHON CODE")
        memory_store.save("lower", "python script")
        memory_store.save("mixed", "PyThOn PrOgRaM")

        results = memory_store.recall("python")

        assert len(results) == 3

    def test_recall_respects_limit(self, memory_store):
        """Test recall respects the limit parameter."""
        for i in range(10):
            memory_store.save(f"key{i}", f"value containing search term {i}")

        results = memory_store.recall("search", limit=3)

        assert len(results) == 3

    def test_recall_sorted_by_importance(self, memory_store):
        """Test recall results sorted by importance (highest first)."""
        memory_store.save("low", "value", importance=0.2)
        memory_store.save("high", "value", importance=0.9)
        memory_store.save("medium", "value", importance=0.5)

        results = memory_store.recall("value")

        assert len(results) == 3
        assert results[0].key == "high"  # 0.9
        assert results[1].key == "medium"  # 0.5
        assert results[2].key == "low"  # 0.2

    def test_recall_tiebreaker_by_date(self, memory_store):
        """Test recall tiebreaker is creation date (oldest first)."""
        # Create memories with same importance but different times
        # Since we can't easily control time, we rely on sequential saves
        memory_store.save("first", "value", importance=0.5)
        import time

        time.sleep(0.01)  # Small delay to ensure different timestamps
        memory_store.save("second", "value", importance=0.5)

        results = memory_store.recall("value")

        # Same importance, so first created should come first
        assert results[0].key == "first"
        assert results[1].key == "second"

    def test_recall_partial_match(self, memory_store):
        """Test recall with partial string match."""
        memory_store.save("config", '{"db": {"host": "localhost"}}')
        memory_store.save("readme", "This project uses PostgreSQL")

        results = memory_store.recall("local")

        assert len(results) == 1
        assert results[0].key == "config"

    def test_save_various_types(self, memory_store):
        """Test saving various value types."""
        # String
        memory_store.save("string", "text")
        # Integer
        memory_store.save("int", 42)
        # Float
        memory_store.save("float", 3.14)
        # List
        memory_store.save("list", [1, 2, 3])
        # Dict
        memory_store.save("dict", {"a": 1})
        # None
        memory_store.save("none", None)

        assert memory_store._store["string"].value == "text"
        assert memory_store._store["int"].value == 42
        assert memory_store._store["float"].value == 3.14
        assert memory_store._store["list"].value == [1, 2, 3]
        assert memory_store._store["dict"].value == {"a": 1}
        assert memory_store._store["none"].value is None

    def test_recall_with_special_characters(self, memory_store):
        """Test recall with special characters in query."""
        memory_store.save("special", "Value with special chars: @#$%^&*()")

        results = memory_store.recall("@#$%")

        assert len(results) == 1

    def test_memory_persistence_in_instance(self, memory_store):
        """Test that memories persist within the instance."""
        memory_store.save("persistent", "This should still be here")

        # Multiple recalls should return the same data
        results1 = memory_store.recall("persistent")
        results2 = memory_store.recall("persistent")

        assert len(results1) == 1
        assert len(results2) == 1
        assert results1[0].value == results2[0].value

    def test_empty_key_and_value(self, memory_store):
        """Test handling of empty key and value."""
        memory_store.save("", "empty key")
        memory_store.save("empty-value", "")

        assert "" in memory_store._store
        assert memory_store._store[""].value == "empty key"

        results = memory_store.recall("")
        assert len(results) >= 2  # Should find both empty key and empty value

    def test_large_values(self, memory_store):
        """Test handling of large values."""
        large_value = "x" * 10000
        memory_store.save("large", large_value)

        results = memory_store.recall("x" * 100)

        assert len(results) == 1
        assert len(results[0].value) == 10000

    def test_unicode_support(self, memory_store):
        """Test unicode in keys and values."""
        memory_store.save("日本語", "こんにちは")
        memory_store.save("emoji", "🚀 🎉 🎊")
        memory_store.save("chinese", "你好世界")

        results = memory_store.recall("日本")
        assert len(results) == 1

        results = memory_store.recall("🚀")
        assert len(results) == 1

        results = memory_store.recall("你好")
        assert len(results) == 1

    def test_multiple_instances_isolated(self):
        """Test that multiple instances are isolated."""
        store1 = PersistentMemory()
        store2 = PersistentMemory()

        store1.save("key", "store1-value")
        store2.save("key", "store2-value")

        assert store1._store["key"].value == "store1-value"
        assert store2._store["key"].value == "store2-value"

    def test_recall_numeric_query(self, memory_store):
        """Test recall with numeric query (converted to string)."""
        memory_store.save("numbers", "The answer is 42")

        results = memory_store.recall("42")

        assert len(results) == 1

    def test_importance_bounds(self, memory_store):
        """Test importance values at bounds."""
        memory_store.save("min", "zero importance", importance=0.0)
        memory_store.save("max", "full importance", importance=1.0)

        results = memory_store.recall("importance")

        assert len(results) == 2
        assert results[0].key == "max"  # 1.0 comes before 0.0
        assert results[1].key == "min"


class TestPersistentMemoryEdgeCases:
    """Edge case tests for PersistentMemory."""

    @pytest.fixture
    def memory_store(self):
        return PersistentMemory()

    def test_recall_zero_limit(self, memory_store):
        """Test recall with limit=0."""
        memory_store.save("key", "value")

        results = memory_store.recall("value", limit=0)

        assert len(results) == 0

    def test_recall_negative_limit(self, memory_store):
        """Test recall with negative limit."""
        memory_store.save("key", "value")

        # Negative limit should either return empty or all results
        # Depending on Python slice behavior
        results = memory_store.recall("value", limit=-1)
        # [: -1] would return all but last, but that's implementation detail
        assert isinstance(results, list)

    def test_save_updates_timestamp(self, memory_store):
        """Test that updating a key updates its timestamp."""
        memory_store.save("key", "original")
        original = memory_store._store["key"]

        import time

        time.sleep(0.01)
        memory_store.save("key", "updated")
        updated = memory_store._store["key"]

        assert updated.created_at > original.created_at

    def test_concurrent_recalls(self, memory_store):
        """Test that concurrent recalls work correctly."""
        for i in range(100):
            memory_store.save(f"key{i}", f"value{i}")

        # Simulate multiple queries
        results1 = memory_store.recall("value", limit=50)
        results2 = memory_store.recall("value", limit=25)
        results3 = memory_store.recall("key5", limit=20)

        assert len(results1) == 50
        assert len(results2) == 25
        assert len(results3) == 11  # key5, key50-59

    def test_memory_string_representation(self, memory_store):
        """Test string representation of Memory in search."""
        memory_store.save("obj", {"nested": "value"})

        results = memory_store.recall("nested")

        assert len(results) == 1
        assert "nested" in str(results[0].value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
