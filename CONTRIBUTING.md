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
  commands and opening its paths; one writer makes the changes. The read starts from the guides
  the pre-push hook names as left behind since the last tag (`behind()` in
  `src/portfusion/hooks/pre_push.py`, its base the tag), and its pull request ticks, for `README.md`, `CONTRIBUTING.md`,
  `CLAUDE.md` and each guide in `docs/` but the audit's log: the way in, the folder map and the
  commands hold; the glossary has every word the milestone changed and none it retired; the
  changelog's entry says what a book's owner needs before moving; the desk's Method and each
  page's help agree; history, finished plans and decided questions are gone; and each
  document's lines before and after.
- **A change to the app is written up in [`CHANGELOG.md`](CHANGELOG.md)**, under Unreleased, a
  store move by name; a push that changes the app and not the changelog is refused
  (`test_hooks.py::test_a_checkouts_branch_that_changes_the_app_writes_it_up`).
- **Never bypass a hook.** A branch reaches `main` as a pull request. The maintainer's yes turns
  its auto-merge on, and GitHub merges it once CI's `guard` is green; it runs on every pull
  request and on `main`. A Dependabot bump within its major version merges the same way, unasked
  (`dependabot-merge.yml`), and so does the nightly agent's clean pull request, whose yes was
  given in advance by a ready issue (below).

### The nightly agent (on trial since 12 Nov 2026)

Unattended Claude sessions work the ready issues, and the maintainer checks in when they ask.
This is a trial: the process is being developed as it runs, and each surprise becomes a rule here,
a test, or a better-written issue. **This section is the agent's instructions**; the agent never
changes it.

**How it runs**

- **Three routines on claude.ai**, each in the personal cloud environment "PortFusion", whose setup
  script builds the venv on Python 3.13 and installs `tools/`. A routine names what it follows
  here, the ready check and the answer run their own part and the night run the whole section,
  and sets how many issues a run takes; nothing else is kept there.
  - **The ready check**, by day: shapes and plans the next work and asks its questions before the
    night, and keeps the dependencies.
  - **The night run**, at 02:00 UK time: builds the ready issues.
  - **The answer run**, ten quiet minutes after the maintainer's last answer or change: records
    what was answered or changed, and builds what of it stands under Next.
- **A run has a cap.** No more issues than the routine names, and no issue past a second attempt
  at a green guard: one that will not go green is left as a draft pull request with what blocks it
  at the top, and the run moves on. A run that is going nowhere stops and says so; it does not file
  issues to show work.
- **The direction is [`docs/direction.md`](docs/direction.md)**: for whom, what never, and what
  each milestone is for. It changes only at a gate, by the maintainer's answer (The answer run,
  below); a release's read checks it and changes nothing in it.

**Which issues, in what order**

- **An issue is ready when it meets its Definition of Ready and carries no `decision` label**, so
  it can be built unattended and merged unread. A fix, and a slice of a feature, needs all five:
  - **Cause**: what in the code makes the symptom, by file and function. A symptom alone is
    evidence, not an issue. A slice's Cause is what the code lacks, by file and function.
  - **Done**: the checks that say it is done, each one a test, a walk step or a command can make.
  - **Not in scope**: what the fix leaves alone.
  - **Decisions**: every question answered by the maintainer, quoted with the date. An answer in
    a comment counts; the agent copies it into this section before it starts.
  - **Order**: what it waits on, and what waits on it. The issue's Order is the source; a Queue
    line's "waits" only copies it.
- **A feature, labelled `feature`, is ready when its shape is decided.** It is never built
  itself; its slices are (Features, below). It has Not in scope, Decisions and Order, and:
  - **Outcome**: who can do what they could not, on which page, in one sentence, and which job
    of the direction page it serves.
  - **Shape**: the option chosen on its design card, quoted with the date, and the options
    declined.
  - **Reach**: the stability rules it touches, the figures that move, and any store move with
    its migration.
  - **Slices**: two to six, in order. More than six makes it two features.
  - **Introduction**: how it stays hidden until its last slice, and what that slice turns on.
  - **Trial**: three jobs for the maintainer to try on their own book after the release.
