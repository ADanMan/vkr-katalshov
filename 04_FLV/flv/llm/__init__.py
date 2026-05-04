"""
flv.llm — LLM-провайдеры и промежуточные модули для Ролей 1 и 3
(ADR-002).

Встроенные провайдеры (entry-points group `flv.llm_provider`):
* `openrouter.OpenRouterProvider` — единая абстракция над пятёркой
  моделей через OpenRouter (Gemini Flash 3, GPT 5.4, Claude Sonnet
  4.6, DeepSeek V4 Flash, Qwen3.6 Flash).
* `mock.MockProvider` — детерминированный stub для unit-тестов.

Опциональные расширения (заглушки):
* anthropic — прямой Claude API.
* openai — прямой OpenAI API.
* onprem — локальные Llama/Yandex GPT.
"""

from .openrouter import OpenRouterProvider  # noqa: F401  (re-export для plugin discovery)
from .mock import MockProvider              # noqa: F401

__all__ = ["OpenRouterProvider", "MockProvider"]
