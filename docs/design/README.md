# The new look: the reference

The look the desk's new frame is built in, drawn once, on the demo book. It is the drawing the
maintainer agreed on 20 Nov 2026 (#9, Decisions), written as one stylesheet and four plain pages,
so that whoever builds a part can open the page, read the rule, and compare what they built.

It is a drawing and not the app: the desk does not load it, nothing in `src/` reads it, and no
figure in it is worked out. Every name and figure is the demo's.

| File | What it holds |
|---|---|
| [`look.css`](look.css) | every value, as a token named by its job, and every part, as one rule that wears tokens only |
| [`parts.html`](parts.html) | the sheet: each value printed from `look.css`, the three heights, the corners, the type steps, the motion, and each part drawn once under the class that draws it |
| [`home.html`](home.html) | Home, the book: the lead card, two figure cards, the accounts, the largest holdings |
| [`companies.html`](companies.html) | the Companies list: chips for held, sold and all, a find field, every company in one table that sorts, and its total |
| [`company.html`](company.html) | a company's page: the lead card with its tiles, the tabs, lines held, a chart, the trades, the status panel |

## Opening it

The pages are files, with no server and no build step:

```bash
open docs/design/parts.html             # on the Mac, in the default browser
```

A run with Playwright opens `file://<checkout>/docs/design/home.html` the same way. On Home,
Quenlan Robotics Inc.'s row opens the company's page, and "Back to Home" returns. The company's
two tabs change what is under them. Home's "All 5 companies" and the menu's Companies open the
Companies list, where the chips, the find field and the heads that sort work on the demo's five
companies. Nothing else on the pages leads anywhere: only these three pages are drawn so far.

The typeface is Inter, read from the machine: one without Inter installed shows the system's face
in its place, and line breaks may differ. The desk gets Inter's own file with #343.

## Reading it

- **A value is defined once**, in `look.css`'s `:root`. `parts.html` prints each from the
  stylesheet as it opens, so the sheet cannot say one thing and the stylesheet another.
- **A part is defined once**, in one rule of `look.css`. The pages are made of those classes and
  hold no style of their own, so a change to a part is one edit, and every page shows it. That
  is the maintainer's rule for the app too: a component is the same wherever it appears.
- **The values are #343's tables**, and the parts are #344's. Where an issue and this folder
  differ, say so on the issue before building either.
- **Every control shows where the keyboard is**, in one ring of the accent (`--focus`), whatever
  the control. Press Tab on `parts.html` to see it.
- **The token and class names here are this folder's own.** What the house calls each value is
  settled where `house/` gains them (#343), and what the kit calls each part where the kit draws
  it (#344).
- **The markup is the drawing's, not the kit's.** A table here is a grid of `div`s; the kit's
  `table()` draws a real table. What the reference fixes is how a part looks and moves, not the
  elements it is made of.

## The name and the mark

The maintainer settled both on 21 Nov 2026.

- **The name is PortFusion**, alone, in Inter 700 and in two colours: "Port" in the ink and
  "Fusion" in the accent. `.wordmark` sets it, and the `span` inside it is the second word. A
  tab's or a window's title is the browser's, in one colour.
- **The mark is the harbour**: one line that goes up the mast and round the bowl and stops short
  of the mast, and a core inside it. In a box of 32, the line is
  `M10.5 24.5 V7.5 H16.4 A5.7 5.7 0 0 1 16.4 18.9`, 2.8 thick with round ends and a round corner,
  and the core is a dot of radius 2.1 at 16.5 across and 13.2 down.
- **In the menu** the mark is white on a tile of the accent, 32px with a corner of 10
  (`.brand .mark`). Without a tile, the line is in the ink and the core in the accent.
- **The app wears neither yet.** Its header says the old name and its icons draw a stand-in ring,
  until the frame is turned on (#347).

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

## What is not here

- **The dark scheme.** Light only: the maintainer gives the dark scheme before the frame is
  turned on.
- **The look in print**, and a chart's own colours beside the accent. Both are parked by the
  maintainer (#9, Decisions).
- **Icons.** None is drawn: the look has no set of them yet.
- **The app's own icons.** The tab's, the Dock's and the touch icon are the mark on its tile, and
  are drawn when the frame is turned on (#347). The mark on a dark ground waits with the dark
  scheme.
- **A phone.** The pages wrap as the browser narrows, and that is all: the phone is a later
  study.
- **Every other page.** Accounts, Quarters, the Inbox, Prices and the lists are drawn
  one by one, each before it is built (#9, Order). A page not drawn yet is made of the parts
  on the sheet; a part it needs that is not on the sheet is asked for, never invented on the page.
- **Safari.** The pages were checked in Chromium. The glass is written with the
  `-webkit-backdrop-filter` Safari reads, with its values typed, and has not been looked at there.

## Changing it

A change to the look is the maintainer's. It is made in `look.css`, in the one token or the one
rule, and checked on every page. Once `house/` holds the values, the house is the source:
a value changes there and here in the same pull request, until this folder is cleared out with
the old look (#9, Order).
