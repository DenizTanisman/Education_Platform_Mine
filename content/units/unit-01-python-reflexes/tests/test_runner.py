"""
M1 — Final test runner.

Tests the SQLite-backed CLI todo tool from solution.py.

Test groups (must match unit.yaml):
  - "Veritabanı işlemleri"       — add, list, complete (CRUD)
  - "Hata yönetimi"              — empty title, missing id
  - "Argparse yapısı"            — parser exists with required flags
  - "JSON çıktı formatı"         — list_tasks returns expected schema

Each test uses a fresh tempfile-based SQLite database so tests don't pollute
each other.
"""

import os
import sys
import tempfile
import time

# In platform sandbox, student code is at /workspace/code
sys.path.insert(0, '/workspace/code')

from harness_api import TestResult, TestGroup


# ---------------------------------------------------------------------------
# Public entry point — harness calls this
# ---------------------------------------------------------------------------

def run_tests() -> list[TestGroup]:
    groups = []

    g1 = TestGroup(name="Veritabanı işlemleri")
    _test_db_operations(g1)
    groups.append(g1)

    g2 = TestGroup(name="Hata yönetimi")
    _test_error_handling(g2)
    groups.append(g2)

    g3 = TestGroup(name="Argparse yapısı")
    _test_argparse_structure(g3)
    groups.append(g3)

    g4 = TestGroup(name="JSON çıktı formatı")
    _test_json_output(g4)
    groups.append(g4)

    return groups


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_db():
    """Return a path to a fresh temp SQLite file. Caller is responsible for
    cleanup if needed (we don't bother — temp files are cleaned by OS)."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)  # delete the empty file so init_db creates schema fresh
    return path


def _safe_import(g: TestGroup, test_id: str):
    """Import the student's tool module. Adds an errored TestResult on failure."""
    try:
        import tool  # noqa: F401
        return tool
    except Exception as e:
        g.add(TestResult(
            id=test_id,
            status="errored",
            detail=f"tool.py içe aktarılamadı: {e.__class__.__name__}: {e}",
            hint="solution.py değil, tool.py adında bir dosya olmalı; build_parser, add_task, list_tasks, complete_task fonksiyonları tanımlı mı kontrol et",
        ))
        return None


# ---------------------------------------------------------------------------
# Group 1 — Database CRUD operations
# ---------------------------------------------------------------------------

