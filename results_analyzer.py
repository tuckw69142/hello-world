#!/usr/bin/env python3
"""Analyze MPC results.xml test results."""

from __future__ import annotations

import argparse
import sys
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass
class TestResult:
    name: str
    status: str
    details: str | None = None


STATUS_ORDER = ["passed", "failed", "skipped", "unknown"]


def strip_namespace(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def iter_test_elements(root: ET.Element) -> Iterable[ET.Element]:
    for elem in root.iter():
        tag = strip_namespace(elem.tag).lower()
        if tag in {"test", "testcase", "test-case", "test_case"} or tag.endswith("testcase"):
            yield elem


def first_text(elem: ET.Element, *names: str) -> Optional[str]:
    for name in names:
        child = elem.find(name)
        if child is not None and child.text:
            return child.text.strip()
    return None


def normalize_status(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = value.strip().lower()
    if value in {"pass", "passed", "success", "succeeded", "ok"}:
        return "passed"
    if value in {"fail", "failed", "failure", "error"}:
        return "failed"
    if value in {"skip", "skipped", "ignored", "notrun", "not-run"}:
        return "skipped"
    return None


def derive_status(elem: ET.Element) -> str:
    for key in ("result", "status", "outcome", "verdict"):
        status = normalize_status(elem.attrib.get(key))
        if status:
            return status
    for key in ("result", "status", "outcome", "verdict"):
        status = normalize_status(first_text(elem, key))
        if status:
            return status
    if elem.find("failure") is not None or elem.find("error") is not None:
        return "failed"
    if elem.find("skipped") is not None:
        return "skipped"
    return "unknown"


def derive_name(elem: ET.Element) -> str:
    for key in ("name", "id", "test", "case", "title"):
        value = elem.attrib.get(key)
        if value:
            return value.strip()
    name = first_text(elem, "name", "testname", "title")
    if name:
        return name
    return strip_namespace(elem.tag)


def derive_details(elem: ET.Element) -> Optional[str]:
    for tag in ("failure", "error", "message", "details"):
        child = elem.find(tag)
        if child is not None:
            if child.text:
                return child.text.strip()
            if child.attrib:
                return ", ".join(f"{k}={v}" for k, v in child.attrib.items())
    for key in ("message", "details", "reason"):
        value = elem.attrib.get(key)
        if value:
            return value.strip()
    return None


def analyze_results(path: Path) -> list[TestResult]:
    tree = ET.parse(path)
    root = tree.getroot()
    tests = []
    for elem in iter_test_elements(root):
        tests.append(
            TestResult(
                name=derive_name(elem),
                status=derive_status(elem),
                details=derive_details(elem),
            )
        )
    return tests


def format_summary(results: list[TestResult]) -> str:
    counts = {status: 0 for status in STATUS_ORDER}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    lines = ["Summary:"]
    for status in STATUS_ORDER:
        lines.append(f"  {status.title():<7}: {counts.get(status, 0)}")
    return "\n".join(lines)


def format_results(results: list[TestResult]) -> str:
    lines = []
    for result in results:
        line = f"- {result.name}: {result.status}"
        if result.details:
            wrapped = textwrap.fill(result.details, width=76, subsequent_indent="    ")
            line = f"{line}\n    {wrapped}"
        lines.append(line)
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze MPC results.xml test results.")
    parser.add_argument(
        "path",
        nargs="?",
        default="results.xml",
        help="Path to results.xml (default: results.xml)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = Path(args.path)
    if not path.exists():
        print(f"Error: {path} not found.", file=sys.stderr)
        return 2
    results = analyze_results(path)
    if not results:
        print("No test results found in the XML document.")
        return 1
    print(format_summary(results))
    print("\nDetails:")
    print(format_results(results))
    return 1 if any(r.status == "failed" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
