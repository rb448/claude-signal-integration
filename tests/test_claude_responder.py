"""Tests for Signal message formatting."""

import asyncio
import time
import pytest

from src.claude.parser import ToolCall, Progress, Error, Response, OutputType
from src.claude.responder import SignalResponder, MessageBatcher


class TestSignalResponder:
    """Test SignalResponder formatting."""

    def test_format_tool_call_read(self):
        """ToolCall with Read tool formats with read emoji."""
        responder = SignalResponder()
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="Read", target="file.py")
        result = responder.format(tool_call)
        assert result == "📖 Read: file.py"

    def test_format_tool_call_edit(self):
        """ToolCall with Edit tool formats with edit emoji."""
        responder = SignalResponder()
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="Edit", target="main.py")
        result = responder.format(tool_call)
        assert result == "✏️ Edit: main.py"

    def test_format_tool_call_write(self):
        """ToolCall with Write tool formats with write emoji."""
        responder = SignalResponder()
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="Write", target="new_file.py")
        result = responder.format(tool_call)
        assert result == "💾 Write: new_file.py"

    def test_format_tool_call_bash(self):
        """ToolCall with Bash tool formats with bash emoji."""
        responder = SignalResponder()
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="Bash", command="pytest tests/")
        result = responder.format(tool_call)
        assert result == "🔧 Bash: pytest tests/"

    def test_format_tool_call_grep(self):
        """ToolCall with Grep tool formats with search emoji."""
        responder = SignalResponder()
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="Grep", target="pattern")
        result = responder.format(tool_call)
        assert result == "🔍 Grep: pattern"

    def test_format_tool_call_glob(self):
        """ToolCall with Glob tool formats with folder emoji."""
        responder = SignalResponder()
        tool_call = ToolCall(type=OutputType.TOOL_CALL, tool="Glob", target="*.py")
        result = responder.format(tool_call)
        assert result == "📁 Glob: *.py"

    def test_format_progress(self):
        """Progress formats with progress emoji."""
        responder = SignalResponder()
        progress = Progress(type=OutputType.PROGRESS, message="Analyzing code")
        result = responder.format(progress)
        assert result == "⏳ Analyzing code..."

    def test_format_error(self):
        """Error formats with error emoji."""
        responder = SignalResponder()
        error = Error(type=OutputType.ERROR, message="Failed to read file")
        result = responder.format(error)
        assert result == "❌ Error: Failed to read file"

    def test_format_response(self):
        """Response formats as plain text."""
        responder = SignalResponder()
        response = Response(type=OutputType.RESPONSE, text="Hello, world!")
        result = responder.format(response)
        assert result == "Hello, world!"

    def test_split_long_message_short_text(self):
        """Short messages don't get split."""
        responder = SignalResponder()
        text = "Short message"
        chunks = responder.split_for_signal(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_split_long_message_exceeds_limit(self):
        """Long messages split at max_len."""
        responder = SignalResponder()
        # Create a message longer than 1600 chars
        text = "A" * 2000
        chunks = responder.split_for_signal(text, max_len=1600)
        assert len(chunks) > 1
        assert all(len(chunk) <= 1600 for chunk in chunks)

    def test_split_on_sentence_boundary(self):
        """Long messages split on sentence boundaries when possible."""
        responder = SignalResponder()
        # Create text with sentence boundaries
        sentences = ["This is sentence one. ", "This is sentence two. "] * 50
        text = "".join(sentences)
        chunks = responder.split_for_signal(text, max_len=1600)
        assert len(chunks) > 1
        # Check that chunks end with punctuation (sentence boundary)
        for chunk in chunks[:-1]:  # All but last should end cleanly
            assert chunk.rstrip().endswith(('.', '!', '?', '...continued'))

    def test_preserve_code_blocks(self):
        """Small code blocks are not split."""
        responder = SignalResponder()
        # Create a small code block that fits in one chunk
        code_block = "```python\n" + "print('hello')\n" * 10 + "```"
        text = "Here's some code:\n" + code_block + "\nAnd more text."
        chunks = responder.split_for_signal(text, max_len=500)

        # Verify code block stays together
        code_block_found = False
        for chunk in chunks:
            if "```python" in chunk:
                # Code block should be complete in this chunk
                assert chunk.count("```") == 2
                code_block_found = True
                break
        assert code_block_found

    def test_continuation_markers(self):
        """Split messages have continuation markers."""
        responder = SignalResponder()
        text = "A" * 2000
        chunks = responder.split_for_signal(text, max_len=1600)
        assert len(chunks) > 1
        # First chunk should end with continuation
        assert chunks[0].endswith("...continued")
        # Last chunk should not have continuation at end
        assert not chunks[-1].endswith("...continued")


class TestMessageBatcher:
    """Test MessageBatcher for rate-aware message batching."""

    def test_batcher_initialization(self):
        """Batcher initializes with min interval."""
        batcher = MessageBatcher(min_batch_interval=0.5)
        assert batcher.min_batch_interval == 0.5
        assert len(batcher.flush()) == 0  # Empty on init

    def test_add_message(self):
        """Messages can be added to buffer."""
        batcher = MessageBatcher()
        batcher.add("Message 1")
        batcher.add("Message 2")
        messages = batcher.flush()
        assert len(messages) == 2
        assert messages[0] == "Message 1"
        assert messages[1] == "Message 2"

    def test_flush_clears_buffer(self):
        """Flush clears the buffer."""
        batcher = MessageBatcher()
        batcher.add("Message 1")
        first_flush = batcher.flush()
        second_flush = batcher.flush()
        assert len(first_flush) == 1
        assert len(second_flush) == 0

    def test_should_flush_empty_buffer(self):
        """Empty buffer should not flush."""
        batcher = MessageBatcher(min_batch_interval=0.1)
        time.sleep(0.2)  # Wait longer than interval
        assert not batcher.should_flush()

    def test_should_flush_before_interval(self):
        """Should not flush before min interval passes."""
        batcher = MessageBatcher(min_batch_interval=0.5)
        batcher.add("Message 1")
        assert not batcher.should_flush()

    def test_should_flush_after_interval(self):
        """Should flush after min interval passes with messages."""
        batcher = MessageBatcher(min_batch_interval=0.1)
        batcher.add("Message 1")
        time.sleep(0.15)  # Wait longer than interval
        assert batcher.should_flush()

    def test_flush_resets_timer(self):
        """Flush resets the interval timer."""
        batcher = MessageBatcher(min_batch_interval=0.1)
        batcher.add("Message 1")
        time.sleep(0.15)
        batcher.flush()

        # Add new message immediately after flush
        batcher.add("Message 2")
        # Should not be ready to flush immediately
        assert not batcher.should_flush()