def _test_db_operations(g: TestGroup) -> None:
    tool = _safe_import(g, "test_db_add_returns_id")
    if tool is None:
        return

    # Test 1.1: add_task returns an integer id
    db = _fresh_db()
    try:
        new_id = tool.add_task("Pazartesi toplantısı", db)
        if isinstance(new_id, int) and new_id > 0:
            g.add(TestResult(id="test_db_add_returns_id", status="passed"))
        else:
            g.add(TestResult(
                id="test_db_add_returns_id",
                status="failed",
                input='add_task("Pazartesi toplantısı", db)',
                expected="positive integer (e.g. 1)",
                actual=repr(new_id),
                hint="add_task INSERT sonrası cursor.lastrowid'i döndürmeli",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_db_add_returns_id",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # Test 1.2: list_tasks returns the inserted task
    db = _fresh_db()
    try:
        tool.add_task("Pazartesi toplantısı", db)
        tool.add_task("Rapor yaz", db)
        tasks = tool.list_tasks(db)
        if len(tasks) == 2 and tasks[0]["title"] == "Pazartesi toplantısı":
            g.add(TestResult(id="test_db_list_after_add", status="passed"))
        else:
            g.add(TestResult(
                id="test_db_list_after_add",
                status="failed",
                input='add 2 tasks then list_tasks(db)',
                expected="2 tasks, first one is 'Pazartesi toplantısı'",
                actual=repr([t.get("title") for t in tasks]),
                hint="list_tasks ORDER BY id ASC ile sıralama yapmalı",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_db_list_after_add",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # Test 1.3: complete_task marks task as done
    db = _fresh_db()
    try:
        new_id = tool.add_task("Test görev", db)
        ok = tool.complete_task(new_id, db)
        tasks = tool.list_tasks(db)
        is_done = tasks[0].get("done")
        if ok is True and is_done is True:
            g.add(TestResult(id="test_db_complete_marks_done", status="passed"))
        else:
            g.add(TestResult(
                id="test_db_complete_marks_done",
                status="failed",
                input=f'complete_task({new_id}, db) then list',
                expected="complete returns True, task done=True",
                actual=f"complete returned {ok}, done={is_done}",
                hint="complete_task UPDATE çalıştırmalı, sonra list_tasks done=True göstermeli",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_db_complete_marks_done",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))


# ---------------------------------------------------------------------------
# Group 2 — Error handling
# ---------------------------------------------------------------------------

def _test_error_handling(g: TestGroup) -> None:
    tool = _safe_import(g, "test_error_empty_title")
    if tool is None:
        return

    # Test 2.1: Empty title raises ValueError
    db = _fresh_db()
    try:
        tool.add_task("", db)
        g.add(TestResult(
            id="test_error_empty_title",
            status="failed",
            input='add_task("", db)',
            expected="ValueError",
            actual="No exception raised",
            hint="Boş başlık ValueError fırlatmalı (titlesi olmayan görev anlamsız)",
        ))
    except ValueError:
        g.add(TestResult(id="test_error_empty_title", status="passed"))
    except Exception as e:
        g.add(TestResult(
            id="test_error_empty_title",
            status="failed",
            input='add_task("", db)',
            expected="ValueError",
            actual=f"{e.__class__.__name__}: {e}",
            hint="Boş başlık için spesifik olarak ValueError kullan, generic Exception değil",
        ))

    # Test 2.2: Whitespace-only title also rejected
    db = _fresh_db()
    try:
        tool.add_task("   ", db)
        g.add(TestResult(
            id="test_error_whitespace_title",
            status="failed",
            input='add_task("   ", db)',
            expected="ValueError",
            actual="No exception raised",
            hint="Sadece boşluktan oluşan başlık da geçersiz; .strip() kontrolü ekle",
        ))
    except ValueError:
        g.add(TestResult(id="test_error_whitespace_title", status="passed"))
    except Exception as e:
        g.add(TestResult(
            id="test_error_whitespace_title",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # Test 2.3: complete_task on missing id returns False (no exception)
    db = _fresh_db()
    try:
        tool.init_db(db)  # ensure schema exists but table is empty
        result = tool.complete_task(9999, db)
        if result is False:
            g.add(TestResult(id="test_error_missing_id_returns_false", status="passed"))
        else:
            g.add(TestResult(
                id="test_error_missing_id_returns_false",
                status="failed",
                input='complete_task(9999, db)  # nonexistent',
                expected="False",
                actual=repr(result),
                hint="Var olmayan id için exception atma, False döndür (cursor.rowcount kontrolü)",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_error_missing_id_returns_false",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))


# ---------------------------------------------------------------------------
# Group 3 — Argparse structure
# ---------------------------------------------------------------------------

def _test_argparse_structure(g: TestGroup) -> None:
    tool = _safe_import(g, "test_parser_has_add_flag")
    if tool is None:
        return

    # Test 3.1: build_parser returns ArgumentParser with --add
    try:
        import argparse
        parser = tool.build_parser()
        if not isinstance(parser, argparse.ArgumentParser):
            g.add(TestResult(
                id="test_parser_has_add_flag",
                status="failed",
                input='build_parser()',
                expected="argparse.ArgumentParser instance",
                actual=type(parser).__name__,
                hint="build_parser() argparse.ArgumentParser nesnesi döndürmeli",
            ))
            return

        # parse a known-good --add invocation
        args = parser.parse_args(["--add", "Test"])
        if getattr(args, "add", None) == "Test":
            g.add(TestResult(id="test_parser_has_add_flag", status="passed"))
        else:
            g.add(TestResult(
                id="test_parser_has_add_flag",
                status="failed",
                input='parser.parse_args(["--add", "Test"])',
                expected='args.add == "Test"',
                actual=f"args.add = {getattr(args, 'add', '<missing>')!r}",
                hint="--add bayrağı argparse'a eklenmemiş veya farklı isimle eklenmiş",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_parser_has_add_flag",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # Test 3.2: --list flag works
    try:
        parser = tool.build_parser()
        args = parser.parse_args(["--list"])
        if getattr(args, "list", False) is True:
            g.add(TestResult(id="test_parser_has_list_flag", status="passed"))
        else:
            g.add(TestResult(
                id="test_parser_has_list_flag",
                status="failed",
                input='parser.parse_args(["--list"])',
                expected="args.list == True",
                actual=f"args.list = {getattr(args, 'list', '<missing>')!r}",
                hint="--list için action='store_true' kullan",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_parser_has_list_flag",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # Test 3.3: --complete requires int (rejects non-numeric)
    try:
        parser = tool.build_parser()
        # parse_args calls sys.exit(2) on parser error; we capture by catching SystemExit
        try:
            parser.parse_args(["--complete", "abc"])
            g.add(TestResult(
                id="test_parser_complete_rejects_non_int",
                status="failed",
                input='parser.parse_args(["--complete", "abc"])',
                expected="SystemExit (argparse rejects non-int)",
                actual="No exception raised",
                hint="--complete bayrağına type=int parametresi ekle",
            ))
        except SystemExit:
            g.add(TestResult(id="test_parser_complete_rejects_non_int", status="passed"))
    except Exception as e:
        g.add(TestResult(
            id="test_parser_complete_rejects_non_int",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))


# ---------------------------------------------------------------------------
# Group 4 — JSON output format
# ---------------------------------------------------------------------------

def _test_json_output(g: TestGroup) -> None:
    tool = _safe_import(g, "test_list_returns_dicts")
    if tool is None:
        return

    # Test 4.1: list_tasks returns list of dicts
    db = _fresh_db()
    try:
        tool.add_task("Görev 1", db)
        tasks = tool.list_tasks(db)
        if isinstance(tasks, list) and all(isinstance(t, dict) for t in tasks):
            g.add(TestResult(id="test_list_returns_dicts", status="passed"))
        else:
            g.add(TestResult(
                id="test_list_returns_dicts",
                status="failed",
                input='list_tasks(db)',
                expected="list[dict]",
                actual=f"{type(tasks).__name__} containing {[type(t).__name__ for t in tasks][:3]}",
                hint="sqlite3.Row nesnelerini dict'e çevir (tuple veya Row değil dict döndür)",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_list_returns_dicts",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # Test 4.2: each task has the required keys
    db = _fresh_db()
    try:
        tool.add_task("Şablon görev", db)
        tasks = tool.list_tasks(db)
        required_keys = {"id", "title", "done"}
        first = tasks[0] if tasks else {}
        present = set(first.keys()) if isinstance(first, dict) else set()
        if required_keys.issubset(present):
            g.add(TestResult(id="test_list_has_required_keys", status="passed"))
        else:
            missing = required_keys - present
            g.add(TestResult(
                id="test_list_has_required_keys",
                status="failed",
                input='list_tasks(db)[0].keys()',
                expected=f"contains {sorted(required_keys)}",
                actual=f"has {sorted(present)} (missing: {sorted(missing)})",
                hint="Her dict için id, title, done anahtarları zorunlu",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_list_has_required_keys",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # Test 4.3: 'done' field is a bool, not int 0/1
    db = _fresh_db()
    try:
        tool.add_task("Bool testi", db)
        tasks = tool.list_tasks(db)
        done_value = tasks[0].get("done") if tasks else None
        if isinstance(done_value, bool):
            g.add(TestResult(id="test_list_done_is_bool", status="passed"))
        else:
            g.add(TestResult(
                id="test_list_done_is_bool",
                status="failed",
                input='list_tasks(db)[0]["done"]',
                expected="bool (True or False)",
                actual=f"{type(done_value).__name__}: {done_value!r}",
                hint="SQLite 0/1 olarak saklar — list_tasks sonucunda bool(row['done']) ile dönüştür",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_list_done_is_bool",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))
