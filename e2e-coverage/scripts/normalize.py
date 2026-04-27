#!/usr/bin/env python3
"""
解析 Appium page_source (XML)，提取可交互元素，计算状态指纹。

用法:
  python normalize.py <page_source.xml>                    # 输出 JSON 到 stdout
  python normalize.py <page_source.xml> -o state.json      # 输出到文件
  echo '<xml>...</xml>' | python normalize.py -             # 从 stdin 读取
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

INTERACTIVE_TYPES = {
    "XCUIElementTypeButton",
    "XCUIElementTypeTextField",
    "XCUIElementTypeTextView",
    "XCUIElementTypeCheckBox",
    "XCUIElementTypeRadioButton",
    "XCUIElementTypePopUpButton",
    "XCUIElementTypeComboBox",
    "XCUIElementTypeSlider",
    "XCUIElementTypeLink",
    "XCUIElementTypeTab",
    "XCUIElementTypeMenuItem",
    "XCUIElementTypeMenuBarItem",
    "XCUIElementTypeIncrementor",
    "XCUIElementTypeDisclosureTriangle",
    "XCUIElementTypeSegmentedControl",
    "XCUIElementTypeOutlineRow",
    "XCUIElementTypeTableRow",
}

# Labels to always skip (empty label = no meaningful identifier)
SKIP_LABELS = {""}

# Window chrome button labels — only skipped when direct child of Window element
WINDOW_CHROME_LABELS = {"Close", "Minimize", "Zoom", "FullScreen"}

# Matches keyboard shortcuts like (⌘D), (⇧⌘N), (⌥⌘I), (⌃⇧⌘F)
SHORTCUT_RE = re.compile(r'\s*\(([⌘⇧⌥⌃]+[A-Za-z0-9])\)\s*$')
# Matches comma-separated shortcuts like ", ⇧⌘T" at end of label
SHORTCUT_COMMA_RE = re.compile(r',\s*([⌘⇧⌥⌃]+[A-Za-z0-9])\s*$')

# Types eligible for RIGHT_CLICK (likely to have context menus)
RIGHT_CLICK_TYPES = {
    "XCUIElementTypeCell",
    "XCUIElementTypeRow",
    "XCUIElementTypeStaticText",
    "XCUIElementTypeLink",
    "XCUIElementTypeImage",
    "XCUIElementTypeTextView",
    "XCUIElementTypeOutlineRow",
    "XCUIElementTypeTableRow",
}

# Types eligible for DRAG (list items, etc.)
DRAG_TYPES = {
    "XCUIElementTypeCell",
    "XCUIElementTypeRow",
    "XCUIElementTypeImage",
    "XCUIElementTypeOutlineRow",
    "XCUIElementTypeTableRow",
    "XCUIElementTypeTab",
}

TEXT_FIELD_TYPES = {
    "XCUIElementTypeTextField",
    "XCUIElementTypeTextView",
}


def get_eligible_actions(element_type: str) -> list[str]:
    """Determine eligible actions for an element based on its type."""
    if element_type in TEXT_FIELD_TYPES:
        actions = ["TYPE"]
    else:
        actions = ["CLICK"]
    if element_type in RIGHT_CLICK_TYPES:
        actions.append("RIGHT_CLICK")
    if element_type in DRAG_TYPES:
        actions.append("DRAG")
    return actions


def _is_window_chrome(elem, parent_map: dict) -> bool:
    """Check if element is a window chrome button (Close/Minimize/Zoom/FullScreen).

    Window chrome buttons are direct children of the Window element.
    """
    label = elem.attrib.get("label") or elem.attrib.get("name") or ""
    if label not in WINDOW_CHROME_LABELS:
        return False
    parent = parent_map.get(elem)
    if parent is not None and parent.tag == "XCUIElementTypeWindow":
        return True
    return False


def parse_page_source(xml_str: str) -> dict:
    root = ET.fromstring(xml_str)

    # Build parent map for ancestry checks
    parent_map = {child: parent for parent in root.iter() for child in parent}

    all_elements = []
    interactive_elements = []
    interactive_xml_refs = []  # parallel list of XML element refs
    seen_dedup = set()  # (type, label, x, y, width, height)

    for elem in root.iter():
        tag = elem.tag
        attrs = elem.attrib
        label = attrs.get("label") or attrs.get("name") or attrs.get("title") or ""
        value = attrs.get("value", "")
        enabled = attrs.get("enabled", "true")
        visible = attrs.get("visible", "true")
        x = attrs.get("x", "0")
        y = attrs.get("y", "0")
        width = attrs.get("width", "0")
        height = attrs.get("height", "0")

        el = {
            "type": tag,
            "label": label,
            "value": value,
            "enabled": enabled,
            "visible": visible,
            "x": int(x), "y": int(y),
            "width": int(width), "height": int(height),
        }
        all_elements.append(el)

        is_interactive = (
            tag in INTERACTIVE_TYPES
            and visible != "false"  # macOS popup menus report visible="" for items
            and label not in SKIP_LABELS
            and not _is_window_chrome(elem, parent_map)
            and int(y) >= 29  # 跳过菜单栏区域 (menu bar is y=0..28)
            and int(width) > 0
            and int(height) > 0
        )
        if is_interactive:
            dedup_key = (tag, label, int(x), int(y), int(width), int(height))
            if dedup_key in seen_dedup:
                continue
            seen_dedup.add(dedup_key)
            interactive_elements.append(el)
            interactive_xml_refs.append(elem)

    # Compute has_children: does this element's XML subtree contain other interactive elements?
    interactive_xml_set = set(interactive_xml_refs)
    for i, xml_elem in enumerate(interactive_xml_refs):
        has_child = any(
            desc in interactive_xml_set and desc is not xml_elem
            for desc in xml_elem.iter()
        )
        interactive_elements[i]["has_children"] = has_child

    return {
        "all_elements_count": len(all_elements),
        "interactive_elements": interactive_elements,
    }


def detect_list_groups(elements: list[dict]) -> list[list[tuple[int, dict]]]:
    """Detect groups of list-like elements based on spatial layout.

    Criteria: same type, same x (±10px via x//20 bucketing),
    consecutive y (gap ≤ 50px), ≥ 3 elements in the group.

    Returns list of groups, where each group is [(index, element), ...].
    """
    if not elements:
        return []

    # Group by (type, x bucket)
    buckets: dict[tuple[str, int], list[tuple[int, dict]]] = {}
    for i, e in enumerate(elements):
        key = (e.get("type", ""), e.get("x", 0) // 20)
        buckets.setdefault(key, []).append((i, e))

    groups = []
    for _key, items in buckets.items():
        if len(items) < 3:
            continue
        items.sort(key=lambda x: x[1].get("y", 0))

        current = [items[0]]
        for j in range(1, len(items)):
            prev_y = items[j - 1][1].get("y", 0)
            curr_y = items[j][1].get("y", 0)
            if curr_y - prev_y <= 50:
                current.append(items[j])
            else:
                if len(current) >= 3:
                    groups.append(current)
                current = [items[j]]
        if len(current) >= 3:
            groups.append(current)

    return groups


def compute_state_hash(interactive_elements: list[dict]) -> str:
    # Detect list groups and aggregate their signatures so that
    # adding/removing list items doesn't change the hash.
    groups = detect_list_groups(interactive_elements)
    list_indices: set[int] = set()
    group_sigs = []
    for group in groups:
        for i, _ in group:
            list_indices.add(i)
        etype = group[0][1]["type"]
        x_bin = group[0][1].get("x", 0) // 20
        group_sigs.append(f"{etype}|__LIST__|x{x_bin}")

    sigs = []
    for i, e in enumerate(interactive_elements):
        if i not in list_indices:
            sigs.append(f"{e['type']}|{e['label']}|{e['enabled']}")
    sigs.extend(group_sigs)
    sigs.sort()
    content = "||".join(sigs)
    return hashlib.md5(content.encode()).hexdigest()[:12]


def compute_structure_hash(interactive_elements: list[dict]) -> str:
    sigs = sorted(
        f"{e['type']}|{e['enabled']}"
        for e in interactive_elements
    )
    content = "||".join(sigs)
    return hashlib.md5(content.encode()).hexdigest()[:12]


CONTAINER_TYPES = {
    "XCUIElementTypeWindow",
    "XCUIElementTypeGroup",
    "XCUIElementTypeToolbar",
    "XCUIElementTypeTabGroup",
    "XCUIElementTypeWebView",
    "XCUIElementTypeScrollView",
    "XCUIElementTypeTable",
    "XCUIElementTypeMenu",
    "XCUIElementTypeSplitGroup",
    "XCUIElementTypeSheet",
    "XCUIElementTypePopover",
}

TAG_SHORT = {
    "XCUIElementTypeButton": "Button",
    "XCUIElementTypeTextField": "TextField",
    "XCUIElementTypeTextView": "TextArea",
    "XCUIElementTypeCheckBox": "CheckBox",
    "XCUIElementTypeRadioButton": "Radio",
    "XCUIElementTypePopUpButton": "PopUpButton",
    "XCUIElementTypeComboBox": "ComboBox",
    "XCUIElementTypeSlider": "Slider",
    "XCUIElementTypeLink": "Link",
    "XCUIElementTypeTab": "Tab",
    "XCUIElementTypeMenuItem": "MenuItem",
    "XCUIElementTypeMenuBarItem": "MenuBarItem",
    "XCUIElementTypeIncrementor": "Incrementor",
    "XCUIElementTypeDisclosureTriangle": "Disclosure",
    "XCUIElementTypeSegmentedControl": "SegmentedControl",
    "XCUIElementTypeOutlineRow": "OutlineRow",
    "XCUIElementTypeTableRow": "TableRow",
    "XCUIElementTypeWindow": "Window",
    "XCUIElementTypeGroup": "Group",
    "XCUIElementTypeToolbar": "Toolbar",
    "XCUIElementTypeTabGroup": "TabGroup",
    "XCUIElementTypeWebView": "WebView",
    "XCUIElementTypeScrollView": "ScrollView",
    "XCUIElementTypeTable": "Table",
    "XCUIElementTypeMenu": "Menu",
    "XCUIElementTypeSplitGroup": "SplitGroup",
    "XCUIElementTypeSheet": "Sheet",
    "XCUIElementTypePopover": "Popover",
    "XCUIElementTypeStaticText": "StaticText",
    "XCUIElementTypeImage": "Image",
    "XCUIElementTypeOther": "Other",
}


def build_ui_tree(xml_str: str) -> dict | None:
    """Build a simplified UI tree from page_source XML.

    Rules:
    - Only keep nodes that are interactive, meaningful containers, or ancestors of these
    - Strip coordinates, enabled, visible, value
    - Collapse chains of unlabeled Groups into a single node
    - Simplify tag names (XCUIElementTypeButton → Button)
    - Skip menu bar area (y <= 50)
    """
    root = ET.fromstring(xml_str)

    def _short_tag(tag: str) -> str:
        return TAG_SHORT.get(tag, tag.replace("XCUIElementType", ""))

    def _get_label(elem) -> str:
        attrs = elem.attrib
        return attrs.get("label") or attrs.get("name") or attrs.get("title") or ""

    def _should_skip(elem) -> bool:
        """Skip macOS menu bar leaf nodes (y <= 30), but allow containers through."""
        if elem.tag in CONTAINER_TYPES or elem.tag == "XCUIElementTypeApplication":
            return False  # Never skip containers — their children decide
        y = int(elem.attrib.get("y", "0"))
        return y <= 30

    def _is_meaningful(elem) -> bool:
        """Node is interactive, a labeled container, or has content (e.g. StaticText)."""
        tag = elem.tag
        label = _get_label(elem)
        if tag in INTERACTIVE_TYPES:
            return True
        if tag in CONTAINER_TYPES and label:
            return True
        # Keep any non-container element with a label (e.g. StaticText, Image)
        if label and tag not in CONTAINER_TYPES:
            return True
        return False

    def _build(elem) -> dict | None:
        if _should_skip(elem):
            return None

        # Recursively build children
        children = []
        for child in elem:
            node = _build(child)
            if node:
                children.append(node)

        is_meaningful = _is_meaningful(elem)

        # Prune: no children and not meaningful → drop
        if not children and not is_meaningful:
            return None

        label = _get_label(elem)
        tag = _short_tag(elem.tag)

        # Collapse: unlabeled non-interactive container with exactly 1 child → return child
        if not is_meaningful and not label and len(children) == 1:
            return children[0]

        node = {"tag": tag}
        if label:
            node["label"] = label
        if children:
            node["children"] = children
        return node

    tree = _build(root)
    return tree


def normalize(xml_str: str) -> dict:
    parsed = parse_page_source(xml_str)
    interactive = parsed["interactive_elements"]
    state_hash = compute_state_hash(interactive)
    structure_hash = compute_structure_hash(interactive)
    ui_tree = build_ui_tree(xml_str)

    shortcuts = []
    elements_out = []
    for e in interactive:
        label = e["label"]
        entry = {
            "type": e["type"],
            "label": label,
            "eligible_actions": get_eligible_actions(e["type"]),
            "x": e["x"], "y": e["y"],
            "width": e["width"], "height": e["height"],
        }
        if e.get("enabled") != "true":
            entry["enabled"] = False
        if e.get("has_children"):
            entry["has_children"] = True
        m = SHORTCUT_RE.search(label)
        if not m:
            m = SHORTCUT_COMMA_RE.search(label)
        if m:
            shortcut = m.group(1)
            clean_label = m.re.sub("", label).strip()
            shortcuts.append({
                "shortcut": shortcut,
                "label": clean_label,
                "type": e["type"],
            })
            entry["shortcut"] = shortcut
        elements_out.append(entry)

    return {
        "state_id": f"s_{state_hash[:8]}",
        "state_hash": state_hash,
        "structure_hash": structure_hash,
        "interactive_elements_count": len(interactive),
        "interactive_elements": elements_out,
        "shortcuts": shortcuts,
        "ui_tree": ui_tree,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Normalize Appium page_source XML")
    parser.add_argument("input", help="XML file path, or '-' for stdin")
    parser.add_argument("-o", "--output", help="Output JSON file path")
    args = parser.parse_args()

    if args.input == "-":
        xml_str = sys.stdin.read()
    else:
        xml_str = Path(args.input).read_text(encoding="utf-8")

    result = normalize(xml_str)

    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Saved to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
