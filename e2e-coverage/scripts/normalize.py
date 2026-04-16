#!/usr/bin/env python3
"""
解析 Appium page_source (XML)，提取可交互元素，计算状态指纹。

用法:
  python normalize.py <page_source.xml>                    # 输出 JSON 到 stdout
  python normalize.py <page_source.xml> -o state.json      # 输出到文件
  echo '<xml>...</xml>' | python normalize.py -             # 从 stdin 读取
"""

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

SKIP_LABELS = {"Close", "Minimize", "Zoom", "FullScreen", ""}

# Matches keyboard shortcuts like (⌘D), (⇧⌘N), (⌥⌘I), (⌃⇧⌘F)
SHORTCUT_RE = re.compile(r'\s*\(([⌘⇧⌥⌃]+[A-Za-z0-9])\)\s*$')

# Types eligible for RIGHT_CLICK (likely to have context menus)
RIGHT_CLICK_TYPES = {
    "XCUIElementTypeCell",
    "XCUIElementTypeRow",
    "XCUIElementTypeStaticText",
    "XCUIElementTypeLink",
    "XCUIElementTypeImage",
    "XCUIElementTypeTextView",
    "XCUIElementTypeButton",
    "XCUIElementTypeTab",
    "XCUIElementTypeOutlineRow",
    "XCUIElementTypeTableRow",
}

# Types eligible for DRAG (list items, tabs, etc.)
DRAG_TYPES = {
    "XCUIElementTypeCell",
    "XCUIElementTypeRow",
    "XCUIElementTypeTab",
    "XCUIElementTypeImage",
    "XCUIElementTypeOutlineRow",
    "XCUIElementTypeTableRow",
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


def parse_page_source(xml_str: str) -> dict:
    root = ET.fromstring(xml_str)

    all_elements = []
    interactive_elements = []

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
            and enabled == "true"
            and visible != "false"  # macOS popup menus report visible="" for items
            and label not in SKIP_LABELS
            and int(y) > 50  # 跳过菜单栏区域
            and int(width) > 0
            and int(height) > 0
        )
        if is_interactive:
            interactive_elements.append(el)

    return {
        "all_elements_count": len(all_elements),
        "interactive_elements": interactive_elements,
    }


def compute_state_hash(interactive_elements: list[dict]) -> str:
    sigs = sorted(
        f"{e['type']}|{e['label']}|{e['enabled']}"
        for e in interactive_elements
    )
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
        """Node is interactive or a labeled container."""
        tag = elem.tag
        label = _get_label(elem)
        if tag in INTERACTIVE_TYPES:
            return True
        if tag in CONTAINER_TYPES and label:
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
        m = SHORTCUT_RE.search(label)
        if m:
            shortcut = m.group(1)
            clean_label = SHORTCUT_RE.sub("", label).strip()
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
