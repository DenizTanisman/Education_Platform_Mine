# Modül 5 — Final Görevi

## Amaç

M3'te LLM'e mesaj gönderip metin aldın. M4'te yapısal JSON aldın. **Şimdi
LLM'e Python fonksiyonları veriyorsun, LLM bu fonksiyonları kendisi
çağırmaya karar veriyor**, sonuçları geri veriyorsun, LLM final cevabı
üretiyor. Bu **agent'ın başlangıcıdır**.

> Bu modül LLM uygulamalarının en heyecanlı kısmıdır. Buradan sonra
> "chatbot" değil "asistan" — kendi başına araç kullanan, çoklu adım
> planlayan bir sistem yazıyorsun.

---

## Ön Hazırlık

```bash
mkdir m05-final && cd m05-final

python -m venv venv
source venv/bin/activate

cat > requirements.txt << EOF
openai>=1.50
pydantic>=2.5
python-dotenv>=1.0
EOF

pip install -r requirements.txt
echo "OPENAI_API_KEY=sk-proj-..." > .env
echo ".env" >> .gitignore
```

---

## Görev Tanımı

`agent.py` adında **tek bir dosya** oluştur. İçinde:

- 2 Pydantic schema (`GetWeatherInput`, `CalculateInput`)
- 1 `Tool` dataclass
- 1 `ToolRegistry` class
- 1 `AgentError` exception
- 4 fonksiyon (`get_weather_handler`, `calculate_handler`, `build_default_registry`, `run_agent`)
- CLI giriş noktası

---

### Tool dataclass

```python
from dataclasses import dataclass
from typing import Awaitable, Callable, Any
from pydantic import BaseModel

@dataclass
class Tool:
    name: str
    description: str
    input_schema: type[BaseModel]   # Pydantic class (M4 ile aynı pattern)
    handler: Callable[[BaseModel], Awaitable[Any]]  # async callable

    def to_openai_format(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema.model_json_schema(),
            },
        }
```

OpenAI'ın istediği tool format'ı bu — `type: "function"` üst seviye sarmalı,
`function` içinde `name`, `description`, `parameters` (JSON Schema).

---

### ToolRegistry

```python
@dataclass
class ToolRegistry:
    tools: dict[str, Tool] = field(default_factory=dict)

    def register(self, tool: Tool) -> None:
        if tool.name in self.tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self.tools[tool.name] = tool

    def to_openai_list(self) -> list[dict]:
        return [t.to_openai_format() for t in self.tools.values()]

    async def call(self, name: str, arguments: dict) -> Any:
        if name not in self.tools:
            raise AgentError(f"Unknown tool: {name}")
        tool = self.tools[name]
        parsed = tool.input_schema.model_validate(arguments)  # M4 pattern
        return await tool.handler(parsed)
```

