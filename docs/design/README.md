# The new look: the design system

The look the desk's new frame is built in, drawn once, on the demo book. It is the drawing the
maintainer agreed on 20 Nov 2026 (#9, Decisions) and the dark scheme they chose on 25 Nov 2026,
written as two stylesheets, a sheet and three pages. It is the design system the loop's builders
work from: every value of the look, every part and each of its states, the light and shadow, the
glass and the motion, in light and in dark. Whoever builds a part can open the sheet, read the
rule, and compare what they built.

It is a drawing and not the app: the desk does not load it, nothing in `src/` reads it, and no
figure in it is worked out. Every name and figure is the demo's.

| File | What it holds |
|---|---|
| [`look.css`](look.css) | the light scheme's values, each a token named by its job, and every part, as one rule that holds each of its states |
| [`dusk.css`](dusk.css) | the dark scheme: a second value for the tokens that change in the dark, and nothing else |
| [`icons/`](icons) | the icons: Lucide's own files, one for each job (Icons), and its licence |
| [`parts.html`](parts.html) | the sheet: every token printed from the two stylesheets, light beside dark, and every part drawn in each of its states, in both schemes |
| [`home.html`](home.html) | Home, the book: the lead card, two figure cards, what the record needs, the accounts, the largest holdings, the value at each quarter end, and the latest events |
| [`companies.html`](companies.html) | the Companies list: chips for held, sold and all, a find field, every company in one table that sorts, and its total |
| [`company.html`](company.html) | a company's page: the lead card with its tiles, the status panel, and six tabs: the overview (lines held and a chart), trades, round trips, income (empty in the demo), the marks, and the reasoning |

## Opening it

The pages are files, with no server and no build step:

```bash
open docs/design/parts.html             # on the Mac, in the default browser
```

A run with Playwright opens `file://<checkout>/docs/design/home.html` the same way. On Home,
Quenlan Robotics Inc.'s row opens the company's page, and "Back to Home" returns. The company's
six tabs each show their own section. Home's "All 5 companies" and the menu's Companies open the
Companies list, where the chips, the find field and the heads that sort work on the demo's five
companies. Nothing else on the pages leads anywhere: only these three pages are drawn so far.

The three pages are drawn in the scheme the Mac is set to, as the desk will be. To see the other,
change the Mac's Appearance (System Settings, Appearance), or open the page in Playwright with
`colorScheme: "dark"`. The sheet draws both side by side, whatever the Mac is set to.

The typeface is Inter, read from the machine: one without Inter installed shows the system's face
in its place, and line breaks may differ. The desk gets Inter's own file with #343.

## How it holds together

- **A value is defined once.** A value the parts share is a token in `look.css`'s `:root`, named
  by its job, and its dark value, if it has one, is the same token in `dusk.css`. A value only one
  part wears, such as a button's padding, is typed in that part's one rule. The sheet prints
  every token from the two stylesheets as it opens, and each part's height, padding and corner
  from its rule, so it cannot say one thing and the stylesheets another.
- **A part is defined once**, in one rule of `look.css`. The pages are made of those classes and
  hold no style of their own, so a change to a part is one edit, and every page shows it. That
  is the maintainer's rule for the app too: a component is the same wherever it appears.
- **A state is defined once**, in its part's rule: what the pointer gives by `:hover` and
  `:active`, what the keyboard gives by `:focus-visible`, and what is chosen by the attribute that
  says so (`aria-current`, `aria-pressed`, `checked`, `data-sort`), as is a control that can't be
  used (`disabled`, `aria-disabled`) or a button at work (`aria-busy`). The pointer's and the
  keyboard's states also answer to `data-as` (`over`, `pressed`, `keyboard`), so that the sheet
  can draw them with no pointer on them. The desk's own parts need only the pseudo-class.
- **Every control shows where the keyboard is**, in one ring of the accent (`--focus`), whatever
  the control, and never under the pointer. A table's scroll box keeps 4px of room round its
  table, the ring's reach, so a row's ring is never cut. Press Tab on `parts.html` to see it.
- **The values are #343's tables**, the parts are #344's, and the dark values are built by #347's
  switch. Where an issue and this folder differ, say so on the issue before building either.
- **The token and class names here are this folder's own.** What the house calls each value is
  settled where `house/` gains them (#343), and what the kit calls each part where the kit draws
  it (#344).
- **The markup is the drawing's, not the kit's.** A table here is a grid of `div`s; the kit's
  `table()` draws a real table. What the reference fixes is how a part looks and moves, not the
  elements it is made of.

## Light and shadow

Light comes from above. A surface sits at one of four heights, and its shadow says which.

| Height | What sits there | Its light and shadow |
|---|---|---|
| sunken | a well: a tab track, a chart; and what is typed into or ticked: the find field, a tick box that is off | `--shadow-well`: a shade inside the top edge and a hairline inside the rim, on `--sunken` |
| resting | a card; the choice box | `--shadow-card`; `--shadow-choice`, smaller, for the choice box |
| resting, under the pointer | a card that opens something, which rises 2px | `--shadow-card-over` |
| raised | the lead card, one to a page; a tile on it; the selected menu line and the chosen chip; the selected tab; the main button, which rises 1px under the pointer, and a tick box that is on | `--shadow-lead`, `--shadow-tile`, `--shadow-line-on`, `--shadow-tab-on`, `--shadow-button` and `--shadow-button-over` |
| floating | the glass: the menu and the bar, and nothing else | `--shadow-glass` |

- **A shadow is a stack of up to four layers**, each with its own job: a lit top edge
  (`inset 0 1px 0`), a hairline ring round the rim (`0 0 0 1px`, inside the rim on the glass and
  the lead card), a contact shadow close under it, and an ambient shadow that falls far and soft.
  The sheet names each layer of each shadow, in both schemes.
- **What is raised out of a surface wears `--raised`**: a tile on the lead card, the selected
  menu line, the selected tab and the chosen chip. In light it is a card's white; in dark it is a
  pale veil over what is under it.
- **The ground** is warm paper (`--ground`) with two glows: violet at the top left
  (`--glow-violet`) and warm at the top right (`--glow-warm`), each fading out by 62% of its
  reach. The page scrolls over them.
- **The glass** is the menu and the bar: `--glass` over a blur of 22px at a saturation of 1.7,
  with `--shadow-glass`. The lead card is a violet glass of its own: `--lead` over a blur of 18px
  at 1.5, with `--shadow-lead`. A card that holds a table or a figure is never glass. Safari reads
  `-webkit-backdrop-filter` only with its values typed, so the blurs are typed in `.glass` and
  `.lead`, and nowhere else.
- **In the dark** the lit edge is a faint white, the ring is a faint white line, and the shadows
  fall deeper and black (The two schemes, below).

## The parts and their states

Each part is drawn on the sheet in each of its states, in both schemes. A state not named here is
not drawn, and is not invented on a page.

| Part | Drawn by | Its states |
|---|---|---|
| the frame | `.frame`, `.menu`, `.page` | the menu beside the page, `--gap` apart; the menu scrolls away with the page |
| a run of boxes | `.stack`, `.flow`, `.split`, `.section`, `.head` | none: they set boxes `--gap` apart, and a section's heading `--gap-tiles` above its cards |
| the menu | `.menu > .glass`, `.brand`, `.group`, `.title` | none of its own; its lines have theirs |
| a menu line | `.line`, `.with-icon`, `.count` | its icon before its name, in the muted ink; at rest; under the pointer (`--line-over`); the page you are on (`aria-current="page"`: raised, in the accent's ink, its icon too, at 600); the keyboard |
| the name and the mark | `.brand .mark`, `.wordmark` | none (The name and the mark, below) |
| the bar | `.glass.bar`, `.where` | the page's title and its note, the way back, and the page's one main button; it stays at the top as the page scrolls under it |
| the main button | `.push` | its icon before its words; at rest; under the pointer (rises 1px, `--shadow-button-over`); pressed (back down); the keyboard; can't be used; at work (`aria-busy="true"`: holds still, says what it is doing, and turns a small ring in its icon's place). One to a page |
| the quiet button | `.quiet` | at rest; under the pointer (`--quiet-over`); the keyboard; can't be used |
| a link to more | `.more`, and `a` | at rest, in the accent; under the pointer, in the ink; the keyboard (`.more`) |
| tabs | `.well.tabs`, `.tab` | a tab at rest, in the muted ink; under the pointer, in the ink; selected (`aria-pressed="true"`: raised, `--shadow-tab-on`, in the accent's ink); the keyboard; can't be used (in the muted ink, answering nothing). The selected tab is the only one with a shadow, and its content fades in |
| a tag | `.tag` | four kinds: `.problem`, `.gap`, `.clear`, `.closed`, each with its kind's icon before its words |
| an icon | `.icon` | none: it takes the ink of the words beside it (Icons) |
| a card | `.card`, `.card.figure`, `.card.tabled` | resting |
| a card that opens its object | `.card.lift` | at rest; under the pointer (rises 2px, `--shadow-card-over`); the keyboard |
| the lead card | `.lead`, `.headline`, `.tiles`, `.tile` | one to a page: the page's one large figure, and tiles for the figures that explain it |
| a well | `.well` | sunken |
| a table | `.scroll`, `.table`, `.cols`, `.row`, `.n`, `.dim`, `.two` | a row under a soft rule; figures to the right, in tabular numerals, and a cell never wraps; a cell with a smaller second line (`.two`). The scroll box keeps 4px of room round the table for the keyboard's ring |
| a row that opens its object | `.table > a.row` | at rest, its name in the accent's ink and no rule under it; under the pointer (`--accent-soft`); the keyboard |
| a head that sorts | `.sort` | at rest, in the heads' muted ink; under the pointer, in the ink; the order, down or up (`data-sort`: in the ink, with an arrow); the keyboard |
| the total row | `.row.total` | under a full rule, in the names' weight |
| an empty table | `.empty` | one line under the heads, saying so, and where to look instead |
| a chart | `.well.chart` | one line in the accent, until a chart's own colours are given (What is still open) |
| the status panel | `.card.status`, `.items`, `.item`, `.latest` | what stands against the object, each a tag and a sentence; then what last happened to it |
| what happened | `.events`, `.what` | events newest first, each its sentence, and under it the day and the account |
| what the record needs | `.needs`, `.need`, `.says` | each item its tag, its sentence and the object it concerns, and one quiet button that opens that object |
| a field grid | `.fields` | one record as labelled fields |
| filter chips | `.filters`, `.filter`, `.count` | at rest (`--quiet`); under the pointer (`--quiet-over`); chosen (`aria-pressed="true"`: raised as a selected line is, its count in the accent's ink); the keyboard; can't be used |
| a find field | `.find` | empty, saying what it finds; typed into; the keyboard; can't be used (its words in the muted ink). Sunken |
| a choice box | `.choice` | closed, resting with its chevron; the keyboard; can't be used. Open, it is the Mac's own list |
| a tick box | `.tick` | off (sunken); on (`checked`: the main button's violet with a white tick); the keyboard; can't be used (sunken, on or off, its tick and its words in the muted ink) |
| the type | `.label`, `.note`, `.small`, `.name`, `h1`, `h2`, `.num-lead`, `.num`, `.num-card`, `.num-tile`, `.up`, `.down` | the ten steps on the sheet; a note in the gap's or the clear's ink (`.note.gap`, `.note.clear`) |

A **control that can't be used** (`disabled`, or `aria-disabled="true"`) drops to the quiet fill
(`--quiet`), its words in the muted ink, with no shadow, and answers neither the pointer nor a
press. Its words still pass 4.5 to 1 in both schemes, and the violet is left to mean what can be
pressed. A tab and the find field keep their own ground and only mute their words. A **main button
at work** (`aria-busy="true"` and `aria-disabled="true"`) keeps its violet and holds still, says
what it is doing in the present ("Refreshing prices…"), and turns a small ring before its words,
so a long wait never looks stuck; the keyboard keeps its place on it. The maintainer chose both on
25 Nov 2026, from two ways of each drawn side by side.

## Motion

| What moves | How | How long |
|---|---|---|
| a pointer's answer: a line, a tab, a row, a button, a chip, a head that sorts, a tick box, a card rising | its fill, its shadow, its ink, or how high it sits | `--dur-pointer`, 160ms, `ease` |
| a tab's content | fades in | `--dur-tab`, 200ms, `ease` |
| a page's content | arrives: fades in and rises `--rise`, 10px, in three steps (`.arrive`, `.later`, `.latest`), `--step` apart | `--dur-arrive`, 260ms, on `--ease-arrive` |
| a main button at work | the small ring before its words turns, again and again | `--dur-turn`, 1000ms a turn, `linear` |

No figure is animated, and nothing else moves. The sheet prints what each part moves, read from
its rule.

## Where the Mac asks

| The Mac's setting | What changes |
|---|---|
| Appearance, dark | every token `dusk.css` gives a second value (The two schemes) |
| Reduce motion | nothing arrives, fades, rises or eases, and a button at work's ring holds still: no animation and no transition |
| Reduce transparency | the glass is solid `--glass-solid` and the lead card solid `--lead-solid`, with no blur |
| Increase contrast | the glass, a card, the lead card, a tile, the find field, the choice box and a tick box gain a 1px outline of `--contrast-edge` |

## The two schemes

The maintainer chose the dark scheme on 25 Nov 2026, from three drawn over these pages: Dusk, the
light look's warm paper turned down to warm graphite.

- **It follows the Mac's setting**, as today's desk does. Each page links `dusk.css` after
  `look.css`, for a Mac set to dark:
  `<link rel="stylesheet" href="dusk.css" media="(prefers-color-scheme: dark)">`. There is no
  switch of the desk's own.
- **Only colour and light change.** Every corner, gap, size, type step and motion is the light
  scheme's, and so are the main button and the mark's tile. No part has a rule of its own in the
  dark: the dark scheme is a second value for some of the tokens, and nothing else.
- **A surface lifts by a lit top edge and a deeper shadow**, since a soft shadow barely shows on
  a dark ground. The lead card is a deep violet glass.
- **What is raised out of a surface is a lighter step of it** (`--raised`), so a tile on the
  violet lead card takes the violet and never sits on it as a dark box.
- **The accent lightens as a colour of text**, to `#978CFF`, so a link, the name's "Fusion" and
  a chart's line read on the graphite. The mark's tile wears its own token (`--mark-tile`) and
  stays the brand's violet, `#4F3FD6`, with the harbour in white, in both schemes.
- **Every text colour passes the accessibility contrast bar** (4.5 to 1) on what is behind it:
  text on a card is about 13.6 to 1, muted text 6.8 to 1, and a tile's label on the lead card
  4.7 to 1 at its lightest, measured on the drawn company page.
- Where the Mac asks for less transparency or more contrast, the dark scheme gives its own solid
  glass, solid lead card and edge (`--glass-solid`, `--lead-solid`, `--contrast-edge`).

## The name and the mark

The maintainer settled both on 21 Nov 2026.

- **The name is PortFusion**, alone, in Inter 700 and in two colours: "Port" in the ink and
  "Fusion" in the accent. `.wordmark` sets it, and the `span` inside it is the second word. A
  tab's or a window's title is the browser's, in one colour.
- **The mark is the harbour**: one line that goes up the mast and round the bowl and stops short
  of the mast, and a core inside it. In a box of 32, the line is
  `M10.5 24.5 V7.5 H16.4 A5.7 5.7 0 0 1 16.4 18.9`, 2.8 thick with round ends and a round corner,
  and the core is a dot of radius 2.1 at 16.5 across and 13.2 down.
- **In the menu** the mark is white on a tile of the brand's violet (`--mark-tile`), 32px with a
  corner of 10 (`.brand .mark`), in both schemes. Without a tile, the line is in the ink and the
  core in the accent.
- **In a browser tab** the icon is the mark on its tile, with the line and the core drawn 1.28
  times larger about the point 16.3 across and 16 down, so the opening and the core still show
  at 16px. Every other icon, the menu's, the Dock's and the touch icon, uses the one drawing. The
  maintainer settled this on 23 Nov 2026.
- **The app wears neither yet.** Its header says the old name and its icons draw a stand-in ring,
  until the frame is turned on (#347).

## Icons

The icons are Lucide's, version 1.69.0, under its ISC licence, which [`icons/LICENSE`](icons/LICENSE)
carries. Each is a line 2px wide on a 24px grid, with round ends and corners, close to the
harbour's own line. The maintainer chose the set on 25 Nov 2026, from Lucide and Phosphor drawn
side by side.

- **An icon stands before a menu line's name, the main button's words and a tag's words**, and
  nowhere else. Everything else stays words, and a new place for an icon is asked for.
- **It is drawn in the ink of the words beside it**, `--icon` (16px) square, and `--icon-tag`
  (12px) on a tag. In the menu it is in the muted ink, and in the accent's ink on the page you are
  on. On a button at work, the turning ring stands in its place.
- **Each job has one icon, and each icon one job:**

| Job | Its icon in `icons/` |
|---|---|
| Home | `house.svg` |
| Companies | `building-2.svg` |
| Accounts | `wallet.svg` |
| Quarters | `calendar.svg` |
| Inbox | `inbox.svg` |
| Prices | `chart-line.svg` |
| Trades | `arrow-left-right.svg` |
| Round trips | `repeat.svg` |
| What changed <!-- tab-name-ok: the new menu's line, in sentence case --> | `history.svg` |
| Method | `book-open.svg` |
| Refresh prices, the main button | `refresh-cw.svg` |
| a tag: a problem | `circle-alert.svg` |
| a tag: a gap | `circle-dashed.svg` |
| a tag: clear | `circle-check.svg` |
| a tag: closed | `circle-minus.svg` |

- **The files are Lucide's own, unchanged.** A page draws an icon inline, as
  `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">` round the file's shapes, so the
  line's width and ends come from `.icon`, and the words beside it say what it means. A new
  job's icon is taken from the same set, at the same version, and added to the table; an icon is
  never redrawn, and never taken from another set.

## Where it evens out the drawing

The agreed drawing typed a few values on one part that it did not type on its twin. The
reference gives each part its one value, as the consistency rule asks:

| Part | In the drawing | Here |
|---|---|---|
| a pointer's answer | 160ms, but 180ms for a card rising and 120ms for a row | 160ms for all, as #343's table says |
| a table row | 44px for a row that opens, 46px for one that does not | 44px for both |
| a table in its card | two insets, and 16px or 12px between cells | one inset and 12px between cells; a rule under a row runs 12px past its text |
| the status panel | padded 20px by 22px | a card's padding, 20px by 24px |
| the lead card's label, figure and note | 6px apart on Home, 4px on a company | 6px on both |
| a company's name in a row that opens | the accent's ink on the one row that opened | on every row that opens its company |

## What is still open

Each is drawn when the maintainer gives it, and until then no page or part decides it.

- **A chart's own colours** beside the accent, which the sector charts the maintainer wants will
  need, and **the look in print**. Both are parked by the maintainer (#9, Decisions).
- **The app's own icons.** The tab's, the Dock's and the touch icon are the mark on its tile, and
  are drawn when the frame is turned on (#347). On a dark ground the mark is the same violet
  tile.
- **Every other page.** Accounts, Quarters, the Inbox, Prices and the lists are drawn
  one by one, each before it is built (#9, Order). A page not drawn yet is made of the parts
  on the sheet; a part it needs that is not on the sheet is asked for, never invented on the page.
- **Safari.** The pages were checked in Chromium. The glass is written with the
  `-webkit-backdrop-filter` Safari reads, with its values typed, and has not been looked at there.
- **A phone** is a later study. The pages wrap as the browser narrows, and that is all.

## Changing it

A change to the look is the maintainer's. It is made in one place, and checked on the sheet, in
both schemes, and on every page:

| To change | Edit |
|---|---|
| a colour, a shadow or the glass's fill | its token in `look.css`, and in `dusk.css` if it has a dark value there |
| a corner, a gap, a size, a type step or a duration | its token in `look.css`: it has one value in both schemes |
| how a part looks, or one of its states | the part's one rule in `look.css` |
| a value only one part wears, or a blur | that part's rule in `look.css` |
| which icon a job has | its file in `icons/`, the table under Icons, and each page that draws it |

A token that no part wears, or a part that types a value a token holds, is a mistake. Once
`house/` holds the values, the house is the source: a value changes there and here in the same
pull request, until this folder is cleared out with the old look (#9, Order).
