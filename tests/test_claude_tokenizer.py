"""
Test Claude tokenizer integration voi TokenizationService.

REFACTORED: Tests da duoc cap nhat tu core.token_counter (da xoa)
sang services.tokenization_service.TokenizationService.

Verify:
1. Auto-detect model from settings
2. Use tokenizers for Claude models
3. Use rs-bpe/tiktoken for other models
4. Reset encoder when model changes
"""

import pytest
from unittest.mock import patch
from services.tokenization_service import TokenizationService
from core.encoders import (
    reset_encoder,
    HAS_TOKENIZERS,
)
from services.encoder_registry import get_current_model


class TestClaudeTokenizer:
    """Test Claude tokenizer auto-detection voi TokenizationService."""

    def setup_method(self):
        """Reset encoder va tao service moi truoc moi test."""
        reset_encoder()
        self.service = TokenizationService()

    def test_detect_claude_model(self):
        """Test model detection from settings."""
        with patch("services.settings_manager.load_settings") as mock_load:
            mock_load.return_value = {"model_id": "claude-sonnet-4.5"}
            model = get_current_model()
            assert "claude" in model

    def test_detect_gpt_model(self):
        """Test GPT model detection."""
        with patch("services.settings_manager.load_settings") as mock_load:
            mock_load.return_value = {"model_id": "gpt-4o"}
            model = get_current_model()
            assert "claude" not in model

    @pytest.mark.skipif(not HAS_TOKENIZERS, reason="tokenizers not installed")
    def test_use_tokenizers_for_claude(self):
        """Test that Claude models use tokenizers library."""
        with patch("services.settings_manager.load_settings") as mock_load:
            mock_load.return_value = {"model_id": "claude-sonnet-4.5"}
            # Tao service voi Claude tokenizer repo
            service = TokenizationService(tokenizer_repo="Xenova/claude-tokenizer")

            text = "Hello, world!"
            tokens = service.count_tokens(text)

            # Should return positive token count
            assert tokens > 0
            assert isinstance(tokens, int)

    def test_use_tiktoken_for_gpt(self):
        """Test that GPT models use tiktoken/rs-bpe."""
        with patch("services.settings_manager.load_settings") as mock_load:
            mock_load.return_value = {"model_id": "gpt-4o"}
            service = TokenizationService(tokenizer_repo=None)

            text = "Hello, world!"
            tokens = service.count_tokens(text)

            # Should return positive token count
            assert tokens > 0
            assert isinstance(tokens, int)

    def test_reset_encoder_clears_state(self):
        """Test that reset_encoder() clears internal state."""
        # Count tokens to initialize encoder
        self.service.count_tokens("test")

        # Reset via service
        self.service.reset_encoder()

        # Should still work (lazy re-init)
        tokens = self.service.count_tokens("test")
        assert tokens > 0

    def test_fallback_to_estimate_if_no_encoder(self):
        """Test fallback to estimation if encoder is unavailable."""
        text = "Hello, world!"

        # Truc tiep test _estimate_tokens (pure function)
        from core.encoders import _estimate_tokens

        tokens = _estimate_tokens(text)

        # Should use estimation (~4 chars = 1 token)
        expected = len(text) // 4
        assert tokens == max(1, expected)

    @pytest.mark.skipif(not HAS_TOKENIZERS, reason="tokenizers not installed")
    def test_claude_tokenizer_accuracy(self):
        """Test Claude tokenizer gives reasonable results."""
        service = TokenizationService(tokenizer_repo="Xenova/claude-tokenizer")

        # Test various texts
        test_cases = [
            ("Hello", 1, 3),  # (text, min_tokens, max_tokens)
            ("Hello, world!", 2, 5),
            ("The quick brown fox jumps over the lazy dog", 8, 15),
            ("def hello():\n    print('world')", 5, 12),
        ]

        for text, min_tok, max_tok in test_cases:
            tokens = service.count_tokens(text)
            assert min_tok <= tokens <= max_tok, (
                f"Text '{text}' got {tokens} tokens, expected {min_tok}-{max_tok}"
            )

    def test_model_switch_via_set_model_config(self):
        """Test switching models via set_model_config()."""
        # Start voi GPT (no tokenizer_repo)
        service = TokenizationService(tokenizer_repo=None)
        tokens_gpt = service.count_tokens("Hello, world!")

        # Switch to Claude
        service.set_model_config(tokenizer_repo="Xenova/claude-tokenizer")
        tokens_claude = service.count_tokens("Hello, world!")

        # Both should return valid counts
        assert tokens_gpt > 0
        assert tokens_claude > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
