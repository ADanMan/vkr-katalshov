"""
flv.llm.mock — детерминированный stub LLM-провайдера для unit-тестов
и работы без реального API-ключа.

MockProvider возвращает заранее заданные ответы по заголовку запроса
(простой routing по подстроке) или один общий ответ. Поддерживает
structured output (если задан response_model — заданный canned-ответ
парсится через response_model.model_validate_json).

Использование:

    provider = MockProvider(canned={"извлеки": '{"states": ["INIT"]}'})
    text = provider.complete("Извлеки DSL из методики", model="mock/dummy")
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MockProvider:
    """Stub-провайдер для тестов."""

    canned: Mapping[str, str] = field(default_factory=dict)
    default_response: str = "{}"
    name: str = field(default="mock", init=False)

    def complete(
        self,
        prompt: str,
        *,
        model: str | None = None,
        response_model: type[Any] | None = None,
        temperature: float = 0.0,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> Any:
        text = self._lookup(prompt)
        if response_model is not None:
            return response_model.model_validate_json(text)
        return text

    def _lookup(self, prompt: str) -> str:
        for key, response in self.canned.items():
            if key.lower() in prompt.lower():
                return response
        return self.default_response


__all__ = ["MockProvider"]
