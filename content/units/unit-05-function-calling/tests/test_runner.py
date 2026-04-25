"""
M5 — Final test runner.

Tests the function-calling agent from agent.py.

Test groups (must match unit.yaml):
  - "Tool tanımı"            — Tool dataclass, registry, OpenAI format
  - "Agent loop"             — single-iter answer, tool call → result → final
  - "Hata yönetimi"          — empty msg, unknown tool, max_iters exhausted
  - "Tool yürütme"           — handler called, args parsed, parallel execution
"""

import asyncio
import json
import os
import sys
import tempfile
from unittest.mock import MagicMock

# In platform sandbox, student code is at /workspace/code
sys.path.insert(0, '/workspace/code')

from harness_api import TestResult, TestGroup


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_tests() -> list[TestGroup]:
    groups = []

    g1 = TestGroup(name="Tool tanımı")
    _test_tool_definition(g1)
    groups.append(g1)

    g2 = TestGroup(name="Agent loop")
    _test_agent_loop(g2)
    groups.append(g2)

    g3 = TestGroup(name="Hata yönetimi")
    _test_error_handling(g3)
    groups.append(g3)

    g4 = TestGroup(name="Tool yürütme")
    _test_tool_execution(g4)
    groups.append(g4)

    return groups


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_import(g: TestGroup, test_id: str):
    try:
        import agent
        return agent
    except Exception as e:
        g.add(TestResult(
            id=test_id,
            status="errored",
            detail=f"agent.py içe aktarılamadı: {e.__class__.__name__}: {e}",
            hint="Dosya adı agent.py olmalı; Tool, ToolRegistry, run_agent, AgentError tanımlı mı?",
        ))
        return None


def _make_response(content=None, tool_calls=None):
    """Build a mock chat completion response."""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _make_tool_call(call_id, name, args_dict):
    """Build a mock tool_call object."""
    tc = MagicMock()
    tc.id = call_id
    tc.function = MagicMock()
    tc.function.name = name
    tc.function.arguments = json.dumps(args_dict)
    return tc


def _make_scripted_client(responses_list):
    """Mock client that returns scripted responses in order, recording calls."""
    client = MagicMock()
    client._call_log = []
    iter_responses = iter(responses_list)

    async def fake_create(**kwargs):
        client._call_log.append(kwargs)
        try:
            return next(iter_responses)
        except StopIteration:
            # Default: model gives final answer
            return _make_response(content="<exhausted>")

    client.chat.completions.create = fake_create
    return client


