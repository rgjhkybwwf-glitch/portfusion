---
name: change-a-word
description: "Any session: renames a word of the agreed nomenclature, a column heading included, everywhere it is held, in one commit (docs/glossary.md, Changing a word)."
---

# Changing a word

The rule is in [`docs/glossary.md`](../../../docs/glossary.md), Changing a word: a word changes in
the glossary and in its declaration in the same commit.

1. **Its declaration**: a column heading in `src/portfusion/house/headings.py`; any other word
   where §8 of the glossary says its list is declared.
2. **The glossary**: the word in its section, §5 for what a reader is shown.
3. **The retired word**: a heading that is retired joins `RETIRED_HEADINGS` in
   `src/portfusion/tests/test_figures.py`, so it cannot come back.
4. **The changelog**: a line under Unreleased in `CHANGELOG.md`.
5. **§9 and the store's table regenerated**: the command writes the glossary's §9 and
   [`docs/store.md`](../../../docs/store.md)'s table of the columns, What a column may hold:

   ```bash
   python3 tools/glossary.py --write
   ```

6. **The guard**: `python3 -m pytest`.
