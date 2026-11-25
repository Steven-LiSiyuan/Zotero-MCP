#!/usr/bin/env python3
"""Organize a Zotero collection tree via the Zotero Web API.

Subcommands
  plan   Read-only. Find (a) papers that exist as several Zotero items in a
         collection tree and (b) papers that are in a subcollection but not in
         the top collection. Writes a JSON plan and prints a summary.
  apply  Execute an (approved, possibly edited) plan: add items to collections,
         merge duplicates into the kept item and move the copies to Trash.
  retag  Rename a tag on every item that has it (e.g. /Useful -> #Useful).

Environment
  ZOTERO_LIBRARY_ID    required (your userID or group ID)
  ZOTERO_LIBRARY_TYPE  "user" (default) or "group"
  ZOTERO_API_KEY       defaults to "proxy-injected" (Claude Code cloud sessions
                       inject the real key via a network secret). Never commit it.

Run with:  uv run --with pyzotero scripts/organize_zotero.py <subcommand> ...
"""
import argparse
import collections
import json
import os
import re
import sys

from pyzotero import zotero

DOI_RE = re.compile(r"10\.\d{4,}/\S+", re.I)


def client():
    lib = os.environ.get("ZOTERO_LIBRARY_ID")
    if not lib:
        sys.exit("Set ZOTERO_LIBRARY_ID")
    return zotero.Zotero(lib, os.environ.get("ZOTERO_LIBRARY_TYPE", "user"),
                         os.environ.get("ZOTERO_API_KEY", "proxy-injected"))


def find_collection(z, name_or_key):
    cols = z.everything(z.collections())
    matches = [c for c in cols if c["key"] == name_or_key or c["data"]["name"] == name_or_key]
    if not matches:
        sys.exit(f"No collection named/keyed {name_or_key!r}")
    if len(matches) > 1:
        sys.exit("Ambiguous collection name; pass the key instead: "
                 + ", ".join(f"{c['key']} (parent {c['data']['parentCollection']})" for c in matches))
    return matches[0], cols


def descendants(root_key, cols):
    out, frontier = [], [root_key]
    while frontier:
        k = frontier.pop()
        kids = [c for c in cols if c["data"]["parentCollection"] == k]
        out += kids
        frontier += [c["key"] for c in kids]
    return out


def identity(d):
    doi = (d.get("DOI") or "").strip().lower()
    if not doi:
        m = DOI_RE.search(d.get("extra") or "")
        doi = m.group(0).lower() if m else ""
    title = re.sub(r"[^a-z0-9]", "", (d.get("title") or "").lower())
    return title, doi.rstrip(".")


def annotation_count(z, key):
    n = 0
    for child in z.children(key):
        if child["data"]["itemType"] == "attachment":
            n += sum(1 for a in z.children(child["key"]) if a["data"]["itemType"] == "annotation")
        elif child["data"]["itemType"] == "note":
            n += 1
    return n


