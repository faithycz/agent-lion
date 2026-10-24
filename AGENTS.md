# AGENTS.md - Context & Instructions for agent-lion web crawler

This file contains context, guidelines, directory structures, constraints, rules and operational workflow for the agent-lion web crawler. Follow these instructions strictly. Write clean and efficient code following best practices.

---

## 1. Project Overview & Architecture
* **Project Name:** agent-lion
* **Language & Runtime:** Python 3.12++
* **Package Manager:** `uv`
* **Source Layout:** All core project source code resides under the root `/src` directory

### Module Architecture
* Do **not** dump all logic into a single file. Organize code into logical modules and packages, avoiding monolithic files.
* Group domain logic into cohesive, logical Python modules inside `/src` (e.g., `src/crawler/core/`, `src/crawler/utils/`).
* Always include proper `__init__.py` files when creating new module packages to ensure correct initialization and explicit public exports
* Create comprehensive unit tests and ensure high level of code coverage

---

## 2. Coding Standards & Style Preferences
* Use latest version of libraries and idiomatic Python 3.12+ features (e.g., `match/case`, `dataclasses`, `asyncio`, `typing`).
* Keep it simple and readable. Avoid unnecessary complexity. Favor clarity over cleverness. No unnecessary defensive programming
* Be concise, keep README and docstrings minimum
* Avoid hard-coding values. Important: no emojis, no ASCII art, no banners, no comments that are not useful for understanding the code
* **Type Hinting:** Enforce strict PEP 484 type hinting on all function signatures, variables, and return values. Avoid using `Any` unless absolutely necessary
* **Formatting:** Adhere to PEP 8 standards. Code is formatted and linted via `ruff`
* **Async/Await:** Use asynchronous patterns (`asyncio`) for handling network operations, LLM API calls, or I/O bound tasks
* **Docstrings:** Document all modules, classes, and public functions using Google-style docstrings

---

## 3. Operational Workflows & Commands

You must use the `uv` toolchain for all dependency management, environments, and execution tasks. Do not call raw `pip` or `python` globally.

### Dependency Management
If a task requires a new package, add it using `uv`:
```bash
uv add <package_name>
uv add --dev <package_name> # For development dependencies
```

### Environment Execution
Always execute scripts, tools, and linters inside the managed environment:
```bash
uv run python -m src.agent_lion.main
```

### Verification & Testing
Before declaring any task complete, run the following validation suite to guarantee zero regressions:
```bash
# Code linting and formatting check
uv run ruff check .
uv run ruff format --check .

# Test execution (assumes pytest is configured)
uv run pytest
```

---

## 4. Requirements & Constraints
- Crawl only URLs that are on the **same domain** and **subdomain** as the seed URL
- Skip any URL that exceeds the seed's `max_depth`
- Use a randomized delay (1–3 seconds) between consecutive visits to URLs to mimic human browsing
- Set a **fake/randomized** `User-Agent` header for each crawl request
- Never bypass authentication walls, CAPTCHAs, or paywalls — skip and log instead
- Handle errors gracefully (timeouts, broken links, blocked requests, login walls)
- Convert and store extracted page content as Markdown files
- For each seed URL, log a summary of links visited and skipped at the end of crawling
- Include current crawl depth when logging visited and skipped URLs to the console

### 1. Technical Stack

| Component                  | Tool                                |
|----------------------------|-------------------------------------|
| Browser automation         | **Playwright (Chromium)**           |
| Concurrency                | **asyncio**                         |
| HTML → Markdown conversion | **markdownify**                     |
| Fake user agents           | **fake_useragent**                  |


### 2. Configuration File (`config.json`)

The crawler is driven entirely by a JSON configuration file.

```json
{
  "seeds": [
    {
      "url": "https://example.com",
      "max_depth": 3,
      "skip": false
    },
    {
      "url": "https://another-site.com",
      "max_depth": 1,
      "skip": true
    }
  ],
  "skip_urls": [
    "https://example.com/login",
    "https://example.com/logout",
    "https://example.com/account"
  ],
  "output_dir": "crawled",
  "delay_min_seconds": 1,
  "delay_max_seconds": 3,
  "concurrency": 3
}
```

