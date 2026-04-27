#!/usr/bin/env python3
"""
Stateless exploration advisor — analyzes crawler state and recommends next actions.

Called by Claude (LLM) at checkpoints during UI exploration. Does NOT execute any
actions itself — it only reads state, computes what's unexplored, and returns
recommendations as JSON.

Commands:
  init       Create initial exploration state from a page_source XML file.
  next       Return the next batch of elements to explore.
  record     Record the result of an action (transition + new state if any).
  skip       Mark a single element as skipped (with reason, stored separately).
  status     Show exploration progress summary.
  supplement Record a supplemental action into utg.json (post-finalization).

Usage:
  # 1. Initialize with first page_source
  python3 advisor.py init --page-source ps.xml --app-name Calculator --output-dir e2e_output

  # 2. Ask what to explore next
  python3 advisor.py next --output-dir e2e_output

  # 3. Record action result
  python3 advisor.py record --output-dir e2e_output \\
    --from-state s_abc123 --action "CLICK(Settings)" --page-source new_ps.xml

  # 4. Skip a single out-of-scope element (with reason)
  python3 advisor.py skip --output-dir e2e_output \\
    --state s_abc123 --effective-key "NTP Link" --reason "NTP element, out of Copilot scope"

  # 5. Check progress
  python3 advisor.py status --output-dir e2e_output
"""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

from normalize import normalize, detect_list_groups


# ── State persistence ──────────────────────────────────────────


def load_state(output_dir: Path) -> dict:
    """Load crawler_state.json (lightweight progress data only)."""
    path = output_dir / "crawler_state.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(output_dir: Path, state: dict):
    """Save crawler_state.json (lightweight progress data only)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "crawler_state.json"
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def load_blacklist(output_dir: Path) -> list[str]:
    """Load blacklist from e2e_output/blacklist.json."""
    path = output_dir / "blacklist.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def save_blacklist(output_dir: Path, blacklist: list[str]):
    """Save blacklist to e2e_output/blacklist.json."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "blacklist.json"
    path.write_text(json.dumps(blacklist, ensure_ascii=False, indent=2), encoding="utf-8")


def append_shortcuts_raw(output_dir: Path, shortcuts: list[dict], source_state: str):
    """Append discovered shortcuts to shortcuts_raw.json."""
    if not shortcuts:
        return
    path = output_dir / "shortcuts_raw.json"
    existing = []
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
    for sc in shortcuts:
        existing.append({**sc, "source_state": source_state})
    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")


def load_state_detail(output_dir: Path, state_id: str) -> dict:
    """Load per-state detail from states/<state_id>.json."""
    path = output_dir / "states" / f"{state_id}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state_detail(output_dir: Path, state_id: str, detail: dict):
    """Save per-state detail to states/<state_id>.json."""
    states_dir = output_dir / "states"
    states_dir.mkdir(parents=True, exist_ok=True)
    path = states_dir / f"{state_id}.json"
    path.write_text(json.dumps(detail, indent=2, ensure_ascii=False), encoding="utf-8")


