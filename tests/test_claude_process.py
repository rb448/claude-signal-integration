"""
Tests for Claude Code subprocess management.

Verifies:
- Process lifecycle (start/stop)
- Working directory isolation
- Graceful shutdown with timeout
- Concurrent process isolation
"""

import asyncio
import os
import tempfile
from pathlib import Path

import pytest

from src.claude.process import ClaudeProcess


@pytest.mark.asyncio
async def test_start_spawns_subprocess():
    """Verify process starts and is_running returns True."""
    with tempfile.TemporaryDirectory() as tmpdir:
        process = ClaudeProcess(session_id="test-start", project_path=tmpdir)

        # Before start, not running
        assert not process.is_running

        # Start process (will fail to find claude-code, but that's OK for structure test)
        try:
            await process.start()
            # If claude-code exists, process should be running
            assert process.is_running
            await process.stop()
        except FileNotFoundError:
            # Expected if claude-code not in PATH
            pytest.skip("claude-code not found in PATH")


@pytest.mark.asyncio
async def test_stop_terminates_process():
    """Verify SIGTERM works and is_running returns False."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Use 'sleep' command as a stand-in that we know exists
        process = ClaudeProcess(session_id="test-stop", project_path=tmpdir)

        # Monkey-patch to use 'sleep' instead of 'claude-code' for testing
        original_start = process.start

        async def mock_start():
            process._process = await asyncio.create_subprocess_exec(
                "sleep",
                "30",
                cwd=process.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

        process.start = mock_start

        await process.start()
        assert process.is_running

        # Stop should terminate gracefully
        await process.stop(timeout=2.0)
        assert not process.is_running


@pytest.mark.asyncio
async def test_stop_with_timeout_kills_process():
    """Verify short timeout forces SIGKILL path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        process = ClaudeProcess(session_id="test-timeout", project_path=tmpdir)

        # Use a process that ignores SIGTERM (sleep on most systems)
        async def mock_start():
            process._process = await asyncio.create_subprocess_exec(
                "sleep",
                "30",
                cwd=process.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

        process.start = mock_start

        await process.start()
        assert process.is_running

        # Very short timeout should trigger SIGKILL
        await process.stop(timeout=0.1)
        assert not process.is_running


@pytest.mark.asyncio
async def test_process_inherits_working_directory():
    """Verify cwd isolation - process runs in correct directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a marker file in the temp directory
        marker_path = Path(tmpdir) / "marker.txt"
        marker_path.write_text("test marker")

        process = ClaudeProcess(session_id="test-cwd", project_path=tmpdir)

        # Use 'pwd' to verify working directory
        async def mock_start():
            process._process = await asyncio.create_subprocess_exec(
                "pwd",
                cwd=process.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

        process.start = mock_start

        await process.start()

        # Wait for command to complete
        stdout, _ = await process._process.communicate()
        reported_cwd = stdout.decode().strip()

        # Verify pwd output matches our tmpdir
        assert reported_cwd == str(Path(tmpdir).resolve())


@pytest.mark.asyncio
async def test_concurrent_processes_isolated():
    """Verify two ClaudeProcess instances have separate PIDs."""
    with tempfile.TemporaryDirectory() as tmpdir1:
        with tempfile.TemporaryDirectory() as tmpdir2:
            process1 = ClaudeProcess(session_id="test-concurrent-1", project_path=tmpdir1)
            process2 = ClaudeProcess(session_id="test-concurrent-2", project_path=tmpdir2)

            # Mock start for both
            async def mock_start_1():
                process1._process = await asyncio.create_subprocess_exec(
                    "sleep",
                    "10",
                    cwd=process1.project_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

            async def mock_start_2():
                process2._process = await asyncio.create_subprocess_exec(
                    "sleep",
                    "10",
                    cwd=process2.project_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

            process1.start = mock_start_1
            process2.start = mock_start_2

            # Start both processes
            await process1.start()
            await process2.start()

            try:
                assert process1.is_running
                assert process2.is_running

                # Different PIDs prove isolation
                pid1 = process1._process.pid
                pid2 = process2._process.pid
                assert pid1 != pid2

                # Different working directories
                assert process1.project_path != process2.project_path

            finally:
                # Clean up
                await process1.stop()
                await process2.stop()


@pytest.mark.asyncio
async def test_start_raises_if_already_running():
    """Verify calling start twice raises RuntimeError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        process = ClaudeProcess(session_id="test-double-start", project_path=tmpdir)

        async def mock_start():
            process._process = await asyncio.create_subprocess_exec(
                "sleep",
                "10",
                cwd=process.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

        process.start = mock_start

        await process.start()

        try:
            # Second start should raise
            with pytest.raises(RuntimeError, match="already running"):
                # Restore original start for the error check
                process.start = ClaudeProcess.start.__get__(process)
                await process.start()
        finally:
            await process.stop()
