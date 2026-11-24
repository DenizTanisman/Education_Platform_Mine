# IAU AI Platform — Content Delivery Contract

> This document defines the format Deniz follows when delivering unit content
> to the platform. Claude Code processes ZIPs in this format automatically.
>
> **Core principle:** Deniz only drops ZIPs into the `content/inbox/` directory.
> He touches nothing else. Claude Code never writes into `content/inbox/`.

---

## 1. GENERAL SCHEMA

Each unit is delivered as a single ZIP:

```
content/inbox/unit-07-rag-pipeline.zip
```

The file name must match this format:
- Prefix: `unit-`
- Sequence number: `00`, `01`, `02`, ... (two digits)
- Slug: kebab-case, English, alphanumeric + hyphen
- Extension: `.zip`

**Regex:** `^unit-\d{2}-[a-z0-9-]+\.zip$`

**Valid examples:**
- `unit-00-welcome.zip`
- `unit-01-python-basics.zip`
- `unit-07-rag-pipeline.zip`

**Invalid examples:**
- `unit-7-rag.zip` (single digit)
- `unit-01-RAG Pipeline.zip` (space, uppercase)
- `ünite-01.zip` (non-ASCII)

---

## 2. DIRECTORY STRUCTURE INSIDE THE ZIP (required)

```
unit-07-rag-pipeline.zip
├── unit.yaml                    # REQUIRED — unit metadata
├── education.pdf                # REQUIRED — lecture notes
├── projects.md                  # REQUIRED — project instructions (markdown)
├── tests/
│   └── test_runner.py           # REQUIRED — harness-compatible test file
├── reference/
│   └── pass_final.zip           # REQUIRED — passing reference solution
└── videos.yaml                  # OPTIONAL — YouTube video list
```

### 2.1. unit.yaml (required)

```yaml
order: 7                         # integer, sequence
slug: rag-pipeline               # must match the one in the file name
title: RAG Pipeline              # human-readable title
description: |                   # short description (max 500 chars)
  Retrieval Augmented Generation temelleri. Document loader, embeddings,
  vector search ve cevap sentezi.
tags: [rag, embeddings, vector-search]   # optional
duration_minutes: 180            # estimated learning time
published: true                  # if false, ingest writes to the DB but it is hidden in the UI
test_groups:
  - name: Document loader
    weight: 1
    order: 1
  - name: Vector search
    weight: 2
    order: 2
  - name: End-to-end pipeline
    weight: 3
    order: 3
```

### 2.2. education.pdf (required)

- Format: PDF (A4 or Letter)
- Max size: 20 MB
- Content: lecture notes, diagrams, examples

### 2.3. projects.md (required)

- Format: GitHub Flavored Markdown
- Rendered with `react-markdown`
- Content: practical tasks the student must do **locally**
- Make the file structure they will put in the ZIP explicit here
- Max 500 lines

Suggested structure (the sample is in Turkish, like the course content):

```markdown
# Unit 7 — RAG Pipeline

## Amaç
<feynman yaklaşımıyla genel resim>

## Ön hazırlık
- Python 3.11
- requirements.txt: ...

## Görevler

### Görev 1 — Document Loader
<açıklama>

**Beklenen fonksiyon imzası:**
```python
def load_document(path: str) -> list[Chunk]: ...
```

### Görev 2 — Vector Search
...

## Teslim formatı
Aşağıdaki dosya yapısıyla bir ZIP oluşturun:

```
submission.zip
├── loader.py
├── search.py
└── pipeline.py
```
```

### 2.4. tests/test_runner.py (required)

The harness imports this file. It follows this contract:

