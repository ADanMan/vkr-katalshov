"""
flv.llm.openrouter — провайдер LLM через сервис OpenRouter.

OpenRouter — единая абстракция над несколькими провайдерами LLM
с OpenAI-совместимым API. Это позволяет в одном коде вызывать
Gemini, GPT, Claude, DeepSeek, Qwen и т.д. через `openai`-SDK,
просто меняя `model_id`.

Согласно ADR-002 Phase 5 фиксирует пятёрку моделей:

* `google/gemini-flash-3` — быстрая, дешёвая.
* `openai/gpt-5.4` — баланс цена/качество.
* `anthropic/claude-sonnet-4.6` — точная, для критичных фрагментов.
* `deepseek/deepseek-v4-flash` — open-weight альтернатива.
* `qwen/qwen3.6-flash` — open-weight, китайская научная база.

API-ключ берётся из переменной окружения `OPENROUTER_API_KEY`
(контракт security.md: никогда не хардкодить ключи).

Если зависимость `openai` или `tenacity` не установлена,
конструктор падает с осмысленным сообщением — это вынуждает
пользователя сделать `pip install -e ".[llm]"`.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Каноничные имена моделей для эксперимента Phase 5 (ADR-002 §3 Role 1).
SUPPORTED_MODELS: tuple[str, ...] = (
    "google/gemini-flash-3",
    "openai/gpt-5.4",
    "anthropic/claude-sonnet-4.6",
    "deepseek/deepseek-v4-flash",
    "qwen/qwen3.6-flash",
)

DEFAULT_MODEL = "anthropic/claude-sonnet-4.6"


@dataclass
class OpenRouterProvider:
    """LLM-провайдер для OpenRouter API.

    Реализует Protocol `flv.core.LlmProvider`.
    """

    api_key: str | None = None
    base_url: str = OPENROUTER_BASE_URL
    default_model: str = DEFAULT_MODEL
    timeout_s: float = 60.0
    max_retries: int = 3
    name: str = field(default="openrouter", init=False)

    def __post_init__(self) -> None:
        # API-ключ — приоритет: явный аргумент > env. Никогда не
        # принимаем хардкод в коде (security.md).
        if not self.api_key:
            self.api_key = os.environ.get("OPENROUTER_API_KEY")
        # Lazy lookup tenacity / openai — модуль может импортироваться
        # без них (например, для тестов с MockProvider).

    # ──────────────────────────────────────────────────────────────────

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
        """Запросить LLM через OpenRouter.

        Параметры
        ---------
        prompt : текст запроса.
        model : id модели (например, 'anthropic/claude-sonnet-4.6').
            Если None — используется `default_model`. Если задан и
            не из SUPPORTED_MODELS — выводится warning, но запрос
            всё равно отправляется (для экспериментов с другими).
        response_model : pydantic-модель для structured output.
            Если задана — ответ парсится в неё через response_format.
        temperature : 0.0 для воспроизводимости (Phase 5).
        system : опциональный system-prompt.
        max_tokens : ограничение длины ответа.

        Возвращает
        ----------
        Если задан response_model — pydantic-объект.
        Иначе — сырой текст (str).
        """
        if not self.api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY не задан. Экспортируй переменную "
                "окружения или передай api_key= в конструктор."
            )

        model_id = model or self.default_model
        if model_id not in SUPPORTED_MODELS:
            logger.warning(
                "Модель %r не входит в SUPPORTED_MODELS пятёрки Phase 5; "
                "используется как есть.",
                model_id,
            )

        client = self._get_client()

        # Сообщения OpenAI-формата
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if response_model is not None:
            # Используем JSON-Mode + хранение схемы pydantic
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "schema": response_model.model_json_schema(),
                    "strict": True,
                },
            }

        # Retry с экспоненциальным backoff (если установлен tenacity)
        @self._retry_decorator()
        def _do_call() -> Any:
            return client.chat.completions.create(**kwargs)

        response = _do_call()
        text = response.choices[0].message.content or ""
        if response_model is not None:
            return response_model.model_validate_json(text)
        return text

    # ──────────────────────────────────────────────────────────────────

    def _get_client(self) -> Any:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Нужен пакет openai. Установи: pip install -e \".[llm]\""
            ) from exc
        return OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout_s,
            default_headers={
                # OpenRouter рекомендует помечать клиентов
                "HTTP-Referer": "https://github.com/ADanMan/vkr-katalshov",
                "X-Title": "vkr-katalshov-flv",
            },
        )

    def _retry_decorator(self):  # type: ignore[no-untyped-def]
        """Вернуть декоратор с retry (если tenacity установлен) или
        no-op identity-декоратор."""
        try:
            from tenacity import (
                retry,
                retry_if_exception_type,
                stop_after_attempt,
                wait_exponential,
            )
        except ImportError:  # pragma: no cover
            def _identity(fn):  # type: ignore[no-untyped-def]
                return fn

            return _identity

        return retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        )


__all__ = ["OpenRouterProvider", "SUPPORTED_MODELS", "DEFAULT_MODEL"]
