"""
OpenAI Compatible Provider - Implementation cho tat ca API tuong thich OpenAI.

Ho tro:
- OpenAI chinh thuc (api.openai.com)
- Local LLM (LM Studio, Ollama, vLLM) qua custom base_url
- Third-party providers (OpenRouter, Together AI, Groq, DeepSeek)

Chien luoc Structured Output 3-tier fallback:
  Tier 1: response_format=json_schema (strict) - OpenAI GPT-4o+, vLLM, LM Studio
  Tier 2: response_format=json_object + schema in prompt - DeepSeek, Groq, Mistral
  Tier 3: No response_format + schema in prompt + client-side parse - Universal

Reference:
  - OpenAI: https://developers.openai.com/api/docs/guides/structured-outputs/
  - DeepSeek (chi json_object): https://api-docs.deepseek.com/guides/json_mode
  - Groq: https://console.groq.com/docs/structured-outputs
  - Together AI: https://docs.together.ai/docs/json-mode

Su dung thu vien `requests` (lightweight) thay vi cai dat full openai SDK.
"""

import json
import logging
from typing import Any, Dict, Generator, List, Optional

import requests

from core.ai.base_provider import (
    BaseLLMProvider,
    LLMMessage,
    LLMResponse,
    StreamChunk,
)

logger = logging.getLogger(__name__)

# Timeout mac dinh cho cac request (seconds)
_DEFAULT_TIMEOUT = 60
# Timeout cho stream request (connect_timeout, read_timeout)
_STREAM_TIMEOUT = (10, 120)
# URL mac dinh neu nguoi dung khong cau hinh
_DEFAULT_BASE_URL = "https://api.openai.com/v1"


def _is_format_unsupported_error(error_msg: str) -> bool:
    """
    Kiem tra error message co phai do provider khong ho tro response_format hay khong.

    Khi provider khong ho tro json_schema hoac json_object, server thuong
    tra ve HTTP 400/422 voi error message chua cac tu khoa nhu
    "response_format", "not supported", "invalid type", v.v.

    Args:
        error_msg: Error message tu API response

    Returns:
        True neu loi lien quan den response_format khong duoc ho tro
    """
    msg_lower = error_msg.lower()
    unsupported_patterns = [
        "response_format" in msg_lower
        and any(
            kw in msg_lower
            for kw in [
                "not supported",
                "not available",
                "unsupported",
                "unrecognized",
                "unknown parameter",
            ]
        ),
        "json_schema" in msg_lower
        and any(kw in msg_lower for kw in ["not supported", "is not", "unsupported"]),
        "response_format" in msg_lower and "invalid type" in msg_lower,
    ]
    return any(unsupported_patterns)


