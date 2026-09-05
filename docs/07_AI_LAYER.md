# AI Layer

## Overview

AI-слой RusEquity Terminal поддерживает два режима работы:
1. **Remote API** — облачные LLM (OpenAI, Anthropic)
2. **Local LLM** — локальные модели через Ollama, LM Studio

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Flutter)                       │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   AI Service (Backend)                      │
│  ┌─────────────────┐         ┌─────────────────────────┐   │
│  │  Request Router │         │   Response Processor    │   │
│  │                 │         │                         │   │
│  │ - Validate      │         │ - Parse                 │   │
│  │ - Select Model  │         │ - Validate              │   │
│  │ - Rate Limit    │         │ - Cache                 │   │
│  └─────────────────┘         └─────────────────────────┘   │
│           │                          ▲                      │
│           ▼                          │                      │
│  ┌─────────────────┐         ┌─────────────────────────┐   │
│  │  Remote API     │         │    Local LLM            │   │
│  │  Client         │         │    Client               │   │
│  │                 │         │                         │   │
│  │ - OpenAI GPT    │         │ - Ollama                │   │
│  │ - Anthropic     │         │ - LM Studio             │   │
│  │ - etc.          │         │ - etc.                  │   │
│  └─────────────────┘         └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Data Context Provider                          │
│  - Stock data                                               │
│  - Analytics metrics                                        │
│  - Historical context                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. Remote API Integration

### 1.1 Supported Providers

| Provider | Models | Use Case |
|----------|--------|----------|
| OpenAI | gpt-4o, gpt-4-turbo, gpt-3.5-turbo | General insights, summaries |
| Anthropic | claude-3-opus, claude-3-sonnet, claude-3-haiku | Analysis, reasoning |
| Google | gemini-pro | Alternative option |

### 1.2 Configuration

```yaml
# config/ai_remote.yaml
remote_api:
  openai:
    api_key_env: OPENAI_API_KEY
    base_url: https://api.openai.com/v1
    models:
      default: gpt-4-turbo
      fast: gpt-3.5-turbo
    
  anthropic:
    api_key_env: ANTHROPIC_API_KEY
    base_url: https://api.anthropic.com/v1
    models:
      default: claude-3-sonnet-20240229
      fast: claude-3-haiku-20240307
  
  rate_limits:
    requests_per_minute: 60
    tokens_per_minute: 100000
```

### 1.3 Implementation Example

```python
# src/ai/remote_api.py

from abc import ABC, abstractmethod
from typing import Optional, List, Dict
import os

class RemoteAIClient(ABC):
    @abstractmethod
    async def generate(self, prompt: str, context: Dict) -> str:
        pass
    
    @abstractmethod
    async def stream(self, prompt: str, context: Dict):
        pass

class OpenAIClient(RemoteAIClient):
    def __init__(self, api_key: str, model: str = "gpt-4-turbo"):
        self.api_key = api_key
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key)
    
    async def generate(self, prompt: str, context: Dict) -> str:
        messages = self._build_messages(prompt, context)
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
            max_tokens=1000
        )
        
        return response.choices[0].message.content
    
    def _build_messages(self, prompt: str, context: Dict) -> List[Dict]:
        system_message = {
            "role": "system",
            "content": self._get_system_prompt()
        }
        
        context_message = {
            "role": "user",
            "content": self._format_context(context)
        }
        
        user_message = {
            "role": "user",
            "content": prompt
        }
        
        return [system_message, context_message, user_message]
    
    def _get_system_prompt(self) -> str:
        return """Ты — финансовый аналитик, специализирующийся на российском рынке акций.
Твоя задача — предоставлять точные, объективные инсайты на основе данных.
Всегда указывай источники данных и дату анализа.
Не давай инвестиционных рекомендаций, только анализ."""
    
    def _format_context(self, context: Dict) -> str:
        # Форматирование контекстных данных
        lines = ["Контекст для анализа:"]
        for key, value in context.items():
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)


class AnthropicClient(RemoteAIClient):
    def __init__(self, api_key: str, model: str = "claude-3-sonnet-20240229"):
        self.api_key = api_key
        self.model = model
        self.client = AsyncAnthropic(api_key=api_key)
    
    async def generate(self, prompt: str, context: Dict) -> str:
        # Similar implementation for Anthropic
        pass
```

---

## 2. Local LLM Support

### 2.1 Supported Runtimes

| Runtime | Models | Use Case |
|---------|--------|----------|
| Ollama | llama-3, mistral, mixtral | Offline analysis, privacy |
| LM Studio | Any GGUF model | Local development |
| vLLM | Various | High-throughput local serving |

### 2.2 Configuration

```yaml
# config/ai_local.yaml
local_llm:
  ollama:
    base_url: http://localhost:11434
    models:
      default: llama3:8b
      large: mixtral:8x7b
    
  lm_studio:
    base_url: http://localhost:1234/v1
    models:
      default: local-model
  
  fallback_to_remote: true  # Если локальная модель недоступна
```

### 2.3 Implementation Example

```python
# src/ai/local_llm.py

import aiohttp
from typing import Optional, Dict

class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3:8b"):
        self.base_url = base_url
        self.model = model
    
    async def generate(self, prompt: str, context: Dict) -> str:
        full_prompt = self._build_prompt(prompt, context)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "max_tokens": 1000
                    }
                }
            ) as response:
                result = await response.json()
                return result["response"]
    
    async def stream(self, prompt: str, context: Dict):
        full_prompt = self._build_prompt(prompt, context)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": True
                }
            ) as response:
                async for line in response.content:
                    yield line.decode()
    
    def _build_prompt(self, prompt: str, context: Dict) -> str:
        context_str = "\n".join(f"- {k}: {v}" for k, v in context.items())
        return f"""Контекст:
{context_str}

Вопрос: {prompt}

Ответ:"""
    
    async def list_models(self) -> List[str]:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/api/tags") as response:
                result = await response.json()
                return [model["name"] for model in result["models"]]
```

