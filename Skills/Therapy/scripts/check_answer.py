#!/usr/bin/env python3
"""Therapy — 한국어 답변 검사기.

코딩 에이전트가 낸 한국어 답변에서 억지 순우리말, 도메인 밖 용어(회계·행정),
직역 관용구, 번역투를 찾아낸다. 규칙은 term-map.json에 데이터로 들어 있고
이 스크립트는 그것을 적용하기만 한다.

코드 블록(``` fence)과 인라인 코드(`...`)는 검사에서 제외한다.

Usage:
    python3 check_answer.py draft.md
    cat draft.md | python3 check_answer.py -
    python3 check_answer.py draft.md --json report.json
    python3 check_answer.py draft.md --fix > fixed.md
    python3 check_answer.py --list-terms
    python3 check_answer.py draft.md --terms ~/.therapy/team-terms.json

Exit code:
    0  error 없음
    1  error 1건 이상 (warn만 있으면 0)
    2  실행 오류

Pure stdlib — no external dependencies. Python 3.10+.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")

# term-map.json을 찾는 순서. 설치본을 먼저 본다.
SEARCH_PATHS = [
    Path.home() / ".therapy" / "term-map.json",
    Path(__file__).resolve().parent.parent / "references" / "term-map.json",
]


# ----------------------------------------------------------------------------
# 자료구조
# ----------------------------------------------------------------------------
@dataclass
class Finding:
    term_id: str
    category: str
    severity: str
    line: int
    bad: str
    good: str
    note: str
    excerpt: str = ""


@dataclass
class Report:
    source: str
    chars: int
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(1 for f in self.findings if f.severity == "error")

    @property
    def warns(self) -> int:
        return sum(1 for f in self.findings if f.severity == "warn")


# ----------------------------------------------------------------------------
# 규칙 로딩
# ----------------------------------------------------------------------------
def load_terms(extra: Path | None) -> list[dict[str, Any]]:
    """기본 term-map을 읽고, 팀 파일이 있으면 같은 id를 덮어쓴다.

    팀 파일에서 severity를 "off"로 주면 해당 규칙을 끈다.
    """
    base = next((p for p in SEARCH_PATHS if p.exists()), None)
    if base is None:
        raise FileNotFoundError("term-map.json을 찾지 못했습니다. --terms로 지정하세요.")
    terms = {t["id"]: t for t in json.loads(base.read_text(encoding="utf-8"))["terms"]}
    if extra is not None:
        for t in json.loads(extra.read_text(encoding="utf-8")).get("terms", []):
            if t.get("severity") == "off":
                terms.pop(t["id"], None)
            else:
                terms[t["id"]] = t
    return list(terms.values())


# ----------------------------------------------------------------------------
# 코드 영역 처리
# ----------------------------------------------------------------------------
def code_spans(text: str) -> list[tuple[int, int]]:
    spans = [m.span() for m in FENCE_RE.finditer(text)]
    for m in INLINE_CODE_RE.finditer(text):
        if not any(s <= m.start() < e for s, e in spans):
            spans.append(m.span())
    return sorted(spans)


def mask_code(text: str) -> str:
    """코드 영역을 공백으로 바꾼다. 오프셋과 줄 번호는 유지된다."""
    chars = list(text)
    for start, end in code_spans(text):
        for i in range(start, end):
            if chars[i] != "\n":
                chars[i] = " "
    return "".join(chars)


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def excerpt_at(text: str, offset: int, width: int = 44) -> str:
    start = max(0, offset - width // 3)
    return text[start:offset + width].replace("\n", " ").strip()


# ----------------------------------------------------------------------------
# 검사
# ----------------------------------------------------------------------------
def analyze(text: str, source: str, terms: list[dict[str, Any]]) -> Report:
    masked = mask_code(text)
    report = Report(source=source, chars=len(text))
    for term in terms:
        try:
            pattern = re.compile(term["pattern"])
        except re.error as exc:
            print(f"규칙 {term['id']}의 정규식이 잘못되었습니다: {exc}", file=sys.stderr)
            continue
        for m in pattern.finditer(masked):
            report.findings.append(Finding(
                term_id=term["id"],
                category=term["category"],
                severity=term["severity"],
                line=line_of(text, m.start()),
                bad=term["bad"],
                good=term["good"],
                note=term.get("note", ""),
                excerpt=excerpt_at(text, m.start()),
            ))
    report.findings.sort(key=lambda f: (f.line, f.term_id))
    return report


# ----------------------------------------------------------------------------
# 자동 수정
# ----------------------------------------------------------------------------
def apply_fixes(text: str, terms: list[dict[str, Any]]) -> tuple[str, int]:
    """auto가 지정된 규칙만 치환한다. 코드 영역은 건드리지 않는다.

    auto == true      → good 값으로 치환
    auto == "문자열"   → 그 문자열로 치환 (빈 문자열이면 삭제)
    auto == false     → 사람이 판단해야 하므로 손대지 않는다
    """
    result, count = text, 0
    for term in terms:
        auto = term.get("auto", False)
        if auto is False:
            continue
        replacement = term["good"] if auto is True else auto
        spans = code_spans(result)
        out, last = [], 0
        for m in re.finditer(term["pattern"], result):
            if any(s <= m.start() < e for s, e in spans) or m.start() < last:
                continue
            out.append(result[last:m.start()])
            out.append(replacement)
            last = m.end()
            count += 1
        out.append(result[last:])
        result = "".join(out)
    return result, count


# ----------------------------------------------------------------------------
# 출력
# ----------------------------------------------------------------------------
def render(report: Report) -> str:
    lines = [f"# 답변 검사 — {report.source}", ""]
    if not report.findings:
        lines.append("지적 사항 없음.")
        return "\n".join(lines)

    lines.append(f"error {report.errors}건, warn {report.warns}건 ({report.chars}자)")
    lines.append("")

    by_category: dict[str, list[Finding]] = {}
    for f in report.findings:
        by_category.setdefault(f.category, []).append(f)

    for category, items in sorted(by_category.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"## {category} ({len(items)})")
        for f in items:
            mark = "ERROR" if f.severity == "error" else "WARN "
            lines.append(f"- L{f.line} [{mark}] {f.bad} → {f.good}")
            if f.note:
                lines.append(f"  {f.note}")
            lines.append(f"  인용: {f.excerpt}")
        lines.append("")

    if report.errors:
        lines.append("error는 고친 뒤 내보냅니다. --fix로 일부는 자동 치환됩니다.")
    return "\n".join(lines)


def render_terms(terms: list[dict[str, Any]]) -> str:
    lines = ["# 등록된 규칙", ""]
    by_category: dict[str, list[dict[str, Any]]] = {}
    for t in terms:
        by_category.setdefault(t["category"], []).append(t)
    for category, items in by_category.items():
        lines.append(f"## {category}")
        for t in items:
            auto = " [auto]" if t.get("auto", False) is not False else ""
            lines.append(f"- {t['bad']} → {t['good']}{auto}")
            if t.get("note"):
                lines.append(f"  {t['note']}")
        lines.append("")
    lines.append(f"총 {len(terms)}개.")
    return "\n".join(lines)


def read_input(target: str) -> tuple[str, str]:
    if target == "-":
        return sys.stdin.read(), "stdin"
    path = Path(target)
    return path.read_text(encoding="utf-8"), str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="한국어 답변 검사기")
    parser.add_argument("target", nargs="?", help="검사할 파일 경로, 또는 - (stdin)")
    parser.add_argument("--json", dest="json_out", help="결과를 JSON으로 저장")
    parser.add_argument("--terms", help="팀 규칙 JSON 경로 (기본 규칙에 덮어씀)")
    parser.add_argument("--fix", action="store_true", help="자동 수정본을 stdout으로 출력")
    parser.add_argument("--list-terms", action="store_true", help="등록된 규칙 출력")
    parser.add_argument("--quiet", action="store_true", help="종료 코드만 사용")
    args = parser.parse_args()

    try:
        terms = load_terms(Path(args.terms) if args.terms else None)
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"규칙을 읽지 못했습니다: {exc}", file=sys.stderr)
        return 2

    if args.list_terms:
        print(render_terms(terms))
        return 0

    if not args.target:
        parser.error("검사할 파일을 지정하세요. 목록만 보려면 --list-terms.")

    try:
        text, source = read_input(args.target)
    except OSError as exc:
        print(f"입력을 읽지 못했습니다: {exc}", file=sys.stderr)
        return 2

    if args.fix:
        fixed, count = apply_fixes(text, terms)
        sys.stdout.write(fixed)
        print(f"{count}건 자동 치환. 나머지는 직접 고치세요.", file=sys.stderr)
        return 0

    report = analyze(text, source, terms)

    if args.json_out:
        payload = {
            "source": report.source,
            "chars": report.chars,
            "errors": report.errors,
            "warns": report.warns,
            "findings": [asdict(f) for f in report.findings],
        }
        Path(args.json_out).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    if not args.quiet:
        print(render(report))
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
