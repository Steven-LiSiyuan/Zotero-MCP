---
name: organize-zotero
description: Organize Zotero — clean up a Zotero collection (folder) and its subcollections so every unique paper appears once in the top folder and once in each subfolder it belongs to, merge papers that exist as several Zotero items, and convert tags (e.g. native /Useful -> Ethereal-style #Useful). Use when the user asks to organize, tidy, dedupe or clean up a Zotero folder, or to convert/rename Zotero tags.
---

# Organize Zotero

Goal for a given top collection (e.g. `LLC`):
1. Every **unique paper** (not every Zotero item) is in the top collection exactly once.
2. It is in each subcollection it belongs to exactly once.
3. Papers that exist as several Zotero items (same DOI or same normalized title) are merged:
   keep one item, delete the other copies.
4. Tags are converted on request, by default native `/Useful` -> Zotero Ethereal Style `#Useful`.

## Approval rule (always)

**Ask the user to approve before adding items to any folder or deleting/trashing any item.**
Use AskUserQuestion with the concrete list of papers (titles, item keys, folders).
Tag-only changes do not move items between folders and need no approval, but report them.
Never permanently delete: trash (`deleted = 1`) so items can be restored.

## Tooling

Script: `scripts/organize_zotero.py` in this repo (needs `ZOTERO_LIBRARY_ID`;
the API key is proxy-injected in cloud sessions, or `ZOTERO_API_KEY` locally — never commit it).

```bash
uv run --with pyzotero scripts/organize_zotero.py plan "LLC" --out "$SCRATCH/plan.json"
uv run --with pyzotero scripts/organize_zotero.py retag /Useful '#Useful'
uv run --with pyzotero scripts/organize_zotero.py apply "$SCRATCH/plan.json" --sections add merge
```

Write the plan to the scratchpad, not the repo.

## Workflow

1. **Plan (read-only).** Run `plan <collection>`. It reads the whole collection tree
   (all nested subcollections), groups items into papers by DOI / normalized title, and lists:
   - `merge`: papers with several items. It keeps the item with the most annotations and notes,
     then the one in the most tree folders, then the oldest. The others are to be trashed, and
     the kept item is added to every folder the copies were in.
   - `add_to_root`: papers in a subfolder but missing from the top folder.
2. **Sanity-check the plan.** Look at near-matches and false positives yourself (e.g. similar titles
   like "Peak current-mode control" vs "Charge current control" are *different* papers).
   Check standalone attachments/documents (datasheets, app notes) aren't PDFs of a paper already present.
   Flag papers that look off-topic for the folder (e.g. laser/medical papers inside an LLC folder),
   but still propose adding them, since the rule is "every paper in a subfolder is also in the top folder".
3. **Retag.** Run `retag /Useful '#Useful'` (library-wide unless the user limits it with `--collection`).
   Use `--dry-run` first if unsure.
4. **Ask for approval** of each section separately (adds to the top folder; merges + trash), with options
   such as "all", "all except off-topic ones", "only add, don't delete", "skip".
   Remove anything the user rejected from the plan JSON before applying.
5. **Apply** with `apply plan.json --sections ...` limited to what was approved.
6. **Verify.** Re-run `plan`; it should report 0 merges and 0 missing. Tell the user the final counts,
   what went to Trash (restorable), and note that trashing a parent item also trashes its attached PDF.

## Notes

- A Zotero folder can't hold the same item twice, so "duplicates in a folder" always means
  *different items for the same paper*.
- Trashed items and trashed subcollections are ignored.
- Collection names can repeat in Zotero; pass the collection key if the script says the name is ambiguous.
