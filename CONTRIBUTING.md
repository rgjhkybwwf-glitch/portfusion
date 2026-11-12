# Contributing to PortFusion

How a change to PortFusion is worked, for a collaborator or a Claude session arriving cold;
[`README.md`](README.md) says what PortFusion is.

## Setting up

```bash
git config core.hooksPath .githooks       # the gate that keeps credentials out of git
python3 -m venv .venv && .venv/bin/python3 -m pip install -e '.[dev]' -c requirements.lock
source .venv/bin/activate                 # once per terminal
export PORTFUSION_BOOK=demo               # once per terminal: a checkout holds no book
python3 -m pytest                         # the guard, on the demo
python3 tools/clean_room.py               # the app on its own: a copy, a new book and a wheel
```

[`docs/testing.md`](docs/testing.md) says what each layer of the guard proves, and what to do when
a test fails.

Everyone taking part follows the [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## The stability rules

A stability rule protects something a user would lose if it broke: their book's data or evidence,
their secrets, a figure they read or have published, their book opening on the next release, or
who may read it. It is held by a test or hook shown to fail when the rule is broken, and stated
once, here, beside that test.

### Your book's data

| # | Rule | Held by |
|---|---|---|
| 1 | **Tests never touch your book.** A test run never moves the book's `store/`, `_archive/` or `_inbox/`; every test writes to a copy. | `harness.py::pytest_sessionfinish` |
| 2 | **Every write is a named door.** Every write to the store or a history is a declared door, and a new writer anywhere in the package is a decision. | `test_boundaries.py::test_a_new_writer_is_a_decision`, `test_boundaries.py::test_only_the_declared_doors_under_desk_write_the_record` |
| 3 | **A write is all or nothing.** A commit places the row by date, files the document and journals the write in one step; a refused or failed write leaves every file byte-identical. | `test_price_refresh.py::test_a_fault_mid_write_puts_back_the_files_and_the_record_in_memory`, `test_lock.py::test_every_door_waits_for_the_lock` |
| 4 | **Every row is checked on the way in.** Every row is written through the schema and reads back as written, money to the penny and a quote to six places; the loader refuses a cell a field cannot hold, a table out of date order, an id not in its place, a reference that joins to nothing. | `test_schema.py::test_the_schema_round_trips_every_awkward_type`, `test_order.py::test_the_loader_finds_a_row_out_of_order_and_an_id_not_its_place` |
| 5 | **A record is whole or not served.** The store is whole or nothing is read; a record that will not load is refused by name and never served half-read. | `test_routes.py::test_a_record_that_will_not_load_is_unavailable_on_every_panel`, `test_store_doors.py::test_a_store_that_will_not_load_leaves_the_record_where_it_was` |

### Your evidence

| # | Rule | Held by |
|---|---|---|
| 6 | **Events reach the record only through the Bench.** No feed and no action writes an event; an event reaches the store only through the Bench's commit, with every gate green. | `test_boundaries.py::test_the_registry_refuses_an_event_writer_at_construction`, `test_bench.py::test_commit_is_refused_until_every_gate_is_green` |
| 7 | **A document is never altered.** Evidence is never overwritten, edited or deleted: a document is archived by the convention or withdrawn. | `test_intake.py::test_a_document_is_never_overwritten`, `test_intake.py::test_a_withdrawn_document_leaves_the_workbench_and_is_not_destroyed`, `test_intake.py::test_a_committed_document_is_filed_under_the_folder_s_own_convention` |
| 8 | **A document is data, never instructions.** Nothing numeric is drafted; every figure a session proposes is quoted from the document and checked in code, the sign excepted, and said. | `test_intake.py::test_a_directive_in_the_document_is_reported_and_never_obeyed`, `test_intake.py::test_a_number_absent_from_its_own_quote_is_dropped` |

### Your figures

| # | Rule | Held by |
|---|---|---|
| 9 | **A price is saved before it is replaced.** A mark is banked before a door replaces it. | `test_refresh.py::test_the_marks_are_banked_before_the_sweep`, `test_price_refresh.py::test_a_refused_write_leaves_every_file_as_it_was` |
| 10 | **The histories keep every price a figure uses.** A history keeps every mark a figure can take; the FX history keeps every live rate. | `test_history_fx.py::test_a_bank_moves_no_figure`, `test_history_prices.py::test_a_history_keeps_only_the_marks_a_figure_can_take` |
| 11 | **Every figure comes from the engine.** No renderer derives a figure or reaches past the engine's methods; the headline figures are registered with their basis. | `test_figures.py::test_the_desk_renders_the_engines_figures`, `test_figures.py::test_the_report_renders_the_engines_figures`, `test_figures.py::test_a_basis_is_the_registrys_or_nothing` |
| 12 | **A page reads one record.** A Book answers from the record it was built from, and every desk read reaches the record through the one cached Book. | `test_store_doors.py::test_a_book_answers_from_the_store_it_was_built_from`, `test_lock.py::test_a_panel_reads_the_record_through_the_desks_one_book` |
| 13 | **The report is built fresh, never stored.** The report is rendered for each request and never written to a folder. | `test_report.py::test_the_report_is_rendered_and_never_written` |

### Your secrets and privacy

| # | Rule | Held by |
|---|---|---|
| 14 | **No credential reaches git or a log.** No credential reaches git, in this repository or any book, and none is logged or printed. | `.githooks/pre-commit` and `commit-msg`, `test_hooks.py::test_a_planted_value_is_refused_by_NAME_and_never_quoted`, `test_hooks.py::test_history_finds_what_no_verify_let_through`, `test_tv.py::test_the_token_travels_in_a_header_and_is_never_printed_or_logged`, GitHub's push protection |
| 15 | **Nothing of your book leaves the checkout.** Nothing of a book is named in what leaves the checkout. | `test_what_leaves.py::test_what_leaves_names_nothing_of_the_loaded_book`, run by `.githooks/pre-push` on the book `PORTFUSION_BOOK` names, and a push that names none refused (`test_hooks.py::test_with_no_book_named_the_push_is_refused_and_says_how_to_name_one`); CI runs on the demo and cannot |

### Who may read and reach

| # | Rule | Held by |
|---|---|---|
| 16 | **The desk answers only this Mac and signed-in readers.** The local desk listens on 127.0.0.1 only; the hosted door fails shut without its secret, only reads, serves only its pinned routes, answers only a signed-in reader at their level, and withholds holders' names from a principal. | `test_routes.py::test_a_request_for_another_host_is_refused`, `test_remote.py::test_with_no_secret_on_the_mac_the_door_fails_shut`, `test_remote.py::test_every_remote_route_only_reads`, `test_remote.py::test_the_remote_door_serves_only_the_pinned_routes`, `test_remote.py::test_each_level_opens_what_was_agreed`, `test_remote.py::test_a_principal_reads_no_holder_and_no_number_anywhere` |
| 17 | **The feeds only read.** A feed makes only allowlisted reads, refused by name before a request is built; a feed writes no mark and no event. | `test_ig.py::test_guard_refuses_everything_that_is_not_a_read`, `test_tv.py::test_the_allowlist_is_checked_before_a_request_is_built`, `test_tv.py::test_a_feed_writes_nothing_but_its_own_sign_in` |

### Upgrades and releases

| # | Rule | Held by |
|---|---|---|
| 18 | **Your book opens on the next release.** The loader refuses an old shape by name; `portfusion migrate --write` makes the moves, and puts every file back if the book will not open or audit. | `test_migrations.py::test_a_book_in_the_old_shape_is_carried_to_this_release_and_can_be_put_back` |
| 19 | **A new book is complete and guarded.** `portfusion init` writes every table, the three histories, the release's hooks and ignore list, and the book names the release it runs. | `test_init.py::test_the_loaded_book_holds_what_init_writes_and_its_hooks_are_the_releases`, `test_init.py::test_a_new_book_names_the_portfusion_it_runs` |
| 20 | **History and releases never move.** `main` is never rewritten or deleted; a release tag never moves. | `test_hooks.py::test_a_force_push_that_rewrites_main_is_refused`, `test_hooks.py::test_deleting_main_is_refused_however_it_is_spelt`, GitHub's rulesets "main" and "release tags" |
| 21 | **The engine needs no desk, feed or history.** The build (engine, record, report) imports nothing from `desk/`, `feeds/` or `history/`. | `pyproject.toml::the-build`, an import contract run by `.github/workflows/guard.yml`, which plants an import it must refuse, and by `.githooks/pre-commit` |
| 22 | **The guard runs on any book.** The guard ships with the app and runs on any book; a test says which rows it needs; a book lists the skips it expects, and any other skip fails, as does a listed one that ran. | `tools/clean_room.py`, `harness.py::needs`, `harness.py::expected_skips`, `harness.py::skips_off` |

## The conventions

One line each; kept by review, and by the test named where there is one.

### Agreeing a change

- **A pull request is the proposal**: a small change is made on a branch and agreed in its pull
  request; a large one (a new table, a store move, a change of direction) is raised in an issue
  first. An approval covers exactly what it names.
- **A decision that appears mid-task is a stop**, and so is a test or guide that would bend one
  already agreed; a test that only needs its expectation moved to the agreed outcome is not.
- **Options carry their cost** (files, tests, figures that move), with a recommendation. A declined
  one is not raised again unless something material has changed, and then with what changed.
- **Search for what already does the job before adding anything**: a function takes a parameter
  rather than gaining a second version, and nothing gets a helper or a package for a single use (the
  upload is a raw body, not multipart; the icon is drawn with the standard library).
- **Docs, comments and tests to the minimum**: definitions and short tables.
- **A rule is stated once** and pointed at; one stated twice has drifted
  (`test_record.py::test_no_file_writes_out_a_rule_the_record_states_once`,
  `test_record.py::test_the_code_repeats_itself_no_more_than_it_did`).

### Where a change goes

| To add | Write it in | Held by |
|---|---|---|
| a table, or a value in a vocabulary | `record/schema.py` | `tests/record/test_schema.py` |
| a change the loader would refuse an older book for | its move in `record/migrations.py` | `tests/record/test_migrations.py` |
| a headline figure | a `Book` method and its entry in `Book.HEADLINE` | `tests/test_figures.py` |
| a column heading | `house/headings.py` | `tests/test_figures.py` |
| a desk panel | `desk/panels/<name>.py` | `tests/desk/test_panels.py` |
| a desk button | its `Action` in `desk/actions.py` | `tests/desk/test_boundaries.py` |
| a route on the hosted desk | `REMOTE_ROUTES` in `desk/remote.py` | `tests/desk/test_remote.py` |
| anything that writes a file, or opens a file of the store | its door, named in `WRITERS` or `STORE_FILE_DOORS` | `tests/desk/test_boundaries.py`, `tests/record/test_store_doors.py` |
| a kind of document | an `Evidence` in `record/rules_evidence.py` | `tests/record/test_evidence.py` |
| which part of the app may import which | an import contract in `pyproject.toml` | `lint-imports` |
| a feed endpoint | the allowlist in `feeds/ig.py` or `feeds/tv.py` | `tests/feeds/test_ig.py`, `tests/feeds/test_tv.py` — meant to stop you |

### The code

- **The linter, the import contracts and the type checker find nothing**: `python3 -m ruff check`,
  `lint-imports`, `pyright`.
- **No formatter**: the aligned columns are the style; the linter holds the rest.
- **A `noqa` names its reason**, and a blind `except Exception` is kept only with one (ruff's
  `RUF100` and `BLE001`).
- **A comment or docstring states the rule as it is**, not its history, and a function it names
  exists (`test_code.py::test_comments_state_the_rule_not_its_history`,
  `test_code.py::test_every_function_a_comment_names_exists`).
- **A comment types no figure the code can move**: no engine figure, no measured duration
  (`test_code.py::test_the_engines_comments_type_no_figure`).
- **Every line a command says goes through `portfusion.log`**
  (`test_code.py::test_nothing_outside_the_tests_prints`).
- **Hold a module, never its names, where they move**: `rules.X`, not `from … import X`, and the
  schema's `STORE` and `BOOK` likewise (`test_code.py::test_a_module_is_imported_one_way`).
- **A cached frame is returned as a copy.**
- **The engine keeps its numbered sections in order**, each topic in one place and its window stated
  once (`test_code.py::test_book_py_keeps_each_topic_in_one_place`,
  `test_code.py::test_the_engine_states_its_window_once`).
- **Every public engine method has a reader**
  (`test_code.py::test_every_public_engine_method_has_a_reader`).
- **A migration records nothing in the book**: a step applies where the old shape still stands.
- **The maintainer's tools sit beside the app**, in `tools/`, never in the package a book installs.

### Tests

- **A stability rule's test keeps on file the case that makes it fail**: a mutation, a sentinel or a
  negative case.
- **Extend a test before adding one.**
- **A test asks for `repo_root` only to read the checkout**, so the wheel's run keeps the rest
  (`test_code.py::test_a_test_asks_for_the_checkout_only_to_read_it`).
- **How to write a test, and what to do when one fails**, is [`docs/testing.md`](docs/testing.md)'s:
  by field, a relationship, the rows it needs, any book, a copy; read its docstring first; never
  weaken a check.
- **A count on file goes down, or up with its reason beside it** in the pull request's diff:
  `DESK_CHROME_WORDS`, `REPORT_PROSE_WORDS`, `REPEATED_PROSE_HIGH_WATER`.
- **Opening an allowlist is a visible diff**: each entry a name, never a count or a pattern.
- **A fake answers through the real allowlist.**
- **A run names the book it ran on**, and git runs unsigned in the suite (`harness.py::book_line`,
  `harness.py::unsigned_git`).
- **The demo is what `tools/make_demo.py` writes**
  (`test_demo.py::test_a_fresh_run_of_the_generator_writes_the_demo_exactly`).

### Commits and pull requests

- **One logical change per commit**, its message written for a reader who was not there.
- **Review the branch's diff before its pull request opens**, and settle what the review finds.
- **A changed desk page is walked cold before its pull request opens**: a reader with the desk's
  address and the issue's jobs, and no code or guides, as [`docs/ux-audit.md`](docs/ux-audit.md)
  was made. The pull request says which of its rows the walk found closed.
- **A release's guides are read whole before its tag**, one reader to a guide, each running its
  commands and opening its paths; one writer makes the changes.
- **A change to the app is written up in [`CHANGELOG.md`](CHANGELOG.md)**, under Unreleased, a
  store move by name; a push that changes the app and not the changelog is refused
  (`test_hooks.py::test_a_checkouts_branch_that_changes_the_app_writes_it_up`).
- **Never bypass a hook.** A branch reaches `main` as a pull request. The maintainer's yes turns
  its auto-merge on, and GitHub merges it once CI's `guard` is green; it runs on every pull
  request and on `main`. A Dependabot bump within its major version merges the same way, unasked
  (`dependabot-merge.yml`), and so does the nightly agent's clean pull request, whose yes was
  given in advance by a ready issue (below).

### The nightly agent (on trial since 12 Nov 2026)

An unattended Claude session works the ready issues, and the maintainer checks in by morning.
This is a trial: the process is being developed as it runs, and each surprise becomes a rule here,
a test, or a better-written issue. **This section is the agent's instructions**; the agent never
changes it.

**How it runs**

- **From a routine on claude.ai** at 02:00 UK time, in the personal cloud environment
  "PortFusion", whose setup script builds the venv on Python 3.13 and installs `tools/`. The
  routine points here and sets how many issues a night; nothing else is kept there.
- **A run has a cap.** No more issues than the routine names, and no issue past a second attempt
  at a green guard: one that will not go green is left as a draft pull request with what blocks it
  at the top, and the run moves on. A run that is going nowhere stops and says so; it does not file
  issues to show work.

**Which issues, in what order**

- **An issue is ready when it meets the Definition of Ready and carries no `decision` label**, so
  it can be built unattended and merged unread: taking `decision` off is the maintainer's yes,
  given in advance, and no other label is needed. The Definition of Ready is all five:
  - **Cause**: what in the code makes the symptom, by file and function. A symptom alone is
    evidence, not an issue.
  - **Done**: the checks that say it is done, each one a test, a walk step or a command can make.
  - **Not in scope**: what the fix leaves alone.
  - **Decisions**: every question answered by the maintainer, quoted with the date. An answer in
    a comment counts; the agent copies it into this section before it starts.
  - **Order**: what it waits on, and what waits on it.
  An issue without them is labelled `decision`, with its questions at the end, or is evidence for
  one that has them.
- **The Queue sets the order**: the open issue "Queue: what the nightly agent builds next" (#206)
  ranks the work, unblockers first, then bugs and wrong figures, small safe fixes, features and
  polish. The agent takes the first line under Next whose issue is ready and has no open pull
  request of its own, and whose "waits" issues are all closed; it skips the rest and never
  reorders. Each issue is read whole, comments included, before its work starts.
- **The agent keeps the Queue current**: after each pull request merges it ticks the line and moves
  it to Done, and each issue it files goes under To rank, for the maintainer to place.
- **Its own open pull requests come first.** Before a new issue, each one is brought level with
  `main` (merged in, never rebased), its pictures retaken when a page it changed moved under it,
  and its CI made green, so none waits on the maintainer for anything but a yes it asked for.
- **No ready line in the Queue and nothing to tend: stop**, posting nothing.

**Asking and answering**

- **Every question for the maintainer is asked at the end, under "Questions for you"**: of an
  issue, and of a comment that stops one. A question is one line, written to be answered on a
  phone: `**Q1** the question? **a** an option (recommended) · **b** another`, with what it
  costs in a few words. Tables above it are evidence, read only when wanted, and carry no column
  to fill in.
- **The maintainer answers in one comment, a line a question**: `Q1: a`, `Q2: b, and …`, or
  `All as recommended`. A question is settled when its answer is written so; a recommendation is
  not an answer, and neither is a comment's tone.
- **An issue's questions are kept few**: what only the maintainer can decide. What the agent can
  settle from the code, the record's rules or an answer already given, it settles and says so.

**Building**

- **A plan, checked, before code.** The agent writes its plan as a comment on the issue: the files
  it will change, how each "Done" check will be made, and what it will not touch. A fresh agent,
  given only the issue and that plan, checks the plan against the code and says what is missing or
  wrong; the plan is mended before a line is written. A plan that finds the issue's cause is wrong
  is a stop, asked as a decision.
- **One issue, one branch, one pull request**: a branch claude/<name> from the latest `main`,
  worked by the conventions above (changelog, own diff reviewed, a changed desk page walked cold),
  the guard run, and the desk walk if a desk file changed. The pull request says "Closes #n", and
  the agent goes on to the next issue without waiting for a merge.
- **Settled rows are built; open rows are asked.** When some of an issue's rows are open, the
  settled ones are built in a pull request that says "Part of #n", auto-merge off; the open ones
  are asked in one comment on the issue, options and a recommendation each, and the issue is
  labelled `decision`. The maintainer answers and takes the label off.
- **A decision that appears mid-build is a stop** for that row, asked the same way.
- **Something a comment raises outside its issue** becomes a new issue labelled `decision`,
  linked from the issue, and is not built.
- **What a cold walk finds that the change did not cause** is filed as an issue, or added to one,
  and listed in the pull request.
- **A milestone being worked only gets shorter.** An issue the agent files goes in the next
  milestone, with the area labels of the issue it came from and `decision` until it is answered,
  unless an issue of the current one cannot close without it. A walk's finds are one issue a walk.
- **A CI failure on its pull request** is the agent's to fix, and it waits for the guard's result
  before it leaves a pull request. When the walk fails only because a page the issue meant to
  change looks different, the agent labels the pull request `baselines`: a workflow retakes the
  walk's Linux pictures onto a branch beside it, `baselines/<branch>` (`baselines.yml`); the agent
  merges that in and pushes, which runs the guard, and the pull request lists the pages whose
  pictures changed. The pictures are the agent's to keep; the
  maintainer never takes or reads them, and they are compared on Linux alone. A failure the agent
  cannot fix is said at the top of the pull request, with what would fix it.

**Merging**

- **A reviewer who did not build it.** Before a pull request is called clean, a fresh agent given
  only the issue's "Done" checks and the diff reviews it, as a skeptic: does each check hold, did
  a test's expectation move without the issue saying so, did anything outside the issue change. Its
  findings are fixed, or said at the top of the pull request.
- **A clean pull request merges itself**: one that asks the maintainer nothing, made no choice
  its issue did not, passes the guard, the walk and the reviewer, and has its cold walk's finds
  filed. The agent
  turns its auto-merge on as it opens it, and GitHub merges it once `guard` is green. Pictures
  retaken for a page the issue meant to change keep it clean.
- **Any other waits for the maintainer's yes**, auto-merge off, with what is needed from them at
  the top of its description.

**Telling the maintainer**

- **A question or pull request reaches the maintainer as a mention**: the agent works as the
  maintainer's account, so GitHub would tell them nothing; an issue labelled `decision`, and a pull
  request from a branch whose name begins claude/, get a comment from `github-actions[bot]`, headed
  "PortFusion agent", that names them and says whether the pull request is merging itself or
  waiting for a yes (`notify.yml`).

**Never**

- **The agent never pushes to `main`, bypasses a hook, or changes** a workflow, a ruleset, a test
  that holds a stability rule, or this section; those are changed in a session the maintainer is
  part of.

### The desk and the report

- **Check a change on the demo**: `portfusion desk --book demo --port 8769`, never on a desk a book
  is using.
- **The renderers move together**: what changes on the desk changes on the report.
- **The desk and the report carry as little prose as they can.**
- **Every size on the desk is a step of the type scale** in `desk/static/app.css`.
- **A panel is one file with one name**, and its tab runs in the order of the work
  (`desk/panels/__init__.py`; `test_panels.py::test_a_panel_has_one_name`,
  `test_panels.py::test_the_tabs_run_in_the_order_of_the_work`).

### A book stays out

- **Examples are invented.** Use the demo's names, never a real book's people, holdings, references,
  figures or dates: in code, guides, commits, branches, issues or pull requests.
