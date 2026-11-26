---
name: design-card
description: "Coordinator: posts a feature's design card, with its mock page, on the feature's issue: two cards a week at most, and one open at a time."
---

# The design card

- **A design card asks a feature's shape.** The coordinator posts it on the issue of the line
  under Design next in the Queue, or of a feature at the top of Next: above the fold, at most 150
  words and three questions.
- **A card also asks which release builds the feature**, as one of its three questions: the one
  it stands in, or the next milestone to open. Its slices take the release answered (the skill `slice-a-feature`),
  so a feature put first for design is not left last to build.
- **Two cards a week, at most.** When Design next is empty the coordinator fills it itself, with
  the first feature that has no decided shape, lowest milestone first and in the order its
  milestone's description gives. It posts a card when none stands unanswered and fewer than two
  went up in the last seven days.
- **One card is open at a time, and one feature is being built.** The rest wait as lines: a
  feature's slices are written only when no other feature's slices stand open under Next. A card
  unanswered is listed in the next gate review, and meanwhile the runs work what is ready.

The card cites `docs/content-map.md` by its numbers.

## The card

Posted on the feature's issue, which takes `decision`. Above the fold, within the rule's limit:

- the outcome in one line;
- three options, each a different idea of the feature and not one idea at three sizes, each with
  its cost (slices, figures that move, a migration or none) and the jobs whose home it moves, by
  the map's numbers, or "no job moves";
- a link to a mock page;
- a recommendation;
- its questions, written as the skill `ask-or-decide` says.

The evidence is folded under `<details>`.

## The mock page

It shows today's page and each option, on the demo's names. It is a private page published with
the Artifact tool and touches no code. A run that cannot publish without stopping to ask gives
words and a picture of today's page instead, and says so. The card links the page, and the run's
end line names it after `Page:`, as the skill `beat` gives it, so the maintainer's project can
copy it in.