def _run_async(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Group 1 — Tool definition
# ---------------------------------------------------------------------------

def _test_tool_definition(g: TestGroup) -> None:
    agent = _safe_import(g, "test_registry_register_and_call")
    if agent is None:
        return

    # 1.1: Registry can register tools and call them by name
    try:
        registry = agent.ToolRegistry()
        tool_called = []

        async def my_handler(input):
            tool_called.append(input.x)
            return {"result": input.x * 2}

        from pydantic import BaseModel

        class MyInput(BaseModel):
            x: int

        registry.register(agent.Tool(
            name="double",
            description="Double a number",
            input_schema=MyInput,
            handler=my_handler,
        ))

        result = _run_async(registry.call("double", {"x": 21}))
        if result == {"result": 42} and tool_called == [21]:
            g.add(TestResult(id="test_registry_register_and_call", status="passed"))
        else:
            g.add(TestResult(
                id="test_registry_register_and_call",
                status="failed",
                input='registry.call("double", {"x": 21})',
                expected="{'result': 42}",
                actual=repr(result),
                hint="ToolRegistry.call() handler'ı parsed input ile çağırmalı, sonuçu döndürmeli",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_registry_register_and_call",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
            hint="Tool dataclass'ı (name, description, input_schema, handler) ve ToolRegistry tanımlı mı?",
        ))

    # 1.2: to_openai_list returns correctly shaped tool entries
    try:
        registry = agent.build_default_registry()
        tools = registry.to_openai_list()
        if not isinstance(tools, list) or not tools:
            g.add(TestResult(
                id="test_openai_format_correct",
                status="failed",
                input='build_default_registry().to_openai_list()',
                expected="non-empty list of tool dicts",
                actual=repr(tools)[:80],
                hint="to_openai_list() liste döndürmeli, boş olmamalı",
            ))
        else:
            first = tools[0]
            ok = (
                first.get("type") == "function"
                and "function" in first
                and "name" in first["function"]
                and "description" in first["function"]
                and "parameters" in first["function"]
            )
            if ok:
                g.add(TestResult(id="test_openai_format_correct", status="passed"))
            else:
                g.add(TestResult(
                    id="test_openai_format_correct",
                    status="failed",
                    input='to_openai_list() entry shape',
                    expected='{"type":"function", "function": {"name", "description", "parameters"}}',
                    actual=repr(first)[:120],
                    hint='Her tool {"type":"function", "function":{...}} formatında olmalı',
                ))
    except Exception as e:
        g.add(TestResult(
            id="test_openai_format_correct",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 1.3: Default registry has weather + calculate tools
    try:
        registry = agent.build_default_registry()
        names = set(registry.tools.keys())
        if {"get_weather", "calculate"} <= names:
            g.add(TestResult(id="test_default_registry_has_tools", status="passed"))
        else:
            g.add(TestResult(
                id="test_default_registry_has_tools",
                status="failed",
                input='build_default_registry().tools.keys()',
                expected='{"get_weather", "calculate"} subset',
                actual=f"got {sorted(names)}",
                hint="build_default_registry() get_weather ve calculate tool'larını eklemeli",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_default_registry_has_tools",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))


# ---------------------------------------------------------------------------
# Group 2 — Agent loop
# ---------------------------------------------------------------------------

def _test_agent_loop(g: TestGroup) -> None:
    agent = _safe_import(g, "test_single_iter_returns_text")
    if agent is None:
        return

    # 2.1: If model returns content with no tool_calls, agent returns it
    try:
        client = _make_scripted_client([
            _make_response(content="Direkt cevap.", tool_calls=None),
        ])
        registry = agent.build_default_registry()
        result = _run_async(agent.run_agent("Hello", client, registry))
        if result == "Direkt cevap.":
            g.add(TestResult(id="test_single_iter_returns_text", status="passed"))
        else:
            g.add(TestResult(
                id="test_single_iter_returns_text",
                status="failed",
                input='run_agent with model returning text only',
                expected='"Direkt cevap."',
                actual=repr(result),
                hint="Model tool_calls'suz cevap verirse content'i döndür",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_single_iter_returns_text",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 2.2: Tool call → result → final answer (2 iterations)
    try:
        client = _make_scripted_client([
            _make_response(content=None, tool_calls=[
                _make_tool_call("c1", "get_weather", {"city": "Istanbul"}),
            ]),
            _make_response(content="İstanbul 15°C.", tool_calls=None),
        ])
        registry = agent.build_default_registry()
        result = _run_async(agent.run_agent("İstanbul hava", client, registry))
        if result == "İstanbul 15°C." and len(client._call_log) == 2:
            g.add(TestResult(id="test_tool_call_then_answer", status="passed"))
        else:
            g.add(TestResult(
                id="test_tool_call_then_answer",
                status="failed",
                input='2-iter loop: tool call then final answer',
                expected='"İstanbul 15°C." after 2 API calls',
                actual=f"result={result!r}, calls={len(client._call_log)}",
                hint="Tool çağrısı sonrası messages'a tool result ekle, döngü devam etsin",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_tool_call_then_answer",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 2.3: tools parameter is passed in API calls
    try:
        client = _make_scripted_client([
            _make_response(content="OK", tool_calls=None),
        ])
        registry = agent.build_default_registry()
        _run_async(agent.run_agent("hello", client, registry))
        if client._call_log:
            kwargs = client._call_log[0]
            tools_param = kwargs.get("tools")
            if isinstance(tools_param, list) and len(tools_param) >= 2:
                g.add(TestResult(id="test_tools_param_passed", status="passed"))
            else:
                g.add(TestResult(
                    id="test_tools_param_passed",
                    status="failed",
                    input='run_agent(...) — first API call kwargs',
                    expected="tools=[...] non-empty list",
                    actual=f"tools = {tools_param!r}",
                    hint="create()'e tools=tool_registry.to_openai_list() geç",
                ))
        else:
            g.add(TestResult(
                id="test_tools_param_passed",
                status="errored",
                detail="No API call recorded",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_tools_param_passed",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))


# ---------------------------------------------------------------------------
# Group 3 — Error handling
# ---------------------------------------------------------------------------

def _test_error_handling(g: TestGroup) -> None:
    agent = _safe_import(g, "test_empty_message_rejected")
    if agent is None:
        return

    # 3.1: empty message rejected before any API call
    try:
        client = _make_scripted_client([])
        registry = agent.build_default_registry()
        try:
            _run_async(agent.run_agent("", client, registry))
            g.add(TestResult(
                id="test_empty_message_rejected",
                status="failed",
                input='run_agent("", ...)',
                expected="ValueError",
                actual="No exception",
                hint="Boş mesaj için ValueError fırlat (API çağrısı yapma)",
            ))
        except ValueError:
            if not client._call_log:
                g.add(TestResult(id="test_empty_message_rejected", status="passed"))
            else:
                g.add(TestResult(
                    id="test_empty_message_rejected",
                    status="failed",
                    input='run_agent("", ...)',
                    expected="ValueError BEFORE API call",
                    actual=f"ValueError raised after {len(client._call_log)} calls",
                    hint="Validation kontrolü API çağrısından önce yap",
                ))
    except Exception as e:
        g.add(TestResult(
            id="test_empty_message_rejected",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 3.2: max_iters exhausted -> AgentError
    try:
        # Always return tool call -> infinite loop
        responses = [
            _make_response(tool_calls=[
                _make_tool_call(f"c{i}", "get_weather", {"city": "Istanbul"}),
            ])
            for i in range(20)
        ]
        client = _make_scripted_client(responses)
        registry = agent.build_default_registry()
        try:
            _run_async(agent.run_agent("test", client, registry, max_iters=3))
            g.add(TestResult(
                id="test_max_iters_exhausted",
                status="failed",
                input='run_agent with max_iters=3, infinite tool calls',
                expected="AgentError after 3 iterations",
                actual="No exception",
                hint="for iter in range(max_iters) bitince AgentError fırlat",
            ))
        except agent.AgentError:
            g.add(TestResult(id="test_max_iters_exhausted", status="passed"))
    except Exception as e:
        g.add(TestResult(
            id="test_max_iters_exhausted",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 3.3: API error wrapped in AgentError
    try:
        bad_client = MagicMock()
        async def _boom(**kw):
            raise RuntimeError("rate limit")
        bad_client.chat.completions.create = _boom

        registry = agent.build_default_registry()
        try:
            _run_async(agent.run_agent("test", bad_client, registry))
            g.add(TestResult(
                id="test_api_error_wrapped",
                status="failed",
                input='run_agent with API raising RuntimeError',
                expected="AgentError",
                actual="No exception",
                hint="API çağrısını try/except ile sar, AgentError fırlat",
            ))
        except agent.AgentError:
            g.add(TestResult(id="test_api_error_wrapped", status="passed"))
        except RuntimeError:
            g.add(TestResult(
                id="test_api_error_wrapped",
                status="failed",
                input='API raising RuntimeError',
                expected="AgentError (wrapped)",
                actual="RuntimeError raised raw",
                hint="raise AgentError(...) from e ile sarmala",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_api_error_wrapped",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))


# ---------------------------------------------------------------------------
# Group 4 — Tool execution
# ---------------------------------------------------------------------------

def _test_tool_execution(g: TestGroup) -> None:
    agent = _safe_import(g, "test_tool_handler_called_with_parsed_input")
    if agent is None:
        return

    # 4.1: Tool handler is called with parsed Pydantic input (not raw dict)
    try:
        registry = agent.ToolRegistry()
        captured = []

        async def my_handler(input):
            # input should be a Pydantic instance, not a dict
            captured.append((type(input).__name__, input.x))
            return {"ok": True}

        from pydantic import BaseModel

        class MyInput(BaseModel):
            x: int

        registry.register(agent.Tool(
            name="check",
            description="d",
            input_schema=MyInput,
            handler=my_handler,
        ))

        _run_async(registry.call("check", {"x": 7}))

        if captured and captured[0] == ("MyInput", 7):
            g.add(TestResult(id="test_tool_handler_called_with_parsed_input", status="passed"))
        else:
            g.add(TestResult(
                id="test_tool_handler_called_with_parsed_input",
                status="failed",
                input='registry.call("check", {"x": 7})',
                expected="handler called with MyInput instance",
                actual=f"captured = {captured!r}",
                hint="Handler'a dict değil, input_schema.model_validate(...) ile parse edilmiş Pydantic instance ver",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_tool_handler_called_with_parsed_input",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 4.2: Unknown tool name -> AgentError when registry.call invoked
    try:
        registry = agent.build_default_registry()
        try:
            _run_async(registry.call("not_a_real_tool", {}))
            g.add(TestResult(
                id="test_unknown_tool_raises",
                status="failed",
                input='registry.call("not_a_real_tool", {})',
                expected="AgentError",
                actual="No exception",
                hint="Bilinmeyen tool adı için AgentError fırlat",
            ))
        except agent.AgentError:
            g.add(TestResult(id="test_unknown_tool_raises", status="passed"))
    except Exception as e:
        g.add(TestResult(
            id="test_unknown_tool_raises",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 4.3: Multiple tool calls in one iteration are all executed
    try:
        client = _make_scripted_client([
            _make_response(tool_calls=[
                _make_tool_call("c1", "get_weather", {"city": "Istanbul"}),
                _make_tool_call("c2", "get_weather", {"city": "Ankara"}),
            ]),
            _make_response(content="İki şehir okundu.", tool_calls=None),
        ])
        registry = agent.build_default_registry()
        result = _run_async(agent.run_agent("test", client, registry))

        # Inspect the SECOND API call's messages — should contain 2 tool result messages
        if len(client._call_log) >= 2:
            second_call_messages = client._call_log[1]["messages"]
            tool_role_count = sum(1 for m in second_call_messages if m.get("role") == "tool")
            if tool_role_count == 2 and result == "İki şehir okundu.":
                g.add(TestResult(id="test_multiple_tools_executed", status="passed"))
            else:
                g.add(TestResult(
                    id="test_multiple_tools_executed",
                    status="failed",
                    input='2 parallel tool calls in one response',
                    expected="2 tool result messages on next API call",
                    actual=f"tool messages: {tool_role_count}, result: {result!r}",
                    hint="Her tool_call için ayrı bir 'role':'tool' mesajı ekle (tool_call_id ile)",
                ))
        else:
            g.add(TestResult(
                id="test_multiple_tools_executed",
                status="failed",
                input='2 parallel tool calls',
                expected="2 API calls",
                actual=f"only {len(client._call_log)} call(s)",
                hint="Tool çağrılarını işle, sonra API'yı tekrar çağır",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_multiple_tools_executed",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))