```python
# content/inbox/.../tests/test_runner.py

from harness_api import TestResult, TestGroup, register

# /workspace/code is added to sys.path to import the student code
# (harness.py does this automatically)
import sys
sys.path.insert(0, '/workspace/code')


def run_tests() -> list[TestGroup]:
    """
    The harness calls this function. Each TestGroup must match one of the
    test_groups in unit.yaml via the 'name' field.
    """
    groups = []

    # ---- Group 1: Document loader ----
    g1 = TestGroup(name="Document loader")

    try:
        from loader import load_document
        chunks = load_document("fixtures/sample.pdf")
        if len(chunks) == 5:
            g1.add(TestResult(
                id="test_load_basic",
                status="passed",
                runtime_ms=12,
            ))
        else:
            g1.add(TestResult(
                id="test_load_basic",
                status="failed",
                expected="len(chunks) == 5",
                actual=f"len(chunks) == {len(chunks)}",
                input='load_document("fixtures/sample.pdf")',
                hint="PDF'deki her sayfa bir chunk olmalı",
            ))
    except Exception as e:
        g1.add(TestResult(
            id="test_load_basic",
            status="errored",
            detail=str(e),
        ))

    groups.append(g1)

    # ---- Group 2: Vector search ----
    # ...

    return groups
```

**Rules:**
- Each TestResult's `id` is unique, snake_case, prefixed with `test_`
- `status` ∈ `{passed, failed, errored, timeout}`
- If `failed`, `expected` + `actual` are required, `input` + `hint` optional
- If `errored`, `detail` is required (the exception message, not a stack trace)
- `hint` is shown to the student; keep it clear and short
- Each test must finish within 2 seconds (harness timeout)

### 2.5. reference/pass_final.zip (required)

This ZIP is the reference version of the solution **the student will upload**.

**Purposes:**
- Automatically tested during ingest → does `pass_final.zip` actually pass
- Can be shown as the "reference solution" in the admin UI (optional)
- Used by Deniz when testing locally

**Schema:**
```
pass_final.zip
└── <file structure specified in projects.md>
```

Example:
```
pass_final.zip
├── loader.py
├── search.py
└── pipeline.py
```

**Rule:** The ingest script automatically submits this ZIP to the sandbox.
If not all tests return PASS, **ingest fails** and the unit is not written to the DB.

### 2.6. videos.yaml (optional)

```yaml
videos:
  - title: "RAG nedir, neden var?"
    youtube_id: "dQw4w9WgXcQ"
    duration_seconds: 720
    order: 1
  - title: "Embedding modelleri"
    youtube_id: "9bZkp7q19f0"
    duration_seconds: 900
    order: 2
```

---

## 3. HARNESS JSON OUTPUT SCHEMA (reference)

`test_runner.py` → `harness.py` → stdout:

```json
{
  "summary": {
    "total": 12,
    "passed": 10,
    "failed": 2,
    "errored": 0,
    "timeout": 0,
    "runtime_ms": 4823,
    "verdict": "failed"
  },
  "groups": [
    {
      "name": "Document loader",
      "weight": 1,
      "passed": 3,
      "total": 3,
      "tests": [
        {
          "id": "test_load_basic",
          "status": "passed",
          "runtime_ms": 12
        }
      ]
    },
    {
      "name": "Vector search",
      "weight": 2,
      "passed": 2,
      "total": 4,
      "tests": [
        {
          "id": "test_top_k_retrieval",
          "status": "failed",
          "expected": "first result id == \"doc_7\"",
          "actual": "first result id == \"doc_12\"",
          "input": "retrieve(\"Istanbul\", k=3)",
          "hint": "Cosine similarity normalizasyonu doğru mu",
          "runtime_ms": 22
        }
      ]
    }
  ]
}
```

`verdict`:
- `"passed"` → all tests passed
- `"failed"` → at least one test failed/errored/timed out

---

## 4. DENIZ'S PREPARATION WORKFLOW

Order to follow for each unit:

1. **Open a working directory** (`~/scratch/unit-XX-slug/`)
2. Write **unit.yaml**
3. Prepare **education.pdf** (or convert from existing material)
4. Write **projects.md** — the task list that guides the student
5. **Write the reference solution** (`.py` files in the `reference/pass_final/` folder)
6. Write **tests/test_runner.py** — the reference solution must pass these tests
7. **Local test:**
   ```bash
   cd ~/scratch/unit-XX-slug
   cd reference && zip -r ../reference/pass_final.zip .
   cd ..
   # Run the local harness
   python /path/to/platform/scripts/test-unit-locally.py .
   # → you should see "all tests passed: 12/12"
   ```
8. **Package the ZIP:**
   ```bash
   cd ~/scratch
   zip -r unit-XX-slug.zip unit-XX-slug/
   ```