**Config fields:**
- `seeds[].url` — starting URL for a crawl tree
- `seeds[].max_depth` — maximum link-following depth from that seed
- `seeds[].skip` — if `true`, bypass this seed entirely (no crawling, no logging of children)
- `skip_urls` — a **global** list of exact URLs (or patterns) to always skip, regardless of seed
- `output_dir` — root folder for saved Markdown files (default: `crawled/`)
- `delay_min_seconds` / `delay_max_seconds` — bounds for the randomized per-URL delay
- `concurrency` — number of parallel browser contexts/workers

### 3. Content Handling Rules
- [ ] **Seed URLs**: visited only to discover outbound links — their own content is **never downloaded or saved**
- [ ] **Non-seed URLs**: content is fetched, converted to Markdown, and saved under `crawled/`
- [ ] Skip and do **not** save any URL found in `skip_urls`
- [ ] Skip any URL not on the **same domain** and **subdomain** as its originating seed URL
- [ ] Skip any URL that exceeds the seed's `max_depth`
- [ ] Skip URLs that return HTTP errors (4xx, 5xx) — log the URL and status code to console
- [ ] Skip URLs that fail to load (timeout, network error) — log the URL and error to console
- [ ] Skip URLs that are blocked by robots.txt (if detected) — log the URL and reason to console
- [ ] Skip URLs that do not have the path **/sp** or **/kb** - log the URL and reason to console, do not save content
- [ ] Skip URLs that do not contain query parameter **sysparm_article** or **sys_kb_id** — log the URL and reason to console, do not save content
- [ ] Skip pages that require manual interaction (login forms, CAPTCHA, click-to-continue) — log the URL and reason to console, do not save content
- [ ] File naming: extract the value of query parameter **sysparm_article** or **sys_kb_id** and use it as the Markdown filename (e.g., `crawled/<sysparm_article>.md`)

### 4. Interaction-Required Detection
Before extracting content, check the page for interaction barriers:
- Presence of `input[type="password"]` fields
- URL path containing keywords: `login`, `signin`, `sign-in`, `signup`, `logout`, `account`
- Presence of CAPTCHA markers (`iframe[src*="recaptcha"]`, `.g-recaptcha`, `#captcha`)

If detected → log `SKIPPED (manual interaction required): <url>` to console and move on.

### 5. Human-Like Scrolling
To trigger lazy-loaded content, simulate scrolling via repeated **Page Down** key presses
- Implement scrolling inside the main body of a page
- Also implement scrolling inside inner overflow containers such as <section class="sp-scroll">
- Click into the page body or inner container to ensure focus
- Press `PageDown` key
- Wait a randomized short delay (e.g. 0.5–1.5s) between presses
- Repeat for N iterations or until page height stops increasing
- Cap total scroll attempts to avoid infinite loops on infinite-scroll pages

---

## 5. Architecture Checklist
- [ ] Load and validate `config.json`
- [ ] URL frontier/queue per seed, tracking current depth
- [ ] URL normalization (resolve relative links, strip fragments)
- [ ] Depth limiting per seed's `max_depth`
- [ ] Same-domain enforcement (compare `urlparse(url).netloc` to seed domain)
- [ ] Global skip-list enforcement
- [ ] Interaction-barrier detector (login/CAPTCHA skip + console log)
- [ ] Human-like scroll simulator
- [ ] Randomized 1–3s delay between visits per URL
- [ ] Fake User-Agent per request (via `fake_useragent`)
- [ ] Concurrency control (async semaphore / browser context pool)
- [ ] HTML → Markdown conversion
- [ ] Markdown file storage under `crawled/` (skip saving for seed URLs)
- [ ] Logging (visited, skipped, failed, saved)
- [ ] Graceful browser/context cleanup


---

## 6. Definition of Done (DoD))
A task is considered complete only when:
1. New functionality is modularized into appropriate Python files within `src/`.
2. All modified and new code passes `ruff` linting and formatting.
3. Every public function and class contains strict type hints and docstrings.
4. All unit tests pass successfully via `uv run pytest`.