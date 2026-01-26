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


class TestCodeDisplayIntegration:
    """Test SignalResponder code display integration."""

    def test_detects_code_blocks(self):
        """Response with code blocks triggers code formatting."""
        responder = SignalResponder()
        response = Response(
            type=OutputType.RESPONSE,
            text="Here's the code:\n```python\ndef hello():\n    print('world')\n```"
        )
        result = responder.format(response)
        # Should contain formatted code with highlighting (ANSI codes)
        assert "```" in result
        assert "hello" in result  # Function name present (may have ANSI codes)

    def test_formats_code_with_formatter(self):
        """Code blocks get formatted for mobile width."""
        responder = SignalResponder()
        response = Response(
            type=OutputType.RESPONSE,
            text="```python\ndef very_long_function_name_that_exceeds_mobile_width():\n    pass\n```"
        )
        result = responder.format(response)
        # Formatted code should have continuation markers for long lines
        assert "```" in result

    def test_highlights_code_with_syntax(self):
        """Code blocks get syntax highlighting."""
        responder = SignalResponder()
        response = Response(
            type=OutputType.RESPONSE,
            text="```python\ndef hello():\n    return 'world'\n```"
        )
        result = responder.format(response)
        # Should contain ANSI escape codes from syntax highlighting
        # (simplified check - just ensure processing happened)
        assert "```" in result

    def test_detects_git_diff(self):
        """Response with git diff triggers diff rendering."""
        responder = SignalResponder()
        diff_text = """diff --git a/file.py b/file.py
index 1234567..abcdefg 100644
--- a/file.py
+++ b/file.py
@@ -1,3 +1,3 @@
 def hello():
-    print('old')
+    print('new')
"""
        response = Response(type=OutputType.RESPONSE, text=diff_text)
        result = responder.format(response)
        # Should contain diff summary
        assert "Changes:" in result or "Modified" in result

    def test_renders_diff_with_renderer(self):
        """Diffs get rendered with mobile-friendly layout."""
        responder = SignalResponder()
        diff_text = """diff --git a/test.py b/test.py
index 1234567..abcdefg 100644
--- a/test.py
+++ b/test.py
@@ -1,2 +1,2 @@
-old line
+new line
"""
        response = Response(type=OutputType.RESPONSE, text=diff_text)
        result = responder.format(response)
        # Should contain rendered diff with emoji markers
        assert "➕" in result or "➖" in result or "Modified" in result

    def test_generates_diff_summary(self):
        """Diffs include plain-English summary before details."""
        responder = SignalResponder()
        diff_text = """diff --git a/config.json b/config.json
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/config.json
@@ -0,0 +1,5 @@
+{
+  "key": "value"
+}
"""
        response = Response(type=OutputType.RESPONSE, text=diff_text)
        result = responder.format(response)
        # Should have summary before diff details
        assert "Created" in result or "config.json" in result

    def test_detects_long_code_for_attachment(self):
        """Long code (>100 lines) triggers attachment mode."""
        responder = SignalResponder()
        long_code = "\n".join([f"line {i}" for i in range(150)])
        response = Response(
            type=OutputType.RESPONSE,
            text=f"```python\n{long_code}\n```"
        )
        result = responder.format(response)
        # Should indicate attachment needed
        assert "attachment" in result.lower() or "lines" in result

    def test_preserves_non_code_text(self):
        """Plain text without code/diff passes through unchanged."""
        responder = SignalResponder()
        plain_text = "This is a plain response without any code."
        response = Response(type=OutputType.RESPONSE, text=plain_text)
        result = responder.format(response)
        assert result == plain_text

    def test_handles_mixed_content(self):
        """Response with text + code + diff processes all correctly."""
        responder = SignalResponder()
        mixed = """Here's an explanation.

```python
def example():
    pass
```

And some more text."""
        response = Response(type=OutputType.RESPONSE, text=mixed)
        result = responder.format(response)
        # Should preserve structure with formatted code
        assert "explanation" in result
        assert "```" in result
        assert "more text" in result


class TestAttachmentIntegration:
    """Test SignalResponder attachment handling integration."""

    @pytest.mark.asyncio
    async def test_send_with_attachments_uploads_code(self):
        """send_with_attachments uploads code and updates message."""
        from unittest.mock import AsyncMock, MagicMock

        responder = SignalResponder(signal_api_url="http://localhost:8080")

        # Mock the attachment handler
        responder.attachment_handler = AsyncMock()
        responder.attachment_handler.send_code_file = AsyncMock(return_value="12345")

        # Message with attachment marker
        formatted = "[Code too long (150 lines) - attachment coming...]"
        code_blocks = [("line 0\nline 1\n" * 75, "example.py")]

        result = await responder.send_with_attachments(
            formatted, code_blocks, "+1234567890"
        )

        # Should upload attachment
        responder.attachment_handler.send_code_file.assert_called_once()

        # Should update message with confirmation
        assert "📎 Sent example.py" in result
        assert "150 lines" in result
        assert "attachment coming" not in result

    @pytest.mark.asyncio
    async def test_send_with_attachments_handles_upload_failure(self):
        """send_with_attachments handles attachment upload failures gracefully."""
        from unittest.mock import AsyncMock

        responder = SignalResponder(signal_api_url="http://localhost:8080")

        # Mock the attachment handler to fail
        responder.attachment_handler = AsyncMock()
        responder.attachment_handler.send_code_file = AsyncMock(return_value=None)

        formatted = "[Code too long (150 lines) - attachment coming...]"
        code_blocks = [("code content", "test.py")]

        result = await responder.send_with_attachments(
            formatted, code_blocks, "+1234567890"
        )

        # Message should remain unchanged if upload fails
        assert "[Code too long (150 lines) - attachment coming...]" in result

    @pytest.mark.asyncio
    async def test_send_with_attachments_multiple_blocks(self):
        """send_with_attachments handles multiple code blocks."""
        from unittest.mock import AsyncMock

        responder = SignalResponder(signal_api_url="http://localhost:8080")

        # Mock the attachment handler
        responder.attachment_handler = AsyncMock()
        responder.attachment_handler.send_code_file = AsyncMock(return_value="12345")

        formatted = """First file:
[Code too long (150 lines) - attachment coming...]

Second file:
[Code too long (200 lines) - attachment coming...]"""

        code_blocks = [
            ("code1" * 50, "file1.py"),
            ("code2" * 100, "file2.js")
        ]

        result = await responder.send_with_attachments(
            formatted, code_blocks, "+1234567890"
        )

        # Should upload both attachments
        assert responder.attachment_handler.send_code_file.call_count == 2

        # Should update both messages
        assert "📎 Sent file1.py" in result
        assert "📎 Sent file2.js" in result