---

## 3. Prompt Templates

### 3.1 Stock Summary

```
Ты — финансовый аналитик. Проанализируй следующую компанию:

КОНТЕКСТ:
- Тикер: {ticker}
- Название: {company_name}
- Сектор: {sector}
- Текущая цена: {price} RUB
- P/E: {pe_ratio} (перцентиль: {pe_percentile}%)
- EV/EBITDA: {ev_ebitda} (перцентиль: {ev_ebitda_percentile}%)
- ROE: {roe}%
- ROIC: {roic}%
- Дивдоходность: {dividend_yield}%
- Total Return 1Y: {tr_1y}%
- Relative Strength 1Y: {rs_1y}%

ЗАДАЧА:
Составь краткий аналитический отчёт (максимум 200 слов) включающий:
1. Оценку текущей стоимости (дорого/дешево)
2. Качество бизнеса (рентабельность, эффективность)
3. Дивидендную привлекательность
4. Главный риск

Отвечай на русском языке.
```

### 3.2 Q&A on Financials

```
Ты — эксперт по финансовой отчётности. Ответь на вопрос пользователя, 
используя предоставленные данные.

КОНТЕКСТ:
{financial_data_json}

ВОПРОС:
{user_question}

ТРЕБОВАНИЯ:
- Используй только предоставленные данные
- Указывай конкретные цифры
- Если данных недостаточно, скажи об этом
- Отвечай на русском языке
```

### 3.3 Alert Explanation

```
Ты — аналитик системы алертов. Объясни пользователю причину срабатывания алерта.

АЛЕРТ:
- Тип: {alert_type}
- Тикер: {ticker}
- Триггер: {trigger_condition}
- Текущее значение: {current_value}
- Порог: {threshold}

КОНТЕКСТ:
{historical_context}

ЗАДАЧА:
Объясни простыми словами:
1. Что произошло
2. Почему это важно
3. На что обратить внимание

Отвечай на русском языке, максимум 100 слов.
```

---

## 4. Response Processing

### 4.1 Validation

```python
def validate_ai_response(response: str, expected_type: str) -> bool:
    """Валидация ответа от AI."""
    
    if not response or len(response.strip()) == 0:
        return False
    
    if expected_type == "json":
        try:
            json.loads(response)
            return True
        except json.JSONDecodeError:
            return False
    
    if expected_type == "summary":
        # Проверка длины
        word_count = len(response.split())
        return 50 <= word_count <= 300
    
    return True
```

### 4.2 Caching

```python
# Кэширование ответов для одинаковых запросов
from hashlib import sha256
import redis

class AICache:
    def __init__(self, redis_client: redis.Redis, ttl: int = 3600):
        self.redis = redis_client
        self.ttl = ttl
    
    def _get_key(self, prompt: str, context: Dict) -> str:
        content = f"{prompt}:{sorted(context.items())}"
        return f"ai_cache:{sha256(content.encode()).hexdigest()}"
    
    async def get(self, prompt: str, context: Dict) -> Optional[str]:
        key = self._get_key(prompt, context)
        return self.redis.get(key)
    
    async def set(self, prompt: str, context: Dict, response: str):
        key = self._get_key(prompt, context)
        self.redis.setex(key, self.ttl, response)
```

---

## 5. Use Cases

### 5.1 Stock Summary Generation

**Trigger:** User opens stock detail page

**Flow:**
1. Fetch latest analytics data
2. Build prompt with context
3. Call AI (remote or local)
4. Display summary to user

### 5.2 Financial Q&A

**Trigger:** User asks question about company

**Flow:**
1. Parse user question
2. Retrieve relevant financial data
3. Send to AI with context
4. Stream response to UI

### 5.3 Alert Explanation

**Trigger:** Analytic alert triggered

**Flow:**
1. Capture alert details
2. Get historical context
3. Generate explanation via AI
4. Show notification with explanation

### 5.4 Report Summarization

**Trigger:** New financial report available

**Flow:**
1. Extract key data from report
2. Send to AI for summarization
3. Store summary in database
4. Notify users

---

## 6. Security & Privacy

### 6.1 API Key Management

```bash
# Хранение ключей в environment variables
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Никогда не коммитить ключи в репозиторий!**

### 6.2 Data Minimization

- Отправлять в AI только необходимые данные
- Не передавать персональные данные пользователей
- Анонимизировать данные при возможности

### 6.3 Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/ai/generate")
@limiter.limit("10/minute")
async def generate_insight(request: Request, ...):
    ...
```

---

## 7. Testing

### 7.1 Unit Tests

```python
async def test_openai_client_generate():
    client = OpenAIClient(api_key="test-key")
    
    context = {"ticker": "SBER", "pe_ratio": 5.2}
    response = await client.generate("Дай оценку", context)
    
    assert len(response) > 0
    assert isinstance(response, str)
```

### 7.2 Integration Tests

```python
async def test_ai_service_with_mock():
    mock_client = MockAIClient()
    mock_client.generate.return_value = "Test response"
    
    service = AIService(client=mock_client)
    result = await service.analyze_stock("SBER")
    
    assert result is not None
    mock_client.generate.assert_called_once()
```

---

## Version History

| Version | Date       | Changes                    |
|---------|------------|----------------------------|
| 1.0     | 2025-01-XX | Initial AI layer spec      |
