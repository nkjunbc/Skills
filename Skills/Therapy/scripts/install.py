#!/usr/bin/env python3
"""Therapy — 온보딩 설치기.

코딩 에이전트가 매 세션 자동으로 읽는 지침 파일에 답변 규율 블록을 써 넣는다.
한 번 실행하면 이후 모든 세션에 적용된다. 스킬을 다시 부를 필요가 없다.

대상 파일:
    Claude Code  전역  ~/.claude/CLAUDE.md      (세션 시작마다 로드)
    Claude Code  프로젝트  <repo>/CLAUDE.md      (git으로 팀 공유)
    Codex        전역  ~/.codex/AGENTS.md        (실행마다 로드)
    Codex        프로젝트  <repo>/AGENTS.md

블록은 마커로 감싸므로 여러 번 실행해도 중복되지 않는다. 기존 내용은 건드리지
않고, 처음 수정할 때 한 번 .bak을 남긴다.

Usage:
    python3 install.py                          # 전역, 감지된 에이전트 전부
    python3 install.py --scope both             # 전역 + 현재 프로젝트
    python3 install.py --agent claude           # Claude Code만
    python3 install.py --project-dir ~/work/api
    python3 install.py --status                 # 설치 상태만 출력
    python3 install.py --dry-run
    python3 install.py --uninstall

Exit code:
    0  정상
    1  대상 파일을 하나도 찾지 못함
    2  실행 오류

Pure stdlib — no external dependencies. Python 3.10+.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

VERSION = 1
BEGIN = "<!-- BEGIN therapy -->"
END = "<!-- END therapy -->"
BLOCK_RE = re.compile(
    re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", re.DOTALL
)

# 설치 후 규칙과 검사기가 사는 곳. 스킬 폴더를 옮기거나 지워도 살아남는다.
PAYLOAD_DIR = Path.home() / ".therapy"

# ----------------------------------------------------------------------------
# 주입할 블록
# ----------------------------------------------------------------------------
# 지침 파일은 매 세션 컨텍스트에 들어간다. 길면 준수율이 떨어지므로 짧게 유지하고
# 자세한 규칙은 payload 파일로 미룬다.

BLOCK = f"""{BEGIN}
<!-- therapy v{VERSION} · install.py가 관리합니다. 직접 고치지 마세요. -->
## 한국어 답변 규율

설명·보고·요약에 항상 적용한다. 코드, 커밋 메시지, 로그 자체는 제외한다.

**1. 기술 용어를 고유어로 풀어쓰지 않는다 (가장 중요).**
한국 개발자가 실제로 쓰는 표기를 그대로 쓴다.
갈래→브랜치 · 잣대→기준/지표 · 꾸러미→패키지 · 얼개→구조 · 훑다→스캔/순회 ·
가르다→분할 · 재다→측정 · 알맹이→페이로드 · 껍데기→래퍼 · 꼬리표→태그 ·
들머리→진입점 · 갈무리→저장. 두 벌/한 벌 대신 "2개".
맥락이 맞으면 허용: 행(테이블), 축(그래프), 몫(나눗셈), 접기(UI collapse).

**2. 회계·행정·법률 용어를 끌어오지 않는다.**
원장→로그/레코드 · 대장→목록/레지스트리 · 대사→대조 · 전표→레코드 ·
사본→복사본 · 귀속→할당 · 소명→설명 · 품의→요청 · 상기/하기/금번/익일/제반 금지.

**3. 영어 관용구를 직역하지 않는다.**
은탄환, 바퀴를 다시 발명, 방 안의 코끼리, 낮게 매달린 과일, 한 입 크기,
무거운 짐을 들어올리다, 여정 — 쓰지 않는다.

**4. 번역투를 쓰지 않는다.**
"~을 가집니다"→"~입니다" · "보여집니다"→"보입니다" · "되어집니다"→"됩니다" ·
"~할 필요가 있습니다"→"~해야 합니다" · "~에 대하여"→주어를 바로 쓴다 ·
"진행하였습니다"→구체 동사. "성공적으로/완벽하게/문제없이", 이모지, 강조 부사 금지.

**5. 근거와 확신도.**
코드베이스에 대한 진술에는 `경로:줄`이나 실행한 명령을 붙인다. "일반적으로"로
이 저장소의 사실을 대체하지 않는다. 확인함/추정/모름 중 하나로 말하고,
테스트를 돌리지 않았으면 "동작합니다"라고 쓰지 않는다.