def save_utg(output_dir: Path, state: dict):
    """Export lightweight utg.json from crawler state."""
    elapsed = time.time() - state.get("start_time", time.time())

    # Build lightweight states summary (no element details)
    states_summary = {}
    for sid in state.get("state_index", []):
        detail = load_state_detail(output_dir, sid)
        states_summary[sid] = {
            "window_title": detail.get("window_title", ""),
            "interactive_elements_count": detail.get("interactive_elements_count", 0),
            "screenshot": detail.get("screenshot", f"states/{sid}.png"),
        }

    # Deduplicate transitions for edges
    seen_edges = set()
    edges = []
    for t in state.get("transitions", []):
        key = (t["from"], t["to"])
        if key not in seen_edges:
            seen_edges.add(key)
            edges.append([t["from"], t["to"]])

    utg = {
        "app_name": state.get("app_name", "App"),
        "start_state": state.get("start_state"),
        "states": states_summary,
        "transitions": state.get("transitions", []),
        "edges": edges,
        "shortcuts": [],
        "stats": {
            "total_states": len(state.get("state_index", [])),
            "total_transitions": len(state.get("transitions", [])),
            "total_actions": state.get("action_count", 0),
            "explored_pairs": len(state.get("explored_pairs", [])),
            "elapsed_seconds": round(elapsed),
        },
    }
    path = output_dir / "utg.json"
    path.write_text(json.dumps(utg, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Key computation ────────────────────────────────────────────


def element_key(el: dict) -> str:
    return el.get("label", "unknown")


def element_key_with_coords(el: dict) -> str:
    label = el.get("label", "unknown")
    x, y = el.get("x", 0), el.get("y", 0)
    return f"{label}@({x},{y})"


def get_effective_key(el: dict, all_elements: list[dict]) -> str:
    k = element_key(el)
    count = sum(1 for e in all_elements if element_key(e) == k)
    if count > 1:
        return element_key_with_coords(el)
    return k


def _is_blacklisted(label: str, blacklist: list[str]) -> bool:
    """Check if an element label matches any global blacklist entry (substring match)."""
    for bl in blacklist:
        if bl in label:
            return True
    return False


def _get_list_skip_keys(elements: list[dict]) -> set[str]:
    """Return effective_keys of non-representative list group members.

    For each list group, keep only the first container (has_children=True)
    and the first leaf (has_children=False) as representatives.
    All other members' keys are returned for skipping.
    """
    groups = detect_list_groups(elements)
    if not groups:
        return set()

    label_counts: dict[str, int] = {}
    for e in elements:
        k = element_key(e)
        label_counts[k] = label_counts.get(k, 0) + 1

    skip_keys: set[str] = set()
    for group in groups:
        containers = [(i, e) for i, e in group if e.get("has_children", False)]
        leaves = [(i, e) for i, e in group if not e.get("has_children", False)]

        rep_indices: set[int] = set()
        if containers:
            rep_indices.add(containers[0][0])
        if leaves:
            rep_indices.add(leaves[0][0])

        for i, e in group:
            if i not in rep_indices:
                k = element_key(e)
                if label_counts[k] > 1:
                    k = element_key_with_coords(e)
                skip_keys.add(k)

    return skip_keys


def _get_all_known_keys(state: dict, exclude_state: str, output_dir: Path) -> set[str]:
    """Collect all element keys from all states except exclude_state."""
    all_keys: set[str] = set()
    for sid in state.get("state_index", []):
        if sid == exclude_state:
            continue
        detail = load_state_detail(output_dir, sid)
        if not detail:
            continue
        els = detail.get("interactive_elements", [])
        for el in els:
            k = element_key(el)
            count = sum(1 for e2 in els if element_key(e2) == k)
            if count > 1:
                all_keys.add(element_key_with_coords(el))
            else:
                all_keys.add(k)
    return all_keys


def get_unexplored(state: dict, state_id: str, output_dir: Path) -> list[tuple[dict, str, bool]]:
    """Return unexplored (element, action_type, is_native) triples for a given state.

    Returns a list of (element_dict, action_type, is_native) tuples, sorted by:
    1. Native elements first (elements unique to this state)
    2. Then by action priority: CLICK/TYPE first, then RIGHT_CLICK, then DRAG.
    Elements matching the global blacklist or non-representative list members
    are excluded.
    """
    ACTION_PRIORITY = {"CLICK": 0, "TYPE": 0, "RIGHT_CLICK": 1, "DRAG": 2}

    detail = load_state_detail(output_dir, state_id)
    if not detail:
        return []

    elements = detail.get("interactive_elements", [])
    explored = set(tuple(p) for p in state.get("explored_pairs", []))
    blacklist = load_blacklist(output_dir)
    list_skip_keys = _get_list_skip_keys(elements)

    # Compute which keys exist in other states (for native detection)
    all_other_keys = _get_all_known_keys(state, state_id, output_dir)

    # Check for duplicate labels
    label_counts: dict[str, int] = {}
    for el in elements:
        k = element_key(el)
        label_counts[k] = label_counts.get(k, 0) + 1

    unexplored = []
    for el in elements:
        label = el.get("label", "")
        if _is_blacklisted(label, blacklist):
            continue
        if el.get("enabled") is False:
            continue
        k = element_key(el)
        if label_counts[k] > 1:
            k = element_key_with_coords(el)
        if k in list_skip_keys:
            continue
        is_native = k not in all_other_keys
        for action_type in el.get("eligible_actions", ["CLICK"]):
            if (state_id, k, action_type) not in explored:
                unexplored.append((el, action_type, is_native))

    # Sort: native first, then by action priority
    unexplored.sort(key=lambda x: (0 if x[2] else 1, ACTION_PRIORITY.get(x[1], 99)))
    return unexplored


# ── Commands ───────────────────────────────────────────────────


def cmd_init(args):
    """Initialize exploration with the first page_source."""
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "states").mkdir(exist_ok=True)

    xml_str = Path(args.page_source).read_text(encoding="utf-8")
    info = normalize(xml_str)

    s0_id = info["state_id"]
    title = args.app_name

    # Save per-state detail file
    save_state_detail(output_dir, s0_id, {
        "state_id": s0_id,
        "state_hash": info["state_hash"],
        "window_title": title,
        "interactive_elements": info["interactive_elements"],
        "interactive_elements_count": info["interactive_elements_count"],
        "ui_tree": info.get("ui_tree"),
        "screenshot": f"states/{s0_id}.png",
    })

    # Append any discovered shortcuts to raw file
    append_shortcuts_raw(output_dir, info.get("shortcuts", []), s0_id)

    # Save lightweight crawler state
    state = {
        "app_name": args.app_name,
        "start_time": time.time(),
        "start_state": s0_id,
        "state_index": [s0_id],
        "state_hashes": {s0_id: info["state_hash"]},
        "state_titles": {s0_id: title},
        "transitions": [],
        "explored_pairs": [],
        "path_from_s0": {s0_id: []},
        "queue": [s0_id],
        "unreachable": [],
        "action_count": 0,
        "restore_failures": {},
    }

    save_state(output_dir, state)

    result = {
        "status": "initialized",
        "start_state": s0_id,
        "interactive_elements_count": info["interactive_elements_count"],
        "interactive_elements": info["interactive_elements"],
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_next(args):
    """Determine the next exploration target."""
    output_dir = Path(args.output_dir)
    state = load_state(output_dir)
    if not state:
        print(json.dumps({"status": "error", "message": "No crawler state found. Run 'init' first."}))
        return

    max_actions = args.max_actions
    max_states = args.max_states

    # Check limits
    if state["action_count"] >= max_actions:
        save_utg(output_dir, state)
        print(json.dumps({
            "status": "done",
            "reason": f"Reached max actions ({max_actions})",
        }))
        return

    if len(state["state_index"]) >= max_states:
        save_utg(output_dir, state)
        print(json.dumps({
            "status": "done",
            "reason": f"Reached max states ({max_states})",
        }))
        return

    # Find state with most unexplored elements
    best_id = None
    best_count = -1
    best_unexplored = []

    queue = list(state.get("queue", []))
    unreachable = set(state.get("unreachable", []))

    new_queue = []
    for sid in queue:
        if sid in unreachable:
            continue
        unexplored = get_unexplored(state, sid, output_dir)
        if not unexplored:
            continue
        new_queue.append(sid)
        if len(unexplored) > best_count:
            best_count = len(unexplored)
            best_id = sid
            best_unexplored = unexplored

    state["queue"] = new_queue
    save_state(output_dir, state)

    if not best_id:
        save_utg(output_dir, state)
        print(json.dumps({
            "status": "done",
            "reason": "All reachable states fully explored",
        }))
        return

    detail = load_state_detail(output_dir, best_id)
    path = state.get("path_from_s0", {}).get(best_id, [])

    # Build elements list with action_type from unexplored pairs
    elements_with_actions = []
    for el, action_type, is_native in best_unexplored:
        label = el.get("label", "")
        ek = get_effective_key(el, detail.get("interactive_elements", []))

        entry = {
            "label": label,
            "type": el.get("type", ""),
            "action_type": action_type,
            "effective_key": ek,
            "x": el.get("x", 0),
            "y": el.get("y", 0),
            "width": el.get("width", 0),
            "height": el.get("height", 0),
            "is_native": is_native,
        }
        # If effective_key differs from label, need coordinate-based action
        if ek != label:
            entry["use_coordinates"] = True
            entry["tap_x"] = el.get("x", 0) + el.get("width", 0) // 2
            entry["tap_y"] = el.get("y", 0) + el.get("height", 0) // 2

        elements_with_actions.append(entry)

    # Apply batch size limit
    batch_size = args.batch_size
    total_elements_count = len(elements_with_actions)
    if batch_size > 0 and len(elements_with_actions) > batch_size:
        elements_with_actions = elements_with_actions[:batch_size]

    result = {
        "status": "continue",
        "target_state": best_id,
        "target_hash": detail.get("state_hash"),
        "window_title": detail.get("window_title", ""),
        "batch_size": len(elements_with_actions),
        "total_elements": detail.get("interactive_elements_count", 0),
        "navigate_path": path,
        "elements": elements_with_actions,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_record(args):
    """Record the result of an executed action."""
    output_dir = Path(args.output_dir)
    state = load_state(output_dir)
    if not state:
        print(json.dumps({"status": "error", "message": "No crawler state found."}))
        return

    from_state = args.from_state
    action = args.action
    effective_key = args.effective_key

    # Normalize new page source
    xml_str = Path(args.page_source).read_text(encoding="utf-8")
    info = normalize(xml_str)
    new_hash = info["state_hash"]
    new_id = info["state_id"]

    state["action_count"] = state.get("action_count", 0) + 1

    # Determine outcome
    from_hash = state.get("state_hashes", {}).get(from_state)

    existing_id = None
    for sid, h in state.get("state_hashes", {}).items():
        if h == new_hash:
            existing_id = sid
            break

    outcome = {}
    if new_hash == from_hash:
        # Same state
        state["transitions"].append({"from": from_state, "to": from_state, "action": action})
        outcome = {"result": "same_state", "state_id": from_state}
    elif existing_id:
        # Known state
        state["transitions"].append({"from": from_state, "to": existing_id, "action": action})
        outcome = {"result": "known_state", "state_id": existing_id}
    else:
        # New state!
        # Deduplicate title — append triggering action if title already used
        title = f"State {new_id}"

        # Save per-state detail file
        save_state_detail(output_dir, new_id, {
            "state_id": new_id,
            "state_hash": new_hash,
            "window_title": title,
            "interactive_elements": info["interactive_elements"],
            "interactive_elements_count": info["interactive_elements_count"],
            "ui_tree": info.get("ui_tree"),
            "screenshot": f"states/{new_id}.png",
        })

        # Append any discovered shortcuts to raw file
        append_shortcuts_raw(output_dir, info.get("shortcuts", []), new_id)

        # Update lightweight state index
        state.setdefault("state_index", []).append(new_id)
        state.setdefault("state_hashes", {})[new_id] = new_hash
        state.setdefault("state_titles", {})[new_id] = title

        state["transitions"].append({"from": from_state, "to": new_id, "action": action})

        # Record path from S0
        parent_path = state.get("path_from_s0", {}).get(from_state, [])
        step = {"action": action, "label": args.label or "", "from_state": from_state}
        if args.tap_x is not None and args.tap_y is not None:
            step["action"] = f"TAP({args.tap_x},{args.tap_y})"
            step["x"] = args.tap_x
            step["y"] = args.tap_y
        state.setdefault("path_from_s0", {})[new_id] = parent_path + [step]

        # Add to queue (unless out-of-scope or too deep)
        new_depth = len(parent_path) + 1
        max_depth = getattr(args, "max_depth", 6) or 6
        out_of_scope = getattr(args, "out_of_scope", False)
        too_deep = new_depth > max_depth

        if out_of_scope:
            oos = state.setdefault("out_of_scope_states", [])
            if new_id not in oos:
                oos.append(new_id)
        elif too_deep:
            deep = state.setdefault("depth_limited_states", [])
            if new_id not in deep:
                deep.append(new_id)
        else:
            if new_id not in state.get("queue", []):
                state.setdefault("queue", []).append(new_id)

        outcome = {
            "result": "new_state",
            "state_id": new_id,
            "depth": new_depth,
            "out_of_scope": out_of_scope,
            "depth_limited": too_deep,
            "interactive_elements_count": info["interactive_elements_count"],
            "interactive_elements": info["interactive_elements"],
            "screenshot_path": f"states/{new_id}.png",
        }

        # ── Aggressive dedup: only keep truly new elements ──────
        # For each element in the new state, check if it already exists
        # in ANY previously discovered state. If so, mark it as explored
        # in the new state. Only elements appearing for the first time
        # across all states remain unexplored.
        if not out_of_scope and not too_deep:
            new_elements = info["interactive_elements"]
            new_keys = set()
            for el in new_elements:
                k = element_key(el)
                count = sum(1 for e2 in new_elements if element_key(e2) == k)
                if count > 1:
                    new_keys.add(element_key_with_coords(el))
                else:
                    new_keys.add(k)

            # Collect all element keys from all OTHER states
            all_existing_keys: set[str] = set()
            for sid in state.get("state_index", []):
                if sid == new_id:
                    continue
                existing_detail = load_state_detail(output_dir, sid)
                if not existing_detail:
                    continue
                existing_els = existing_detail.get("interactive_elements", [])
                for el in existing_els:
                    k = element_key(el)
                    count = sum(1 for e2 in existing_els if element_key(e2) == k)
                    if count > 1:
                        all_existing_keys.add(element_key_with_coords(el))
                    else:
                        all_existing_keys.add(k)

            # Mark shared elements as explored in the new state
            shared_keys = new_keys & all_existing_keys
            inherited = 0
            if shared_keys:
                explored_pairs = state.get("explored_pairs", [])
                explored_set = set(tuple(p) for p in explored_pairs)
                for el in new_elements:
                    k = element_key(el)
                    count = sum(1 for e2 in new_elements if element_key(e2) == k)
                    if count > 1:
                        k = element_key_with_coords(el)
                    if k in shared_keys:
                        for act in el.get("eligible_actions", ["CLICK"]):
                            new_pair = (new_id, k, act)
                            if new_pair not in explored_set:
                                explored_pairs.append(list(new_pair))
                                explored_set.add(new_pair)
                                inherited += 1
                state["explored_pairs"] = explored_pairs

            truly_new = new_keys - all_existing_keys
            outcome["inherited_explored"] = inherited
            outcome["truly_new_elements"] = len(truly_new)

    # Mark explored (triple: state_id, effective_key, action_type)
    explored_pairs = state.get("explored_pairs", [])
    action_type = getattr(args, "action_type", "CLICK") or "CLICK"
    triple = [from_state, effective_key, action_type]
    if triple not in explored_pairs:
        explored_pairs.append(triple)
    state["explored_pairs"] = explored_pairs

    save_state(output_dir, state)

    result = {
        "status": "recorded",
        "action_count": state["action_count"],
        **outcome,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_record_restore_failure(args):
    """Record that restoring to a state failed."""
    output_dir = Path(args.output_dir)
    state = load_state(output_dir)
    if not state:
        print(json.dumps({"status": "error", "message": "No crawler state found."}))
        return

    target = args.target_state
    failures = state.get("restore_failures", {})
    count = failures.get(target, 0) + 1
    failures[target] = count
    state["restore_failures"] = failures

    max_failures = args.max_failures

    if count >= max_failures:
        unreachable = state.get("unreachable", [])
        if target not in unreachable:
            unreachable.append(target)
        state["unreachable"] = unreachable
        queue = state.get("queue", [])
        if target in queue:
            queue.remove(target)
        state["queue"] = queue

    save_state(output_dir, state)

    result = {
        "status": "recorded",
        "target_state": target,
        "failure_count": count,
        "marked_unreachable": count >= max_failures,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_skip(args):
    """Mark a single element as skipped (out of feature scope).

    Skipped elements are stored separately from explored elements so they can
    be audited later by a validation step or evaluator agent.
    """
    output_dir = Path(args.output_dir)
    state = load_state(output_dir)
    if not state:
        print(json.dumps({"status": "error", "message": "No crawler state found."}))
        return

    state_id = args.state
    key = args.effective_key
    reason = args.reason
    action_type = getattr(args, "action_type", "CLICK") or "CLICK"

    # Store in skipped_pairs (separate from explored_pairs)
    skipped_pairs = state.get("skipped_pairs", [])
    entry = [state_id, key, action_type, reason]

    # Also add to explored_pairs so cmd_next won't recommend it again
    explored_pairs = state.get("explored_pairs", [])
    triple = [state_id, key, action_type]

    already_skipped = any(s == state_id and k == key and a == action_type for s, k, a, *_ in skipped_pairs)
    if already_skipped:
        print(json.dumps({
            "status": "already_skipped",
            "state": state_id,
            "key": key,
            "action_type": action_type,
            "message": f"Element '{key}' ({action_type}) in state '{state_id}' was already skipped.",
        }))
        return

    skipped_pairs.append(entry)
    if triple not in explored_pairs:
        explored_pairs.append(triple)

    state["skipped_pairs"] = skipped_pairs
    state["explored_pairs"] = explored_pairs

    save_state(output_dir, state)

    result = {
        "status": "skipped",
        "state": state_id,
        "key": key,
        "reason": reason,
        "total_skipped": len(skipped_pairs),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_unskip(args):
    """Reverse a skip — remove element from skipped_pairs and explored_pairs.

    Used by the Evaluator (Phase 1.5) when it determines a skipped element
    should have been explored. After unskip, the advisor's `next` command
    will recommend this element again.
    """
    output_dir = Path(args.output_dir)
    state = load_state(output_dir)
    if not state:
        print(json.dumps({"status": "error", "message": "No crawler state found."}))
        return

    state_id = args.state
    key = args.effective_key
    action_type = getattr(args, "action_type", None)

    # Remove from skipped_pairs
    skipped_pairs = state.get("skipped_pairs", [])
    if action_type:
        new_skipped = [e for e in skipped_pairs if not (e[0] == state_id and e[1] == key and e[2] == action_type)]
    else:
        # No action_type specified: remove all action types for this element
        new_skipped = [e for e in skipped_pairs if not (e[0] == state_id and e[1] == key)]
    removed = len(skipped_pairs) - len(new_skipped)

    # Remove from explored_pairs
    explored_pairs = state.get("explored_pairs", [])
    if action_type:
        new_explored = [p for p in explored_pairs if not (p[0] == state_id and p[1] == key and p[2] == action_type)]
    else:
        new_explored = [p for p in explored_pairs if not (p[0] == state_id and p[1] == key)]

    state["skipped_pairs"] = new_skipped
    state["explored_pairs"] = new_explored

    # Ensure the state is back in queue so `next` will visit it
    queue = state.get("queue", [])
    if state_id not in queue:
        queue.append(state_id)
    state["queue"] = queue

    save_state(output_dir, state)

    result = {
        "status": "unskipped" if removed > 0 else "not_found",
        "state": state_id,
        "key": key,
        "remaining_skipped": len(new_skipped),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_blacklist(args):
    """Add labels to global blacklist (stored in blacklist.json).

    Blacklisted elements are filtered out from all states (current and future)
    in get_unexplored() and _summary(). Uses substring matching.
    """
    output_dir = Path(args.output_dir)

    new_labels = [l.strip() for l in args.labels.split(",") if l.strip()]
    blacklist = load_blacklist(output_dir)

    added = []
    for label in new_labels:
        if label not in blacklist:
            blacklist.append(label)
            added.append(label)

    save_blacklist(output_dir, blacklist)

    result = {
        "status": "updated",
        "added": added,
        "total_blacklisted": len(blacklist),
        "global_blacklist": blacklist,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_status(args):
    """Show exploration progress."""
    output_dir = Path(args.output_dir)
    state = load_state(output_dir)
    if not state:
        print(json.dumps({"status": "error", "message": "No crawler state found."}))
        return

    print(json.dumps({"status": "ok", **_summary(state, output_dir)}, indent=2, ensure_ascii=False))


def cmd_verify_state(args):
    """Verify that the current page_source matches the expected target state.

    Compares the hash of the provided page_source against the stored hash of
    the target state. Returns match=true if they match, or match=false with
    information about what state was actually found.
    """
    output_dir = Path(args.output_dir)
    state = load_state(output_dir)
    if not state:
        print(json.dumps({"status": "error", "message": "No crawler state found."}))
        return

    target_state = args.target_state

    # Get the expected hash for the target state
    target_hash = state.get("state_hashes", {}).get(target_state)
    if not target_hash:
        print(json.dumps({
            "status": "error",
            "message": f"Unknown target state: {target_state}",
        }))
        return

    # Normalize current page_source and compute hash
    xml_str = Path(args.page_source).read_text(encoding="utf-8")
    info = normalize(xml_str)
    actual_hash = info["state_hash"]

    if actual_hash == target_hash:
        print(json.dumps({
            "match": True,
            "state_id": target_state,
        }))
        return

    # Not a match — check if it's a known state
    actual_state_id = None
    for sid, h in state.get("state_hashes", {}).items():
        if h == actual_hash:
            actual_state_id = sid
            break

    actual_title = ""
    if actual_state_id:
        actual_title = state.get("state_titles", {}).get(actual_state_id, "")

    print(json.dumps({
        "match": False,
        "expected_state": target_state,
        "expected_title": state.get("state_titles", {}).get(target_state, ""),
        "actual_state": actual_state_id,
        "actual_title": actual_title,
        "known": actual_state_id is not None,
    }))


def cmd_rename_state(args):
    """Rename a state's title in crawler_state.json and its detail file."""
    output_dir = Path(args.output_dir)
    state = load_state(output_dir)
    state_id = args.state
    titles = state.get("state_titles", {})
    if state_id not in titles:
        print(json.dumps({"error": f"State {state_id} not found in state_titles"}))
        return
    old_title = titles[state_id]
    titles[state_id] = args.title
    save_state(output_dir, state)

    # Also update the per-state detail file
    detail_path = output_dir / "states" / f"{state_id}.json"
    if detail_path.exists():
        detail = json.loads(detail_path.read_text(encoding="utf-8"))
        detail["window_title"] = args.title
        detail_path.write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"renamed": state_id, "old_title": old_title, "new_title": args.title}))


def cmd_supplement(args):
    """Record a supplemental action result directly into utg.json.

    Used after exploration is done (advisor status=done) to add new transitions
    (e.g., drag operations) without resetting the exploration state.
    """
    output_dir = Path(args.output_dir)
    utg_path = output_dir / "utg.json"

    if not utg_path.exists():
        print(json.dumps({"status": "error", "message": "utg.json not found. Run finalize first."}))
        return

    utg = json.loads(utg_path.read_text(encoding="utf-8"))
    from_state = args.from_state
    action = args.action

    # Validate from_state exists in utg
    if from_state not in utg.get("states", {}):
        print(json.dumps({"status": "error", "message": f"State {from_state} not found in utg.json"}))
        return

    # Build hash→id mapping from state detail files
    hash_to_id = {}
    for sid in utg["states"]:
        detail = load_state_detail(output_dir, sid)
        if detail:
            hash_to_id[detail.get("state_hash", "")] = sid

    # Get from_state's hash
    from_detail = load_state_detail(output_dir, from_state)
    from_hash = from_detail.get("state_hash", "")

    # Normalize the new page source
    xml_str = Path(args.page_source).read_text(encoding="utf-8")
    info = normalize(xml_str)
    new_hash = info["state_hash"]
    new_id = info["state_id"]

    # Determine outcome
    if new_hash == from_hash:
        # Same state — no visible change
        utg["transitions"].append({"from": from_state, "to": from_state, "action": action})
        outcome = {"result": "same_state", "state_id": from_state}

    elif new_hash in hash_to_id:
        # Known state
        existing_id = hash_to_id[new_hash]
        utg["transitions"].append({"from": from_state, "to": existing_id, "action": action})
        # Add edge if new
        edge_pair = [from_state, existing_id]
        if edge_pair not in utg.get("edges", []):
            utg.setdefault("edges", []).append(edge_pair)
        outcome = {"result": "known_state", "state_id": existing_id}

    else:
        # New state
        title = info.get("ui_tree", {}).get("label", "") or f"State {new_id}"
        save_state_detail(output_dir, new_id, {
            "state_id": new_id,
            "state_hash": new_hash,
            "window_title": title,
            "interactive_elements": info["interactive_elements"],
            "interactive_elements_count": info["interactive_elements_count"],
            "ui_tree": info.get("ui_tree"),
            "screenshot": f"states/{new_id}.png",
        })
        utg["states"][new_id] = {
            "window_title": title,
            "interactive_elements_count": info["interactive_elements_count"],
            "screenshot": f"states/{new_id}.png",
            "title": title,
        }
        utg["transitions"].append({"from": from_state, "to": new_id, "action": action})
        utg.setdefault("edges", []).append([from_state, new_id])
        # Save any shortcuts discovered
        if info.get("shortcuts"):
            append_shortcuts_raw(output_dir, info["shortcuts"], new_id)
        outcome = {"result": "new_state", "state_id": new_id}

    # Update stats
    stats = utg.get("stats", {})
    stats["total_states"] = len(utg.get("states", {}))
    stats["total_transitions"] = len(utg.get("transitions", []))
    stats["total_actions"] = stats.get("total_actions", 0) + 1
    utg["stats"] = stats

    # Save utg.json
    utg_path.write_text(json.dumps(utg, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "status": "recorded",
        "from_state": from_state,
        "action": action,
        **outcome,
    }, indent=2, ensure_ascii=False))


def cmd_finalize(args):
    """Generate utg.json from current state."""
    output_dir = Path(args.output_dir)
    state = load_state(output_dir)
    if not state:
        print(json.dumps({"status": "error", "message": "No crawler state found."}))
        return

    save_utg(output_dir, state)
    print(json.dumps({
        "status": "finalized",
        "utg_path": str(output_dir / "utg.json"),
        **_summary(state, output_dir),
    }))


# ── Helpers ────────────────────────────────────────────────────


def _summary(state: dict, output_dir: Path) -> dict:
    """Compute exploration progress summary."""
    state_index = state.get("state_index", [])
    explored = set(tuple(p) for p in state.get("explored_pairs", []))
    oos = set(state.get("out_of_scope_states", []))
    depth_limited = set(state.get("depth_limited_states", []))

    total_unexplored = 0
    total_native_unexplored = 0
    total_action_slots = 0
    per_state = {}
    blacklist = load_blacklist(output_dir)

    for sid in state_index:
        if sid in oos or sid in depth_limited:
            continue  # Don't count out-of-scope or depth-limited states
        detail = load_state_detail(output_dir, sid)
        elements = detail.get("interactive_elements", [])
        list_skip_keys = _get_list_skip_keys(elements)

        # Compute which keys exist in other states
        all_other_keys = _get_all_known_keys(state, sid, output_dir)

        # Check for duplicate labels
        label_counts: dict[str, int] = {}
        for el in elements:
            k = element_key(el)
            label_counts[k] = label_counts.get(k, 0) + 1

        unexplored = 0
        native_unexplored = 0
        state_slots = 0
        for el in elements:
            label = el.get("label", "")
            if _is_blacklisted(label, blacklist):
                continue
            if el.get("enabled") is False:
                continue
            k = element_key(el)
            if label_counts[k] > 1:
                k = element_key_with_coords(el)
            if k in list_skip_keys:
                continue
            is_native = k not in all_other_keys
            for action_type in el.get("eligible_actions", ["CLICK"]):
                state_slots += 1
                if (sid, k, action_type) not in explored:
                    unexplored += 1
                    if is_native:
                        native_unexplored += 1

        total_action_slots += state_slots
        total_unexplored += unexplored
        total_native_unexplored += native_unexplored
        if unexplored > 0:
            per_state[sid] = {
                "window_title": detail.get("window_title", ""),
                "unexplored": unexplored,
                "native_unexplored": native_unexplored,
                "total": state_slots,
            }

    explored_count = total_action_slots - total_unexplored
    coverage = (explored_count / total_action_slots * 100) if total_action_slots > 0 else 0

    return {
        "states_discovered": len(state_index),
        "total_actions": state.get("action_count", 0),
        "total_action_slots": total_action_slots,
        "explored_action_slots": explored_count,
        "unexplored_action_slots": total_unexplored,
        "native_unexplored_slots": total_native_unexplored,
        "skipped_elements": len(state.get("skipped_pairs", [])),
        "coverage_pct": round(coverage, 1),
        "unreachable_states": len(state.get("unreachable", [])),
        "out_of_scope_states": len(state.get("out_of_scope_states", [])),
        "depth_limited_states": len(state.get("depth_limited_states", [])),
        "states_with_unexplored": per_state,
    }


# ── CLI ────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Stateless exploration advisor")
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="Initialize exploration state")
    p_init.add_argument("--page-source", required=True, help="Path to initial page_source XML file")
    p_init.add_argument("--app-name", required=True, help="App display name")
    p_init.add_argument("--output-dir", default="e2e_output", help="Output directory")

    # next
    p_next = sub.add_parser("next", help="Get next exploration target")
    p_next.add_argument("--output-dir", default="e2e_output", help="Output directory")
    p_next.add_argument("--max-actions", type=int, default=500, help="Max total actions")
    p_next.add_argument("--max-states", type=int, default=50, help="Max states to discover")
    p_next.add_argument("--batch-size", type=int, default=10, help="Max elements to return per batch (0 = unlimited)")

    # record
    p_rec = sub.add_parser("record", help="Record action result")
    p_rec.add_argument("--output-dir", default="e2e_output", help="Output directory")
    p_rec.add_argument("--from-state", required=True, help="State ID where action was executed")
    p_rec.add_argument("--action", required=True, help="Action description, e.g. CLICK(Settings)")
    p_rec.add_argument("--effective-key", required=True, help="Element effective key for tracking")
    p_rec.add_argument("--page-source", required=True, help="Path to resulting page_source XML file")
    p_rec.add_argument("--label", default="", help="Element label")
    p_rec.add_argument("--tap-x", type=int, default=None, help="Tap X coordinate (if coordinate-based)")
    p_rec.add_argument("--tap-y", type=int, default=None, help="Tap Y coordinate (if coordinate-based)")
    p_rec.add_argument("--out-of-scope", action="store_true", default=False,
                       help="Record transition but don't explore the new state (out of feature scope)")
    p_rec.add_argument("--action-type", default="CLICK",
                       help="Action type: CLICK, TYPE, RIGHT_CLICK, DRAG (default: CLICK)")
    p_rec.add_argument("--max-depth", type=int, default=6,
                       help="Max exploration depth from start state (default: 6)")

    # restore-failure
    p_rf = sub.add_parser("restore-failure", help="Record a restore failure")
    p_rf.add_argument("--output-dir", default="e2e_output", help="Output directory")
    p_rf.add_argument("--target-state", required=True, help="State that couldn't be restored")
    p_rf.add_argument("--max-failures", type=int, default=3, help="Max failures before unreachable")

    # skip
    p_skip = sub.add_parser("skip", help="Mark a single element as skipped (out of scope) with reason")
    p_skip.add_argument("--output-dir", default="e2e_output", help="Output directory")
    p_skip.add_argument("--state", required=True, help="State ID containing the element")
    p_skip.add_argument("--effective-key", required=True, help="Effective key of the element to skip")
    p_skip.add_argument("--reason", required=True, help="Why this element is being skipped")
    p_skip.add_argument("--action-type", default="CLICK",
                       help="Action type: CLICK, TYPE, RIGHT_CLICK, DRAG (default: CLICK)")

    # unskip
    p_unskip = sub.add_parser("unskip", help="Reverse a skip — re-enable element for exploration")
    p_unskip.add_argument("--output-dir", default="e2e_output", help="Output directory")
    p_unskip.add_argument("--state", required=True, help="State ID containing the element")
    p_unskip.add_argument("--effective-key", required=True, help="Effective key of the element to unskip")
    p_unskip.add_argument("--action-type", default=None,
                         help="Action type to unskip. If omitted, unskips all action types for this element.")

    # blacklist
    p_bl = sub.add_parser("blacklist", help="Add labels to global blacklist (applies to all states)")
    p_bl.add_argument("--output-dir", default="e2e_output", help="Output directory")
    p_bl.add_argument("--labels", required=True,
                     help="Comma-separated labels to blacklist. Uses substring matching.")

    # status
    p_stat = sub.add_parser("status", help="Show exploration progress")
    p_stat.add_argument("--output-dir", default="e2e_output", help="Output directory")

    # verify-state
    p_vs = sub.add_parser("verify-state", help="Verify current page matches expected state")
    p_vs.add_argument("--output-dir", default="e2e_output", help="Output directory")
    p_vs.add_argument("--target-state", required=True, help="Expected state ID")
    p_vs.add_argument("--page-source", required=True, help="Path to current page_source XML file")

    # finalize
    p_fin = sub.add_parser("finalize", help="Generate utg.json from current state")
    p_fin.add_argument("--output-dir", default="e2e_output", help="Output directory")

    p_rename = sub.add_parser("rename-state", help="Rename a state's title")
    p_rename.add_argument("--output-dir", default="e2e_output", help="Output directory")
    p_rename.add_argument("--state", required=True, help="State ID to rename")
    p_rename.add_argument("--title", required=True, help="New descriptive title")

    # supplement
    p_sup = sub.add_parser("supplement", help="Record supplemental action into utg.json (post-finalization)")
    p_sup.add_argument("--output-dir", default="e2e_output", help="Output directory")
    p_sup.add_argument("--from-state", required=True, help="State ID where action was executed")
    p_sup.add_argument("--action", required=True, help="Action description, e.g. DRAG(Tab1→Tab2)")
    p_sup.add_argument("--page-source", required=True, help="Path to resulting page_source XML file")
    p_sup.add_argument("--label", default="", help="Element label")

    args = parser.parse_args()

    handlers = {
        "init": cmd_init,
        "next": cmd_next,
        "record": cmd_record,
        "restore-failure": cmd_record_restore_failure,
        "skip": cmd_skip,
        "unskip": cmd_unskip,
        "blacklist": cmd_blacklist,
        "status": cmd_status,
        "verify-state": cmd_verify_state,
        "finalize": cmd_finalize,
        "rename-state": cmd_rename_state,
        "supplement": cmd_supplement,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
