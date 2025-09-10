import os
import json
import asyncio
import tempfile
from pathlib import Path
import pytest

from src.fabric.onelake_migrator_turbo_fixed import OptimizedOneLakeMigrator, load_fabric_config


class DummySession:
    pass

def _dummy_config():
    return {
        "tenant_id": "t",
        "client_id": "c",
        "client_secret": "s",
        "fabric_workspace_id": "w",
        "fabric_lakehouse_id": "l",
        "onelake_base_path": "/Files/Test"
    }

@pytest.mark.parametrize("size,expected", [
    (1_000_000, 4*1024*1024),
    (20*1024*1024, 8*1024*1024),
    (200*1024*1024, 16*1024*1024),
    (800*1024*1024, 32*1024*1024),
])
def test_adaptive_chunk_size(size, expected):
    mig = OptimizedOneLakeMigrator(".", _dummy_config())
    assert mig._adaptive_chunk_size(size) == expected


@pytest.mark.asyncio
async def test_stream_file_chunks_and_hash(tmp_path: Path):
    file_path = tmp_path / "sample.bin"
    data = b"abc" * 10000  # 30KB
    file_path.write_bytes(data)
    mig = OptimizedOneLakeMigrator(str(tmp_path), _dummy_config())
    chunk_size = 4096
    positions = []
    total = 0
    async for pos, idx, chunk in mig._stream_file_chunks(str(file_path), 0, len(data), chunk_size):
        positions.append(pos)
        total += len(chunk)
    assert total == len(data)
    assert positions[0] == 0

def test_progress_hash_persistence(tmp_path: Path):
    # Simulate adding a completed file with hash, saving progress, and reloading
    mig = OptimizedOneLakeMigrator(str(tmp_path), _dummy_config())
    progress = mig.init_progress()
    progress['completed_files'].append({"file": "a.txt", "sha256": "deadbeef", "size": 123})
    mig.save_progress(progress)
    loaded = mig.load_progress()
    assert loaded['completed_files'][0]['sha256'] == 'deadbeef'