- **The milestone being worked is the lowest open milestone.** The Queue's Next holds only its
  lines and ends with the release checklist (#156), which stays open: each release ticks it, and
  the release's pull request links to it. The tag is the maintainer's.
- **The gate: when only the checklist is left under Next, with any feature whose shape is not
  decided, nothing of the next milestone is built.** The ready check posts the gate review that
  day (The ready check, below). The gate is answered when a comment headed "Gate review" for the
  milestone is on #206 and #206 carries no `decision`; only then is the checklist worked, ready
  as it stands.
- **The checklist is never closed.** Its pull request says "For #156", not "Closes", and ticks
  its boxes.
- **After the tag, the next milestone opens.** A night run or ready check that finds the release
  tagged and its milestone closed first moves the Queue's lines from after the gate to Next, in
  the order answered, the checklist last.
- **The Queue sets the order**: the open issue "Queue: what the nightly agent builds next" (#206)
  ranks the lines of the milestone being worked, unblockers first, then bugs and wrong figures,
  small safe fixes, features and polish. A run takes the first line under Next whose issue is
  ready and has no open pull request of its own, and whose "waits" issues are all closed; it
  skips the rest and never reorders, but for a review the maintainer has answered (The ready
  check, below). Nothing outside Next is built: an open pull request of an issue that is not
  under Next is kept level and green, and nothing is added to it. Each issue is read whole,
  comments included, before its work starts.
- **The agent keeps the Queue current**: after each pull request merges it ticks the line and moves
  it to Done, and each issue it files goes under To rank, for the maintainer to place; a decided
  feature's slices are the exception (Features, below). It reads the Queue afresh just before
  each edit, since another run may have changed it.
- **A milestone being worked only gets shorter**, except for the slices of a feature already in
  it: nothing else joins Next but by the maintainer's placing. An issue the agent files takes
  the area labels of the issue it came from, and a milestone only when it fits the theme of the
  one being worked (the direction page's arc); the Queue review proposes a place for the rest.
- **Its own open pull requests come first** in the night run. Before a new issue, each one is
  brought level with `main` (merged in, never rebased), its pictures retaken when a page it changed
  moved under it, and its CI made green, so none waits on the maintainer for anything but a yes it
  asked for.
- **No ready line in the Queue and nothing to tend: stop**, posting nothing.

**Asking and answering**

- **Every question for the maintainer is asked at the end, under "Questions for you"**: of an
  issue, and of a comment that stops one. A question is one line, written to be answered on a
  phone: `**Q1** the question? **a** an option (recommended) · **b** another`, with what it
  costs in a few words. Tables above it are evidence, read only when wanted, and carry no column
  to fill in.
- **The maintainer answers in one comment, a line a question**: `Q1: a`, `Q2: b, and …`, or
  `All as recommended`. **That comment is the yes.** A question is settled when its answer is
  written so; a recommendation is not an answer, and neither is a comment's tone or silence.
- **The run that reads a full answer records it**: it copies the answers into the issue's
  Decisions, quoted with the date, and takes `decision` off. An answer that leaves a question
  open is asked again, for that question alone, and `decision` is taken off and put back on, so
  the maintainer is told.
- **A reply beginning `Change:` redirects an issue or one of the agent's pull requests.**
  `answer.yml` marks it 👀 and holds the work at once: the issue takes `decision`, the pull request
  loses its auto-merge. The answer run then reads the change and rewrites the issue's Done, Not in
  scope and Decisions to match, quoting the change with the date. If nothing is left unclear it takes
  `decision` off; otherwise it asks what the change leaves open. A pull request already open is
  brought to the changed issue, or closed with the reason when the change makes it moot.
- **An issue whose title begins `Idea:` is new work in the maintainer's words.** The ready check
  shapes it in place: the maintainer's words kept at the top, quoted; the title made an issue's
  title; its area labels; the milestone whose theme it fits; and a line under To rank in the
  Queue. One that adds function is shaped as a feature and labelled `feature`, its Shape left
  for its design card; any other gets a cause found in the code, Done, Not in scope and Order.
  What only the maintainer can settle is asked, with `decision`. An idea that is already an open
  issue's is added to that issue and closed.
- **A question is asked when its issue is next, not when it is filed.** An issue short of its
  Definition of Ready carries its questions at its end, or is evidence for one that meets it. One
  the agent files, from a find or from a comment, has its Decisions read "Open: asked when it is
  planned"; it takes no `decision`, so it pings no one, and it is not ready. The ready check asks
  them, with `decision`, when it reaches the issue under Next. Two are asked sooner: an `Idea:`,
  as it is shaped, since the maintainer is waiting on it, and a feature's shape, on its design
  card. An answer the maintainer gives early, in a comment, counts when the issue is reached.
- **An issue's questions are kept few**: what only the maintainer can decide. What the agent can
  settle from the code, the record's rules or an answer already given, it settles and says so.
- **At most five questions stand open on the issues of the milestone being worked**, a design
  card's among them; #206's reviews and the maintainer's own long-standing decisions (#3, #5, #6
  and the like) apart. Beyond five the ready check asks only what blocks the first line under
  Next: an `Idea:`'s and a card's questions are written, and wait.

**The ready check**

- **It reads [`docs/direction.md`](docs/direction.md) first**, and cites it for a milestone, a
  cut or an idea. The Definitions of Ready and the gate are under Which issues, the limits on
  questions under Asking and answering (above), and what its debrief says under Telling the
  maintainer (below).
- **After a tag it opens the next milestone** (Which issues, above), before anything else.
- **"Covers" is by the code, not the topic.** An open issue covers a find, an idea or a bump when
  its Cause or Done names the same file and function; the ready check reads every open issue's
  Cause and Done for that before it files a new one.
- **It first shapes each open `Idea:` issue** (Asking and answering, above).
- **Then it keeps the dependencies.** A Dependabot pull request that stays in its major version
  merges itself (`dependabot-merge.yml`); the ready check looks after the rest. Each open
  Dependabot pull request left for the maintainer (a major or a 0.x bump), each one red or behind
  `main` for a week, and each open Dependabot security alert it can read becomes an issue that meets
  the Definition of Ready, under To rank, unless an open issue covers it. Its cause is what the
  release notes change that this repository uses, by file; its Done shows each test that leans on
  the package still able to fail. Its pull request makes the bump and closes Dependabot's, which is
  never merged on its own.
- **Then the design card, or a decided feature's slices** (Features, below).
- **It runs the planning, by day, so the questions reach the maintainer before the night.** It
  takes the first lines under Next in order, up to the routine's number, ready or not: an issue
  whose questions are written but not asked is one it is there to ask. It skips a feature, an
  issue with an open pull request of its own or an open "waits" issue, and one whose checked plan
  is its latest comment and whose files `main` has not changed since.
- **For each, the plan and its check** (below, under Building), against today's `main`. A plan
  with no question is posted as **Plan, checked**, naming the commit of `main` it was checked
  against. A plan that finds a question, or finds the issue's cause or premise no longer holds,
  asks it and labels the issue `decision`; so do the questions an issue was filed with, less any
  the maintainer has answered in a comment since.
- **Twice a week it reviews the whole Queue**: on its first run when no review is on #206 from the
  last three days. It reads every open issue of the milestone being worked and the next, against
  today's `main`, and posts a **Queue review** on #206: issues that duplicate one another, to
  merge; overlaps by file and function that no "waits" orders; causes that no longer hold, to
  close with the reason; a place for each walk find left to sort; and a suggested order. Each is a question, with its recommendation, and #206 takes
  `decision`. Below its questions it lists three ideas for improving a feature, a line each with
  the job it serves and its cost; they are not asked, and the maintainer takes one up with an
  `Idea:` issue. A review with nothing to ask is posted for its ideas alone, without `decision`,
  so it pings no one. None is posted while a gate review stands unanswered.
- **With the review it sorts "Walk finds: to sort" (#220)**, and not each run. A find goes
  onto the open issue that covers it, as evidence, or onto the decided feature that will rework
  its page; one not worth an issue is struck through with the reason. The rest stay one line
  each, and the review proposes their place. A find the maintainer has placed is shaped then,
  with others like it, into an issue that meets the Definition of Ready, on the line answered,
  its questions written but not asked. Each line handled is struck through, so the list only
  holds what is unsorted.
- **On the day the gate is reached it posts the gate review** on #206, once, headed "Gate
  review" with the milestone's name, in the Queue review's place and holding all of it for the
  next milestone, and:
  - what shipped, against the milestone's sentence in the direction page;
  - keep or pull, for each feature the maintainer has trialled;
  - each design card unanswered, and a move for each feature left under Next with no shape;
  - the next milestone's proposed shape: its order, its cuts and its moves;
  - at most three ideas, a line each with its cost; an idea never pings on its own;
  - the rules of this section that cost a run a wrong turn, time or money, each with its run;
  - at most five questions in all, the direction page's open ones among them. What it holds
    beyond five is listed as proposals, and asked in the next review. #206 takes `decision`.
- **It writes no code**, opens no branch, and changes no label but `decision` and those of an
  issue it shapes or files.

**Features**

- **A design card asks a feature's shape.** The ready check posts it on the issue of the line
  under Design next in the Queue, or of a feature at the top of Next, and the issue takes
  `decision`. Above the fold, in at most 150 words: the outcome in one line; three
  options, each a different idea of the feature and not one idea at three sizes, each with its
  cost (slices, figures that move, a migration or none); a link to a mock page; a
  recommendation; and at most three questions. The evidence is folded under `<details>`.
- **The mock page shows today's page and each option**, on the demo's names. It is a private page
  published with the Artifact tool and touches no code. A run that cannot publish without stopping
  to ask gives words and a picture of today's page instead, and says so.
- **Two cards a week, at most.** When Design next is empty the ready check fills it itself, with
  the first feature that has no decided shape, lowest milestone first and in the order its
  milestone's description gives. It posts a card when none stands unanswered and fewer than two
  went up in the last seven days.
- **One card is open at a time, and one feature is being built.** The rest wait as lines: a
  feature's slices are written only when no other feature's slices stand open under Next. A card
  unanswered is listed in the next gate review, and meanwhile the runs work what is ready.
- **A decided shape becomes slices.** The ready check completes the feature and writes its slices
  as issues, each "Part of #n", each leaving `main` green with its own changelog line. Their
  Decisions quote the card.
  A slice takes its feature's milestone and area labels. It places them at the feature's line,
  in order, wherever that stands in the Queue, and under To rank when it has none. The last
  slice's pull request closes the feature too, and its line is ticked with the slice's.
- **A slice stays hidden until the last**: nothing registers it on a page, a tab or the report.
  One that moves the store or a figure is the exception (Merging, below). The last slice turns
  the feature on. Its cold walk walks the whole feature, by the feature's
  Trial jobs, and its pull request shows the maintainer each page's picture before and after.
- **The trial is on the release.** The maintainer tries the Trial jobs on their own book, and
  keep or pull is asked in the next gate review. Pull applies to display slices only: a store
  move is not pulled back. A pull answered becomes an issue, its Decisions the answer, first
  under Next; its pull request reverts the slices and is never clean.

**The answer run**

- **The maintainer's answers start it, in a batch.** `answer.yml` sees the owner's comment on an
  issue labelled `decision` that begins `Q1:` or `All as recommended`, or one that begins
  `Change:` on an issue or an agent's pull request, waits ten minutes, and fires
  the routine "PortFusion answer"; an answer within those minutes starts the wait again, so answers
  given together make one run. Nothing of a comment is passed.
- **It first claims every answered or changed issue**: each open issue labelled `decision` whose
  owner's latest comment answers it or begins `Change:`, and each issue whose open pull request of
  the agent's has the owner's `Change:` as its latest comment. It records each answer or change
  (Asking and answering, above) before it builds any, so a run started later does not take the same issue.
- **An answer records a decision; only lines under Next are built.** Every answer is recorded,
  wherever its issue stands. An issue not under Next, a feature, and the issue a design card was
  answered on are left there: nothing of them is built, and the maintainer's placing or the
  ready check's slices come first. A card's answer takes its line out of Design next.
- **An answered review is applied, not built.** The Queue (#206) is never an issue to build and
  takes no Decisions section. For a Queue review the run makes the answered changes: the Queue's
  lines, a "waits", an issue merged or closed with the reason, a find's place noted on #220. For
  a gate review it also moves issues between milestones, writes the next milestone's lines in the
  order answered under the Queue's heading for after the gate, files the issue for a pull
  (Features, above), and edits `docs/direction.md` to the answer in a pull request that links
  #206 and may merge itself once `guard` is green, the answer being its yes. Then it takes
  `decision` off #206, and goes on.
- **Then it builds those under Next one after another, in Queue order**, as the night run would,
  up to the routine's number. One still not ready, a question open or a "waits" issue open, it
  says which on the issue and leaves; the night run takes it when it is.
- **Under Next, an issue with a branch of its own continues on it**, brought level with `main`.
  An open pull request from it is completed to the whole issue, its own "Part of #n" made "Closes
  #n", and merges itself if it is clean. A slice's "Part of" its feature stays.
- **For the rest it follows Building, Merging, Telling the maintainer and Never**, below, and
  keeps the Queue as the night run does (Which issues, above).

**Building**

- **A plan, checked, before code.** The agent writes its plan as a comment on the issue: the files
  it will change, how each "Done" check will be made, and what it will not touch. A fresh agent,
  given only the issue and that plan, checks the plan against the code and says what is missing or
  wrong; the plan is mended before a line is written. A plan the ready check has already checked is
  used as it stands when `main` has not changed the files it names since; otherwise it is written
  and checked again.
- **The plan names its overlaps**: every open issue and open pull request whose Cause, Done or diff
  names a file or function the plan changes. Each is settled in the issue: a "waits" in Order when
  one must land first, a line in Not in scope when the other owns that part, or a question when the
  two issues' Done disagree. The plan's checker looks for one the plan missed.
- **One issue, one branch, one pull request**: a branch claude/<name> from the latest `main`,
  worked by the conventions above (changelog, own diff reviewed, a changed desk page walked cold),
  the guard run, and the desk walk if a desk file changed. The pull request says "Closes #n", and
  the agent goes on to the next issue without waiting for a merge.
- **Done means `guard` green on the last push.** No pull request is called clean, and none is
  left, until CI's `guard` has passed on its newest commit; a local run is a quick check, not the
  proof.
- **A question stops the issue; nothing of it is built.** An open question, in the issue, in the
  plan or appearing mid-build, is asked at the end of a comment on the issue, the issue is labelled
  `decision`, what is built so far is pushed to its branch with no pull request, and the run moves
  on. The answer starts the issue again, whole, on that branch.
- **Something a comment raises outside its issue** becomes a new issue under To rank, its
  questions written but not asked, linked from the issue, and is not built.
- **The cold walk keeps to the pages the change touched**, with jobs about the change. What it
  meets there that the change did not cause goes first onto the open issue that covers it, as
  evidence, and the rest onto "Walk finds: to sort" (#220), one line a find, with no question and no
  ping; the pull request lists both.
- **A CI failure on its pull request** is the agent's to fix, and it waits for the guard's result
  before it leaves a pull request. **It waits in the foreground**, by a command that polls the
  checks and the `baselines/<branch>` ref, run again until they finish, **never by ending its
  turn** (Telling the maintainer, below). A retake not landed ten minutes
  after the label is asked for again, `baselines` taken off and put back on (a label already on
  starts nothing). When the walk fails only because a page the issue meant to
  change looks different, the agent labels the pull request `baselines`: a workflow retakes the
  walk's Linux pictures onto a branch beside it, `baselines/<branch>` (`baselines.yml`); the agent
  merges that in and pushes, which runs the guard, and the pull request lists the pages whose
  pictures changed. The pictures are the agent's to keep, compared on Linux alone; the
  maintainer never takes them, and reads them only for a feature's last slice (Features, above).
  A failure the agent cannot fix is said at the top of the pull request, with what would fix it.

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
- **Three are never clean**: a pull request that moves the store (a table or column of
  `record/schema.py`, or a move in `record/migrations.py`), a slice that moves a figure (what an
  engine method returns on the demo), and the slice that turns a feature on. The first two are
  never hidden: each says what moves at the top of its pull request, and in the changelog.
- **Any other waits for the maintainer's yes**, auto-merge off, with what is needed from them at
  the top of its description. The yes is a reply beginning `yes` on the pull request, which turns
  its auto-merge on (`answer.yml`), or the button itself.

**Telling the maintainer**

- **A question or pull request reaches the maintainer as a mention**: the agent works as the
  maintainer's account, so GitHub would tell them nothing; an issue labelled `decision`, and a pull
  request from a branch whose name begins claude/ that waits for a yes, get a comment from
  `github-actions[bot]`, headed "PortFusion agent", that names them (`notify.yml`). A pull request
  merging itself gets the same note without naming them: it asks nothing, so it pings no one.
- **A run is one turn, and its last message is the debrief.** The routine delivers the message
  that ends the run's first turn to the maintainer's phone, and nothing after it; a run sends no
  push notification of its own, and nothing on GitHub wakes it again. So every wait is inside
  that turn: a helper agent (the plan's checker, the reviewer) is run in the foreground and
  waited for, and CI is polled in the foreground. A message that ends the turn is the debrief,
  never a note that something is still running. While a gate review stands unanswered, or a
  release untagged, the debrief says in one line what the run waits on.
- **The agent's own comments never begin `Q` and a number, `All as recommended`, `yes` or
  `Change:`**, in any case: the maintainer's shapes, which start a workflow, since it writes as
  the maintainer's account.

**Never**

- **The agent never pushes to `main`, bypasses a hook, or changes** a workflow, a ruleset, a test
  that holds a stability rule, this section, or a routine (its prompt, model, effort, cap or
  schedule); those are changed in a session the maintainer is part of.

### The desk and the report

- **Check a change on the demo**: `portfusion desk --book demo --port 8769`, never on a desk a book
  is using.
- **The renderers move together**: what changes on the desk changes on the report.
- **The desk and the report carry as little prose as they can.**
- **Every size on the desk is a step of the type scale** in `desk/static/kit.css`.
- **A panel is one file with one name**, and its tab runs in the order of the work
  (`desk/panels/__init__.py`; `test_panels.py::test_a_panel_has_one_name`,
  `test_panels.py::test_the_tabs_run_in_the_order_of_the_work`).

### A book stays out

- **Examples are invented.** Use the demo's names, never a real book's people, holdings, references,
  figures or dates: in code, guides, commits, branches, issues or pull requests.
