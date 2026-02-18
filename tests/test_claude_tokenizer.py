"""
Test Claude tokenizer integration.

Verify:
1. Auto-detect model from settings
2. Use tokenizers for Claude models
3. Use rs-bpe/tiktoken for other models
4. Reset encoder when model changes
"""

import pytest
from unittest.mock import patch
from core.token_counter import (
    count_tokens,
)
from core.encoders import (
    reset_encoder,
    HAS_TOKENIZERS,
)
from core.tokenization.encoder_registry import get_current_model


class TestClaudeTokenizer:
    """Test Claude tokenizer auto-detection"""

    def setup_method(self):
        """Reset encoder before each test"""
        reset_encoder()

    def test_detect_claude_model(self):
        """Test model detection from settings"""
        with patch("services.settings_manager.load_settings") as mock_load:
            mock_load.return_value = {"model_id": "claude-sonnet-4.5"}
            model = get_current_model()
            assert "claude" in model

    def test_detect_gpt_model(self):
        """Test GPT model detection"""
        with patch("services.settings_manager.load_settings") as mock_load:
            mock_load.return_value = {"model_id": "gpt-4o"}
            model = get_current_model()
            assert "claude" not in model

    @pytest.mark.skipif(not HAS_TOKENIZERS, reason="tokenizers not installed")
    def test_use_tokenizers_for_claude(self):
        """Test that Claude models use tokenizers library"""
        with patch("services.settings_manager.load_settings") as mock_load:
            mock_load.return_value = {"model_id": "claude-sonnet-4.5"}
            reset_encoder()

            text = "Hello, world!"
            tokens = count_tokens(text)

            # Should return positive token count
            assert tokens > 0
            assert isinstance(tokens, int)

    def test_use_tiktoken_for_gpt(self):
        """Test that GPT models use tiktoken/rs-bpe"""
        with patch("services.settings_manager.load_settings") as mock_load:
            mock_load.return_value = {"model_id": "gpt-4o"}
            reset_encoder()

            text = "Hello, world!"
            tokens = count_tokens(text)

            # Should return positive token count
            assert tokens > 0
            assert isinstance(tokens, int)

    def test_reset_encoder_clears_cache(self):
        """Test that reset_encoder() clears singleton"""
        # Count tokens to initialize encoder
        with patch("services.settings_manager.load_settings") as mock_load:
            mock_load.return_value = {"model_id": "gpt-4o"}
            count_tokens("test")

            # Reset
            reset_encoder()

            # Encoder should be None after reset

            # Note: Can't directly access _encoder due to scope,
            # but we can verify by checking if next call reinitializes

            # Change model and count again
            mock_load.return_value = {"model_id": "claude-sonnet-4.5"}
            tokens = count_tokens("test")
            assert tokens > 0

    def test_fallback_to_estimate_if_no_encoder(self):
        """Test fallback to estimation if encoder fails"""
        with patch("core.tokenization.counter.get_encoder", return_value=None):
            text = "Hello, world!"
            tokens = count_tokens(text)

            # Should use estimation (~4 chars = 1 token)
            expected = len(text) // 4
            assert tokens == max(1, expected)

    @pytest.mark.skipif(not HAS_TOKENIZERS, reason="tokenizers not installed")
    def test_claude_tokenizer_accuracy(self):
        """Test Claude tokenizer gives reasonable results"""
        with patch("services.settings_manager.load_settings") as mock_load:
            mock_load.return_value = {"model_id": "claude-sonnet-4.5"}
            reset_encoder()

            # Test various texts
            test_cases = [
                ("Hello", 1, 3),  # (text, min_tokens, max_tokens)
                ("Hello, world!", 2, 5),
                ("The quick brown fox jumps over the lazy dog", 8, 15),
                ("def hello():\n    print('world')", 5, 12),
            ]

            for text, min_tok, max_tok in test_cases:
                tokens = count_tokens(text)
                assert min_tok <= tokens <= max_tok, (
                    f"Text '{text}' got {tokens} tokens, expected {min_tok}-{max_tok}"
                )

    def test_model_switch_reloads_encoder(self):
        """Test switching between Claude and GPT reloads encoder"""
        with patch("services.settings_manager.load_settings") as mock_load:
            # Start with GPT
            mock_load.return_value = {"model_id": "gpt-4o"}
            reset_encoder()
            tokens_gpt = count_tokens("Hello, world!")

            # Switch to Claude
            mock_load.return_value = {"model_id": "claude-sonnet-4.5"}
            reset_encoder()
            tokens_claude = count_tokens("Hello, world!")

            # Both should return valid counts
            assert tokens_gpt > 0
            assert tokens_claude > 0

            # Counts may differ slightly due to different tokenizers
            # but should be in same ballpark (within 50%)
            ratio = tokens_claude / tokens_gpt
            assert 0.5 <= ratio <= 1.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