9. **Drop it at the door:**
   ```bash
   cp unit-XX-slug.zip /path/to/platform/content/inbox/
   ```
10. **Trigger ingest:**
    ```bash
    make ingest
    ```
11. **Verify:**
    - Terminal output shows "unit-XX ingested"
    - `npx prisma studio` → new row in the Unit table
    - In the UI, `http://localhost/dashboard` → the unit is visible
    - Reference solution is tested automatically → all tests PASS

12. **On error:**
    - Error details in `content/inbox/errors/unit-XX-slug.log`
    - The ZIP stays in `content/inbox/` and can be retried
    - Fix → drop again → `make ingest`

---

## 5. WHAT HAPPENS AFTER DELIVERY (Claude Code's job)

The ingest script follows these steps:

1. `content/inbox/unit-XX-slug.zip` is detected
2. Schema validation (the rules in this document)
3. Extracted to a temporary directory (`/tmp/ingest-<uuid>/`)
4. `unit.yaml` is parsed
5. `reference/pass_final.zip` is automatically submitted to the sandbox
6. If not all tests PASS → ERROR, log to the `content/inbox/errors/` folder
7. If PASS:
   - Placed into the `content/units/unit-XX-slug/` folder
   - `education.pdf` → `app/public/pdfs/unit-XX-slug.pdf`
   - DB upsert: Unit, Video, Project, TestGroup, TestCase
   - ZIP is moved to the `content/inbox/processed/` folder
8. A success message is written to the terminal

---

## 6. UPDATE SCENARIO

If Deniz wants to fix a unit:

1. Prepare a new ZIP (same slug, same order)
2. Drop it into `content/inbox/`
3. `make ingest`
4. Script: if order + slug match, it performs an **upsert**
5. Setting `published: false` hides it from the UI but keeps the data
6. To delete it completely, delete manually from the admin UI (v2)

**Important:** The same slug with a different order is forbidden. In that case the
script errors out and keeps the old value.

---

## 7. PROHIBITED

- ❌ Dropping loose files like `.py` or `.md` into `content/inbox/` (everything is a ZIP)
- ❌ Symbolic links inside the ZIP
- ❌ `.exe`, `.sh`, `.bat` files inside the ZIP
- ❌ `__MACOSX/`, `.DS_Store` (tolerated, but with a warning)
- ❌ Any `.py` file under `tests/` other than `test_runner.py` (harness import conflict)
- ❌ Personal information (name, email, phone) in unit.yaml or projects.md
- ❌ Hardcoded paths in test cases (`C:\Users\...`)

---

## 8. MINI REFERENCE — SAMPLE ZIP CONTENTS

A minimal working example:

```
unit-00-welcome.zip
├── unit.yaml
├── education.pdf
├── projects.md
├── tests/
│   └── test_runner.py
└── reference/
    └── pass_final.zip
```

`unit.yaml`:
```yaml
order: 0
slug: welcome
title: Welcome to IAU AI
description: "Platform tanıtımı ve ilk Python kodu."
published: true
test_groups:
  - name: Hello world
    weight: 1
    order: 1
```

`tests/test_runner.py`:
```python
from harness_api import TestResult, TestGroup
import sys
sys.path.insert(0, '/workspace/code')

def run_tests():
    g = TestGroup(name="Hello world")
    try:
        from solution import greet
        result = greet("Deniz")
        if result == "Hello, Deniz!":
            g.add(TestResult(id="test_greet_basic", status="passed"))
        else:
            g.add(TestResult(
                id="test_greet_basic",
                status="failed",
                expected='"Hello, Deniz!"',
                actual=repr(result),
                input='greet("Deniz")',
            ))
    except Exception as e:
        g.add(TestResult(id="test_greet_basic", status="errored", detail=str(e)))
    return [g]
```

Contents of `reference/pass_final.zip`:
```
pass_final.zip
└── solution.py
```

`solution.py`:
```python
def greet(name: str) -> str:
    return f"Hello, {name}!"
```

This example works: `make ingest` → Unit-0 lands in the DB, users can
access it, the student writes `solution.py` → drops a ZIP → gets a PASS.