`registry.call("get_weather", {"city": "İstanbul"})` üç şey yapar:
1. Tool'u isimden bul
2. JSON arguments'ı Pydantic instance'a parse et (M4'teki gibi)
3. Handler'ı çağır, sonucu döndür

---

### Tool handlers

```python
class GetWeatherInput(BaseModel):
    city: str = Field(description="Şehir adı, örn: 'İstanbul'")

class CalculateInput(BaseModel):
    expression: str = Field(description="Matematiksel ifade, örn: '(15+12)/2'")
```

**Handler 1 — `get_weather_handler`:**
```python
_MOCK_WEATHER = {
    "istanbul": {"temperature": 15, "condition": "parçalı bulutlu"},
    "ankara": {"temperature": 12, "condition": "açık"},
    # ...
}

async def get_weather_handler(input: GetWeatherInput) -> dict:
    key = input.city.strip().lower().replace("\u0307", "")  # Türkçe normalize
    if key not in _MOCK_WEATHER:
        return {"error": f"'{input.city}' için veri yok"}
    return {
        "city": input.city,
        "temperature_celsius": _MOCK_WEATHER[key]["temperature"],
        "condition": _MOCK_WEATHER[key]["condition"],
    }
```

> **Türkçe locale tuzağı:** `'İstanbul'.lower()` → `'i̇stanbul'` (combining dot
> above) — Python'un Türkçe kuralı. `.replace("\u0307", "")` ile temizle.

**Handler 2 — `calculate_handler`:**
```python
async def calculate_handler(input: CalculateInput) -> dict:
    safe_chars = set("0123456789+-*/(). %")
    expr = input.expression.strip()
    if not all(c in safe_chars or c.isalpha() for c in expr):
        return {"error": f"Geçersiz karakter: {expr!r}"}

    try:
        # __builtins__ boş = kısıtlı eval
        result = eval(expr, {"__builtins__": {}}, {"abs": abs, "min": min, "max": max})
    except Exception as e:
        return {"error": f"Hesaplama hatası: {e}"}

    return {"expression": expr, "result": result}
```

> **Güvenlik notu:** `eval()` genelde tehlikeli ama burada whitelist + boş
> `__builtins__` ile evren çok dar. Production'da `simpleeval` veya `ast`
> tabanlı parser daha güvenli.

---

### Exception — `AgentError`

```python
class AgentError(Exception):
    pass
```

Şunlar için kullanılır:
- API çağrısı hatası
- Bilinmeyen tool adı
- max_iters tükendi

---

### Fonksiyon — `run_agent` (kalp)

**İmza:**
```python
async def run_agent(
    user_message: str,
    client,
    tool_registry: ToolRegistry,
    model: str = "gpt-4o-mini",
    max_iters: int = 5,
    temperature: float = 0.0,
) -> str:
    ...
```

**Davranış (agent loop):**

1. Boş mesaj → `ValueError` (API çağrısı yapma)
2. `messages` listesi başlat: `[system, user]`
3. `for iter in range(max_iters)`:
   - LLM'i çağır (`client.chat.completions.create(tools=registry.to_openai_list(), tool_choice="auto")`)
   - Response alındı:
     - **`tool_calls` boşsa:** `message.content` döndür → loop biter
     - **`tool_calls` varsa:**
       - Assistant mesajını messages'a ekle (tool_calls dahil)
       - Her tool_call'ı çalıştır (paralel `asyncio.gather`)
       - Her sonuç için `{"role": "tool", "tool_call_id": ..., "content": json.dumps(result)}` mesajı ekle
       - Loop devam eder
4. Loop biter ama hâlâ tool_call istiyorsa → `AgentError("max iters exhausted")`

**Kritik mesaj formatları:**

```python
# Assistant tool call yaparsa kaydet:
messages.append({
    "role": "assistant",
    "content": message.content,  # None olabilir
    "tool_calls": [
        {
            "id": tc.id,
            "type": "function",
            "function": {
                "name": tc.function.name,
                "arguments": tc.function.arguments,
            },
        }
        for tc in tool_calls
    ],
})

# Her tool sonucu:
messages.append({
    "role": "tool",
    "tool_call_id": tool_call_id,
    "content": json.dumps(result, ensure_ascii=False),
})
```

`tool_call_id` kritik — model hangi cevap hangi çağrıya ait olduğunu bundan anlıyor.

---

## Kullanım Örneği

```bash
python agent.py --message "İstanbul ve Ankara'nın sıcaklık ortalaması nedir?"
```

Beklenen akış (loglarda görünür):
```
iter 1: LLM "get_weather(city='İstanbul')" + "get_weather(city='Ankara')" çağırıyor
        İki tool paralel çalışıyor → sonuçlar
iter 2: LLM "calculate(expression='(15+12)/2')" çağırıyor
        Hesap → 13.5
iter 3: LLM final cevap: "İstanbul 15°C, Ankara 12°C, ortalama 13.5°C."
```

Çıktı:
```json
{
  "answer": "İstanbul 15°C, Ankara 12°C. Ortalama 13.5°C."
}
```

---

## Test Edilecek Davranışlar

| Grup | Test sayısı | Neyi kontrol eder |
|---|---|---|
| Tool tanımı | 3 | Registry register/call, OpenAI format, default registry |
| Agent loop | 3 | Tek-iter cevap, tool→sonuç→cevap, tools param geçilmiş |
| Hata yönetimi | 3 | Empty message, max_iters, API error wrapping |
| Tool yürütme | 3 | Pydantic input parse, unknown tool, parallel execution |

**Toplam:** 12 test.

---

## OpenAI vs Anthropic — Tool Calling

İki SDK çok benzer (M4'tekinden daha az farklı):

| Konu | OpenAI | Anthropic |
|---|---|---|
| Method | `client.chat.completions.create(tools=[...])` | `client.messages.create(tools=[...])` |
| Tool format | `{"type":"function", "function":{name, description, parameters}}` | `{name, description, input_schema}` (üst sarmalı yok) |
| Tool call | `message.tool_calls[i].function.name/arguments` | `message.content[i].input/name/id` (content içinde gömülü) |
| Tool result | `{"role":"tool", "tool_call_id":id, "content":...}` | `{"role":"user", "content":[{"type":"tool_result","tool_use_id":id,"content":...}]}` |

İki SDK'da agent loop **kavramsal olarak aynı**: çağır → tool kullanılırsa execute
et → sonucu geri ver → cevap gelene kadar tekrarla. Sadece messaj formatları farklı.

---

## Teslim Formatı

```
solution.zip
├── agent.py
└── requirements.txt
```

---

## İpuçları

### `tool_choice` parametresi

```python
tool_choice="auto"      # default, model karar verir
tool_choice="required"  # model MUTLAKA tool çağırmalı
tool_choice="none"      # model tool kullanamaz
tool_choice={"type": "function", "function": {"name": "calculate"}}  # belli bir tool zorunlu
```

Bu kursta `"auto"` yeterli.

### Paralel tool execution

```python
# YANLIŞ — sequential
for tc in tool_calls:
    result = await registry.call(tc.function.name, json.loads(tc.function.arguments))
    messages.append({"role": "tool", ...})

# DOĞRU — parallel (M3'teki summarize_many pattern'i)
async def _execute(tc):
    args = json.loads(tc.function.arguments)
    return tc.id, await registry.call(tc.function.name, args)

results = await asyncio.gather(*(_execute(tc) for tc in tool_calls))
for tool_call_id, result in results:
    messages.append({"role": "tool", "tool_call_id": tool_call_id, ...})
```

### Pydantic helper

OpenAI SDK'da `pydantic_function_tool(MyInput)` helper'ı var, Pydantic class'ından
tool format üretir. Ama biz manuel yapıyoruz çünkü daha açık ve dependency'siz.

### Production'da neler eksik?

Bu basit agent şunları yapmıyor:
- Streaming response (token token cevap)
- Tool error retry (LLM tool hatası gördüğünde nasıl davranmalı?)
- Memory (M6'da geliyor)
- Cost tracking (kaç token harcandı)
- Tracing (OpenTelemetry, LangSmith)

M8 capstone'da bunların bazıları eklenecek.

---

## Anti-pattern Uyarıları

- ❌ **Sequential tool execution** — `for tc: await ...` yerine `asyncio.gather`
- ❌ **`tool_call_id` atlamak** — model cevabı eşleştiremez, hata verir
- ❌ **`max_iters` koymamak** — LLM sonsuz tool çağırabilir, kontrol kaybedersin
- ❌ **`tool_choice="required"` her zaman** — basit sorularda bile tool çağırır, yavaşlar
- ❌ **Tool handler'da raw dict** — Pydantic parse et, validation alırsın

---

## Önerilen Kaynaklar

- [OpenAI Function Calling Guide](https://platform.openai.com/docs/guides/function-calling)
- [Anthropic Tool Use Guide](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview)
- [LangChain Agents](https://python.langchain.com/docs/modules/agents/) — daha gelişmiş agent pattern'leri
- [ReAct paper](https://arxiv.org/abs/2210.03629) — tool kullanan agent'ların ilk akademik makalesi