def cmd_plan(args):
    z = client()
    root, cols = find_collection(z, args.collection)
    subs = descendants(root["key"], cols)
    names = {c["key"]: c["data"]["name"] for c in cols}
    tree = [root["key"]] + [c["key"] for c in subs]
    items = {}
    for k in tree:
        for it in z.everything(z.collection_items_top(k)):
            if not it["data"].get("deleted"):
                items[it["key"]] = it

    # Union-find on title / DOI to group items into papers.
    parent = {k: k for k in items}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    buckets = collections.defaultdict(list)
    for k, it in items.items():
        t, doi = identity(it["data"])
        if len(t) >= 10:  # very short titles are too ambiguous to match on
            buckets["t:" + t].append(k)
        if doi:
            buckets["d:" + doi].append(k)
    for ks in buckets.values():
        for k in ks[1:]:
            parent[find(k)] = find(ks[0])
    groups = collections.defaultdict(list)
    for k in items:
        groups[find(k)].append(k)

    plan = {"collection": root["key"], "collection_name": root["data"]["name"],
            "subcollections": {c["key"]: c["data"]["name"] for c in subs},
            "merge": [], "add_to_root": []}

    for keys in groups.values():
        cols_of = {k: set(items[k]["data"]["collections"]) for k in keys}
        union_tree = sorted({c for k in keys for c in cols_of[k] if c in tree})
        if len(keys) > 1:
            ann = {k: annotation_count(z, k) for k in keys}
            keep = sorted(keys, key=lambda k: (-ann[k], -len(cols_of[k] & set(tree)),
                                               items[k]["data"]["dateAdded"]))[0]
            target = sorted(set(union_tree) | {root["key"]})
            plan["merge"].append({
                "title": items[keep]["data"].get("title"),
                "keep": keep,
                "trash": [k for k in keys if k != keep],
                "add_collections": [c for c in target if c not in cols_of[keep]],
                "add_collection_names": [names[c] for c in target if c not in cols_of[keep]],
                "details": {k: {"annotations_and_notes": ann[k],
                                "collections": [names.get(c, c) for c in cols_of[k]],
                                "dateAdded": items[k]["data"]["dateAdded"]} for k in keys},
            })
        elif root["key"] not in cols_of[keys[0]]:
            k = keys[0]
            plan["add_to_root"].append({"item": k, "title": items[k]["data"].get("title"),
                                        "itemType": items[k]["data"]["itemType"],
                                        "in": [names[c] for c in union_tree]})

    with open(args.out, "w") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)

    print(f"Collection: {root['data']['name']} ({root['key']}), {len(subs)} subcollections")
    print(f"Zotero items in tree: {len(items)}; unique papers: {len(groups)}")
    print(f"\nPapers with several Zotero items: {len(plan['merge'])}")
    for m in plan["merge"]:
        print(f"- {m['title']}\n    keep {m['keep']}, trash {m['trash']}, add to {m['add_collection_names']}")
        for k, d in m["details"].items():
            print(f"      {k}: {d}")
    print(f"\nIn a subcollection but missing from {root['data']['name']}: {len(plan['add_to_root'])}")
    for a in plan["add_to_root"]:
        print(f"- {a['item']} [{a['itemType']}] {a['title']}  (in {a['in']})")
    print(f"\nPlan written to {args.out}")


def cmd_apply(args):
    z = client()
    plan = json.load(open(args.plan))
    root = plan["collection"]

    def add(key, col):
        d = z.item(key)["data"]
        if col in d["collections"]:
            return
        d["collections"].append(col)
        print("add", key, "->", col, z.update_item(d))

    if "add" in args.sections:
        for a in plan["add_to_root"]:
            add(a["item"], root)
    if "merge" in args.sections:
        for m in plan["merge"]:
            keep = z.item(m["keep"])["data"]
            changed = False
            for t in m["trash"]:
                other = z.item(t)["data"]
                for c in other["collections"]:  # keep every folder the copies were in
                    if c not in keep["collections"]:
                        keep["collections"].append(c); changed = True
                for tag in other["tags"]:      # and every tag
                    if tag["tag"] not in {x["tag"] for x in keep["tags"]}:
                        keep["tags"].append({"tag": tag["tag"]}); changed = True
            for c in m["add_collections"]:
                if c not in keep["collections"]:
                    keep["collections"].append(c); changed = True
            if changed:
                print("update", m["keep"], z.update_item(keep))
            for t in m["trash"]:
                d = z.item(t)["data"]
                d["deleted"] = 1  # move to Trash, restorable; never permanent delete
                print("trash", t, z.update_item(d))


def cmd_retag(args):
    z = client()
    targets = z.everything(z.items(tag=args.old))
    if args.collection:
        root, cols = find_collection(z, args.collection)
        tree = {root["key"]} | {c["key"] for c in descendants(root["key"], cols)}
        targets = [t for t in targets if set(t["data"].get("collections", [])) & tree]
    for it in targets:
        d = it["data"]
        new, seen = [], set()
        for t in d["tags"]:
            name = args.new if t["tag"] == args.old else t["tag"]
            if name not in seen:
                seen.add(name)
                new.append({"tag": name} if name == args.new else t)
        d["tags"] = new
        print(it["key"], (d.get("title") or "")[:80], z.update_item(d) if not args.dry_run else "(dry run)")
    print(f"{len(targets)} item(s) {'would be' if args.dry_run else ''} retagged {args.old!r} -> {args.new!r}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("plan"); a.add_argument("collection", help="top collection name or key")
    a.add_argument("--out", default="zotero_plan.json"); a.set_defaults(func=cmd_plan)
    a = sp.add_parser("apply"); a.add_argument("plan")
    a.add_argument("--sections", nargs="+", choices=["add", "merge"], default=["add", "merge"])
    a.set_defaults(func=cmd_apply)
    a = sp.add_parser("retag"); a.add_argument("old"); a.add_argument("new")
    a.add_argument("--collection", help="limit to this collection tree (default: whole library)")
    a.add_argument("--dry-run", action="store_true"); a.set_defaults(func=cmd_retag)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