긴 답변은 내보내기 전에 검사한다:
`python3 ~/.therapy/check_answer.py <파일>` — error가 남으면 고친 뒤 보낸다.
전체 규칙 `~/.therapy/answer-rules.md` · 팀 추가어 `~/.therapy/team-terms.json`
{END}
"""


# ----------------------------------------------------------------------------
# 대상 파일
# ----------------------------------------------------------------------------
@dataclass
class Target:
    agent: str          # claude | codex
    scope: str          # global | project
    path: Path
    detected: bool      # 해당 에이전트를 쓰고 있다는 흔적이 있는가


def discover(scope: str, agent: str, project_dir: Path) -> list[Target]:
    home = Path.home()
    candidates = [
        Target("claude", "global", home / ".claude" / "CLAUDE.md", (home / ".claude").is_dir()),
        Target("codex", "global", home / ".codex" / "AGENTS.md", (home / ".codex").is_dir()),
        Target("claude", "project", project_dir / "CLAUDE.md", project_dir.is_dir()),
        Target("codex", "project", project_dir / "AGENTS.md", project_dir.is_dir()),
    ]
    scopes = {"global", "project"} if scope == "both" else {scope}
    agents = {"claude", "codex"} if agent == "both" else {agent}
    return [t for t in candidates if t.scope in scopes and t.agent in agents]


def installed_version(text: str) -> int | None:
    if BEGIN not in text:
        return None
    m = re.search(r"therapy v(\d+)", text)
    return int(m.group(1)) if m else 0


# ----------------------------------------------------------------------------
# 파일 조작
# ----------------------------------------------------------------------------
def upsert(path: Path, dry_run: bool) -> str:
    """블록을 넣거나 갱신한다. 반환값은 사람이 읽을 동작 이름."""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    current = installed_version(text)

    if current is None:
        new_text = (text.rstrip() + "\n\n" + BLOCK) if text.strip() else BLOCK
        action = "설치"
    else:
        new_text = BLOCK_RE.sub(BLOCK, text)
        if new_text == text:
            return f"변경 없음 (v{current})"
        action = f"갱신 (v{current} → v{VERSION})"

    if dry_run:
        return action + " 예정"

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not path.with_suffix(path.suffix + ".bak").exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    path.write_text(new_text, encoding="utf-8")
    return action


def remove(path: Path, dry_run: bool) -> str:
    if not path.exists():
        return "파일 없음"
    text = path.read_text(encoding="utf-8")
    if BEGIN not in text:
        return "설치되어 있지 않음"
    if dry_run:
        return "제거 예정"
    path.write_text(BLOCK_RE.sub("", text).rstrip() + "\n", encoding="utf-8")
    return "제거"


def install_payload(skill_dir: Path, dry_run: bool) -> list[str]:
    """규칙 데이터와 검사기를 홈 디렉터리로 복사한다.

    team-terms.json은 팀이 채우는 파일이라 이미 있으면 덮어쓰지 않는다.
    """
    items = [
        (skill_dir / "references" / "term-map.json", PAYLOAD_DIR / "term-map.json", True),
        (skill_dir / "references" / "answer-rules.md", PAYLOAD_DIR / "answer-rules.md", True),
        (skill_dir / "scripts" / "check_answer.py", PAYLOAD_DIR / "check_answer.py", True),
        (skill_dir / "references" / "team-terms.json", PAYLOAD_DIR / "team-terms.json", False),
    ]
    notes = []
    for src, dst, overwrite in items:
        if not src.exists():
            notes.append(f"원본 없음: {src}")
            continue
        if dst.exists() and not overwrite:
            notes.append(f"유지: {dst.name} (기존 파일 보존)")
            continue
        if dry_run:
            notes.append(f"복사 예정: {dst}")
            continue
        PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        notes.append(f"복사: {dst}")
    return notes


# ----------------------------------------------------------------------------
# 출력
# ----------------------------------------------------------------------------
def render(title: str, rows: list[tuple[Target, str]], notes: list[str]) -> str:
    lines = [f"# {title}", ""]
    for target, result in rows:
        mark = "" if target.detected else "  (미감지 — 디렉터리가 없어 새로 만듭니다)"
        lines.append(f"- {target.agent} / {target.scope} — {target.path}")
        lines.append(f"  {result}{mark}")
    if notes:
        lines.append("")
        lines.append("## payload")
        lines.extend(f"- {n}" for n in notes)
    return "\n".join(lines)


def status(targets: list[Target]) -> str:
    lines = ["# therapy 설치 상태", ""]
    for t in targets:
        if not t.path.exists():
            state = "파일 없음"
        else:
            v = installed_version(t.path.read_text(encoding="utf-8"))
            state = "설치되지 않음" if v is None else f"v{v} 설치됨"
        lines.append(f"- {t.agent} / {t.scope} — {t.path}: {state}")
    lines.append("")
    payload = "있음" if (PAYLOAD_DIR / "check_answer.py").exists() else "없음"
    lines.append(f"payload({PAYLOAD_DIR}): {payload}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="답변 규율 온보딩 설치기")
    parser.add_argument("--scope", choices=["global", "project", "both"], default="global")
    parser.add_argument("--agent", choices=["claude", "codex", "both"], default="both")
    parser.add_argument("--project-dir", default=".", help="프로젝트 스코프 기준 디렉터리")
    parser.add_argument("--skill-dir", default=None, help="스킬 폴더 경로 (기본: 이 스크립트의 상위)")
    parser.add_argument("--status", action="store_true", help="설치 상태만 출력")
    parser.add_argument("--dry-run", action="store_true", help="쓰지 않고 계획만 출력")
    parser.add_argument("--uninstall", action="store_true", help="블록 제거")
    args = parser.parse_args()

    skill_dir = Path(args.skill_dir) if args.skill_dir else Path(__file__).resolve().parent.parent
    project_dir = Path(args.project_dir).resolve()

    try:
        targets = discover(args.scope, args.agent, project_dir)
    except OSError as exc:
        print(f"대상을 찾지 못했습니다: {exc}", file=sys.stderr)
        return 2

    if not targets:
        print("대상 파일이 없습니다. --scope / --agent 조합을 확인하세요.", file=sys.stderr)
        return 1

    if args.status:
        print(status(targets))
        return 0

    if args.uninstall:
        rows = [(t, remove(t.path, args.dry_run)) for t in targets]
        print(render("therapy 제거", rows, []))
        print("\npayload는 남겨 둡니다. 완전히 지우려면 ~/.therapy 폴더를 삭제하세요.")
        return 0

    notes = install_payload(skill_dir, args.dry_run)
    rows = [(t, upsert(t.path, args.dry_run)) for t in targets]
    print(render("therapy 설치", rows, notes))
    if not args.dry_run:
        print("\n다음 세션부터 적용됩니다. 실행 중인 세션은 다시 시작하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