class OpenAICompatibleProvider(BaseLLMProvider):
    """
    Provider cho tat ca API tuong thich voi OpenAI Chat Completions.

    Implement 3-tier fallback strategy cho structured output de tuong thich
    voi nhieu provider nhat co the (OpenAI, DeepSeek, Groq, Ollama,
    LM Studio, vLLM, OpenRouter, Together AI, Mistral, v.v.).

    Attributes:
        _api_key: API key da cau hinh
        _base_url: Base URL cua API endpoint
    """

    def __init__(self) -> None:
        """Khoi tao provider voi trang thai chua cau hinh."""
        self._api_key: str = ""
        self._base_url: str = _DEFAULT_BASE_URL

    # === Configuration ===

    def configure(self, api_key: str, base_url: str = "") -> None:
        """
        Cau hinh API key va base URL cho provider.

        Args:
            api_key: API key de xac thuc
            base_url: Base URL (de trong = dung OpenAI mac dinh)
        """
        self._api_key = api_key.strip()
        # Normalize: loai bo trailing slash
        if base_url and base_url.strip():
            self._base_url = base_url.strip().rstrip("/")
        else:
            self._base_url = _DEFAULT_BASE_URL

    def is_configured(self) -> bool:
        """Kiem tra da co API key chua."""
        return bool(self._api_key)

    def get_provider_name(self) -> str:
        """Tra ve ten hien thi cua provider."""
        return "OpenAI Compatible"

    # === Fetch Models ===

    def fetch_available_models(self) -> List[str]:
        """
        Goi GET /v1/models de lay danh sach model tu server.

        Returns:
            List model IDs, sap xep theo alphabet

        Raises:
            ConnectionError: Khi khong ket noi duoc
            PermissionError: Khi API key khong hop le
        """
        if not self.is_configured():
            raise ConnectionError("Provider chua duoc cau hinh. Vui long nhap API Key.")

        url = f"{self._base_url}/models"
        headers = self._build_headers()

        try:
            response = requests.get(url, headers=headers, timeout=15)
            self._check_response_error(response)

            data = response.json()
            # Format cua OpenAI: {"data": [{"id": "gpt-4o", ...}, ...]}
            models = data.get("data", [])
            model_ids = [m.get("id", "") for m in models if m.get("id")]
            return sorted(model_ids)

        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(
                f"Khong the ket noi toi {self._base_url}. "
                f"Kiem tra lai URL va ket noi mang. Chi tiet: {e}"
            ) from e
        except requests.exceptions.Timeout:
            raise ConnectionError(f"Request timeout khi ket noi toi {self._base_url}.")

    # === Structured Output (JSON mode) — 3-Tier Fallback ===

    def generate_structured(
        self,
        messages: List[LLMMessage],
        model_id: str,
        json_schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """
        Goi Chat Completions API voi JSON response format.

        Su dung chien luoc 3-tier fallback de tuong thich voi da so providers:

        Tier 1 — json_schema + strict (OpenAI GPT-4o+, vLLM, LM Studio):
            Server-side schema enforcement. Output LUON dung schema.

        Tier 2 — json_object + schema trong prompt (DeepSeek, Groq, Mistral):
            Output la JSON hop le nhung KHONG dam bao dung schema.
            Schema duoc inject vao system prompt de huong dan model.

        Tier 3 — Khong response_format, chi dung prompt (Universal fallback):
            Can parse va validate JSON tu plain text response.

        Args:
            messages: Chuoi hoi thoai
            model_id: Model ID (VD: "gpt-4o", "deepseek-chat")
            json_schema: Optional schema de ep dang response
            temperature: Do sang tao (0.0 = stable nhat)

        Returns:
            LLMResponse voi content la JSON string
        """
        if not self.is_configured():
            raise ConnectionError("Provider chua duoc cau hinh. Vui long nhap API Key.")

        # Xay dung danh sach strategies theo thu tu uu tien
        strategies = self._build_format_strategies(json_schema)

        url = f"{self._base_url}/chat/completions"
        headers = self._build_headers()
        last_error: Optional[Exception] = None

        for strategy in strategies:
            try:
                # Xay dung payload cho strategy nay
                payload = self._build_structured_payload(
                    messages=messages,
                    model_id=model_id,
                    temperature=temperature,
                    strategy=strategy,
                    json_schema=json_schema,
                )

                response = requests.post(
                    url, headers=headers, json=payload, timeout=_DEFAULT_TIMEOUT
                )
                self._check_response_error(response)

                data = response.json()
                llm_response = self._parse_chat_response(data)

                tier_name = strategy.get("tier_name", "unknown")
                logger.info(
                    "Structured output thanh cong voi strategy: %s (model=%s)",
                    tier_name,
                    model_id,
                )
                return llm_response

            except (ConnectionError, PermissionError) as e:
                error_msg = str(e)
                tier_name = strategy.get("tier_name", "unknown")

                # Kiem tra: loi co phai do response_format khong duoc ho tro?
                if _is_format_unsupported_error(error_msg):
                    logger.info(
                        "Strategy '%s' khong duoc ho tro boi provider, "
                        "falling back... (error: %s)",
                        tier_name,
                        error_msg[:200],
                    )
                    last_error = e
                    continue  # Thu strategy tiep theo

                # Loi khac (auth, network, rate limit) -> raise ngay
                raise

            except requests.exceptions.ConnectionError as e:
                raise ConnectionError(
                    f"Khong the ket noi toi {self._base_url}. Chi tiet: {e}"
                ) from e
            except requests.exceptions.Timeout:
                raise ConnectionError(
                    f"Request timeout ({_DEFAULT_TIMEOUT}s) khi goi model {model_id}."
                )

        # Tat ca strategies deu that bai
        if last_error:
            raise last_error
        raise ConnectionError("Khong the lay structured output tu API.")

    def _build_format_strategies(
        self, json_schema: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Xay dung danh sach strategies theo thu tu uu tien giam dan.

        Tier 1: json_schema (strict)  — Chi khi co schema
        Tier 2: json_object           — Luon co
        Tier 3: no response_format    — Universal fallback

        Args:
            json_schema: JSON Schema (neu co)

        Returns:
            List strategies, moi strategy la dict chua:
              - tier_name: Ten de log
              - response_format: Dict hoac None
              - inject_schema_in_prompt: Co inject schema vao prompt hay khong
        """
        strategies: List[Dict[str, Any]] = []

        # Tier 1: json_schema + strict (best, limited support)
        if json_schema:
            strategies.append(
                {
                    "tier_name": "Tier1_json_schema_strict",
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "context_builder_response",
                            "strict": True,
                            "schema": json_schema,
                        },
                    },
                    "inject_schema_in_prompt": False,
                }
            )

        # Tier 2: json_object + schema in prompt (widest support)
        strategies.append(
            {
                "tier_name": "Tier2_json_object",
                "response_format": {"type": "json_object"},
                "inject_schema_in_prompt": True,
            }
        )

        # Tier 3: no response_format, pure prompt engineering (universal)
        strategies.append(
            {
                "tier_name": "Tier3_prompt_only",
                "response_format": None,
                "inject_schema_in_prompt": True,
            }
        )

        return strategies

    def _build_structured_payload(
        self,
        messages: List[LLMMessage],
        model_id: str,
        temperature: float,
        strategy: Dict[str, Any],
        json_schema: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Tao request payload dua tren strategy duoc chon.

        Neu strategy yeu cau inject_schema_in_prompt, se them schema
        vao system message de huong dan model tra ve dung format.
        Day la best practice duoc khuyen dung boi OpenAI, DeepSeek,
        Groq, va Together AI.

        Args:
            messages: Chuoi messages goc
            model_id: Model ID
            temperature: Temperature
            strategy: Strategy dict tu _build_format_strategies()
            json_schema: JSON Schema goc (de inject vao prompt)

        Returns:
            Dict payload cho HTTP request
        """
        # Clone messages de khong mutate original
        effective_messages = list(messages)

        if strategy.get("inject_schema_in_prompt") and json_schema:
            # Inject schema instruction vao system message
            schema_instruction = (
                "\n\nIMPORTANT: You MUST respond with valid JSON only. "
                "No markdown, no explanation, no code blocks. "
                "Your response must conform to this exact JSON Schema:\n"
                f"```json\n{json.dumps(json_schema, indent=2)}\n```"
            )

            # Tim system message dau tien va append schema vao
            injected = False
            for i, msg in enumerate(effective_messages):
                if msg.role == "system":
                    effective_messages[i] = LLMMessage(
                        role="system",
                        content=msg.content + schema_instruction,
                    )
                    injected = True
                    break

            # Neu khong co system message, them mot cai moi
            if not injected:
                effective_messages.insert(
                    0,
                    LLMMessage(
                        role="system",
                        content="You are a helpful assistant." + schema_instruction,
                    ),
                )

        payload: Dict[str, Any] = {
            "model": model_id,
            "messages": [
                {"role": m.role, "content": m.content} for m in effective_messages
            ],
            "temperature": temperature,
            "stream": False,
        }

        # Them response_format neu strategy co
        response_format = strategy.get("response_format")
        if response_format is not None:
            payload["response_format"] = response_format

        return payload

    # === Streaming ===

    def generate_stream(
        self,
        messages: List[LLMMessage],
        model_id: str,
        temperature: float = 0.7,
    ) -> Generator[StreamChunk, None, None]:
        """
        Stream response tu Chat Completions API (Server-Sent Events).

        Yields tung StreamChunk voi noi dung delta text.
        Chunk cuoi cung co done=True.

        Su dung try/finally de dam bao dong HTTP connection
        khi generator bi close hoac gap exception giua chung.

        Args:
            messages: Chuoi hoi thoai
            model_id: Model ID
            temperature: Do sang tao

        Yields:
            StreamChunk voi delta text va trang thai
        """
        if not self.is_configured():
            raise ConnectionError("Provider chua duoc cau hinh. Vui long nhap API Key.")

        payload = self._build_chat_payload(
            messages=messages,
            model_id=model_id,
            temperature=temperature,
            stream=True,
        )

        url = f"{self._base_url}/chat/completions"
        headers = self._build_headers()
        response = None

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=_STREAM_TIMEOUT,
                stream=True,
            )
            self._check_response_error(response)

            # Doc tung dong cua SSE stream
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                # SSE format: "data: {json}"
                if not line.startswith("data: "):
                    continue

                data_str = line[6:]  # Cat bo "data: " prefix

                # Stream ket thuc
                if data_str.strip() == "[DONE]":
                    yield StreamChunk(delta="", done=True)
                    return

                try:
                    chunk_data = json.loads(data_str)
                    choices = chunk_data.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        finish = choices[0].get("finish_reason")
                        yield StreamChunk(
                            delta=content,
                            done=(finish is not None),
                        )
                except json.JSONDecodeError:
                    logger.warning("Khong parse duoc SSE chunk: %s", data_str[:100])
                    continue

        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(
                f"Khong the ket noi toi {self._base_url}. Chi tiet: {e}"
            ) from e
        except requests.exceptions.Timeout:
            raise ConnectionError(f"Stream timeout khi goi model {model_id}.")
        finally:
            # Dam bao dong HTTP connection khi xong hoac gap loi
            # Tranh connection leak khi generator bi close giua chung
            if response is not None:
                response.close()

    # === Private Helpers ===

    def _build_headers(self) -> Dict[str, str]:
        """Tao HTTP headers chung cho moi request."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

    def _build_chat_payload(
        self,
        messages: List[LLMMessage],
        model_id: str,
        temperature: float,
        stream: bool,
    ) -> Dict[str, Any]:
        """Tao request body cho Chat Completions API (non-structured)."""
        return {
            "model": model_id,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "stream": stream,
        }

    def _check_response_error(self, response: requests.Response) -> None:
        """
        Kiem tra HTTP response va raise exception neu co loi.

        Raises:
            PermissionError: 401/403 - API key khong hop le
            ConnectionError: 4xx/5xx khac
        """
        if response.status_code == 401:
            raise PermissionError(
                "API Key khong hop le. Vui long kiem tra lai trong Settings."
            )
        if response.status_code == 403:
            raise PermissionError(
                "Khong co quyen truy cap model nay. Kiem tra API Key permissions."
            )
        if response.status_code == 404:
            raise ConnectionError(
                f"Endpoint khong ton tai: {response.url}. "
                f"Kiem tra Base URL trong Settings."
            )
        if response.status_code == 429:
            raise ConnectionError(
                "Rate limit exceeded. Vui long cho vai giay roi thu lai."
            )
        if response.status_code >= 400:
            # Doc error message tu body neu co
            try:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", response.text)
            except (json.JSONDecodeError, AttributeError):
                error_msg = response.text
            raise ConnectionError(f"API Error ({response.status_code}): {error_msg}")

    def _parse_chat_response(self, data: Dict[str, Any]) -> LLMResponse:
        """Parse JSON response tu Chat Completions API thanh LLMResponse."""
        choices = data.get("choices", [])
        content = ""
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content", "")

        usage_data = data.get("usage")
        usage = None
        if usage_data:
            usage = {
                "prompt_tokens": usage_data.get("prompt_tokens", 0),
                "completion_tokens": usage_data.get("completion_tokens", 0),
                "total_tokens": usage_data.get("total_tokens", 0),
            }

        return LLMResponse(
            content=content,
            model=data.get("model", ""),
            usage=usage,
            raw=data,
        )
