---
name: therapy
description: 코딩 에이전트의 한국어 답변에서 억지 순우리말(갈래·잣대·꾸러미·훑다), 회계·행정 용어(원장·대장·전표·사본), 영어 관용구 직역(은탄환·바퀴를 다시 발명), 번역투를 없애는 온보딩 스킬. 한 번 실행하면 ~/.claude/CLAUDE.md 와 ~/.codex/AGENTS.md 에 규칙 블록을 심어 이후 모든 세션에 자동 적용된다. Claude Code나 Codex를 처음 켰을 때, "에이전트 한국어가 이상하다", "말투 고치느라 시간 다 쓴다", "용어를 자꾸 이상하게 번역한다", "답변 스타일을 영구적으로 고정하고 싶다", "온보딩 세팅해줘" 같은 말이 나오면 트리거할 것. 새 장비·새 계정·새 저장소를 세팅하는 맥락에서도 먼저 제안할 것.
---

# Therapy

코딩 에이전트가 한국어로 답할 때 생기는 용어 사고를 **설치 한 번으로** 막는
스킬입니다. 스킬을 매번 부르는 방식이 아니라, 에이전트가 세션 시작마다 자동으로
읽는 지침 파일에 규칙을 심어 놓는 방식입니다.

고치려는 증상은 셋입니다. 기술 용어를 고유어로 풀어쓰는 것(갈래, 잣대, 꾸러미,
얼개, 훑다, 가르다, 재다, 알맹이, 껍데기, 들머리, 두 벌), 회계·행정 용어를
끌어오는 것(원장, 대장, 대사, 전표, 사본, 귀속, 소명, 품의, 상기, 제반),
영어 관용구를 직역하는 것(은탄환, 바퀴를 다시 발명, 낮게 매달린 과일, 여정).
여기에 번역투와 근거 없는 단정이 따라붙습니다.

## When to use

- Claude Code / Codex를 처음 설치하고 세팅하는 중
- "에이전트가 쓰는 한국어가 이상하다", "말투 고치느라 실제 작업을 못 한다"
- 새 저장소에 팀 공통 답변 규칙을 걸고 싶을 때
- 용어 사전을 팀에 맞게 고치거나, 규칙을 끄고 싶을 때
- 트리거 키워드 없이도 온보딩·초기 세팅 맥락이면 먼저 제안한다

## What it does

1. `~/.therapy/`에 규칙 데이터와 검사기를 설치한다.
2. 에이전트가 매 세션 자동으로 읽는 파일에 규칙 블록을 심는다.
   - Claude Code 전역: `~/.claude/CLAUDE.md`
   - Codex 전역: `~/.codex/AGENTS.md`
   - 프로젝트 스코프를 고르면 `<repo>/CLAUDE.md`, `<repo>/AGENTS.md`
3. 이후 세션부터 규칙이 항상 컨텍스트에 있다. 스킬을 다시 부를 필요가 없다.

블록은 마커로 감싸므로 여러 번 실행해도 중복되지 않는다. 기존 내용은 그대로
두고 뒤에 덧붙이며, 처음 수정할 때 한 번 `.bak`을 남긴다.

## Workflow

### 1. 범위를 정한다

기본은 전역(개인 장비 전체)이다. 팀 저장소에 커밋해 공유하려면 프로젝트
스코프를 함께 건다. 사용자가 명시하지 않으면 전역으로 설치하고, 프로젝트에도
걸지 물어본다.

### 2. 설치한다

```bash
python3 ~/.claude/skills/Therapy/scripts/install.py            # 전역
python3 ~/.claude/skills/Therapy/scripts/install.py --scope both --project-dir .
python3 ~/.claude/skills/Therapy/scripts/install.py --dry-run  # 계획만 확인
```

`--agent claude` 또는 `--agent codex`로 한쪽만 설치할 수 있다. 기본은 둘 다이며,
해당 디렉터리가 없으면 새로 만든다.

### 3. 확인한다

```bash
python3 ~/.therapy/check_answer.py --list-terms   # 등록된 규칙 전체
python3 ~/.claude/skills/Therapy/scripts/install.py --status
```

설치 직후에는 실행 중인 세션에 아직 반영되지 않는다. 세션을 다시 시작해야 한다.
이 점을 사용자에게 반드시 알린다.

### 4. 팀에 맞게 고친다 (선택)

`~/.therapy/team-terms.json`에서 같은 `id`로 덮어쓰거나 `severity`를
`"off"`로 주어 규칙을 끈다. 테이블 작업이 많은 팀은 `row`를, 그래프 작업이 많은
팀은 `axis`를 끄는 식이다. 새 단어를 추가할 때는 `pattern` 앞에
`(?<![가-힣])`를 붙여야 `실행`, `은행` 같은 단어 안의 글자가 걸리지 않는다.

## 답변을 내보내기 전 검사

긴 보고나 문서를 내보내기 전에 검사기를 돌린다. error가 남아 있으면 고친 뒤
보낸다.

```bash
python3 ~/.therapy/check_answer.py draft.md
cat draft.md | python3 ~/.therapy/check_answer.py -
python3 ~/.therapy/check_answer.py draft.md --fix > fixed.md
python3 ~/.therapy/check_answer.py draft.md --json report.json
```

`--fix`는 1:1 대응이 확실한 것만 치환한다(갈래→브랜치, 꾸러미→패키지,
보여집니다→보입니다, 이모지 삭제). 맥락 판단이 필요한 것은 그대로 두고
보고서에만 남긴다. 코드 블록과 인라인 코드는 검사·치환 모두에서 제외된다.

## 갱신과 제거

```bash
python3 .../scripts/install.py            # 블록이 구버전이면 자동 갱신
python3 .../scripts/install.py --uninstall
```

제거는 블록만 지우고 `~/.therapy`는 남긴다. 완전히 지우려면 그 폴더를
직접 삭제한다.

## 한계

지침 파일은 강제가 아니라 컨텍스트다. 규칙이 항상 눈에 보이게 만들어 위반을
줄이는 것이지 없애지는 못한다. 긴 세션에서는 앞쪽 지침이 흐려질 수 있으므로,
중요한 산출물은 검사기를 한 번 돌리는 편이 확실하다.

검사기는 정규식 기반이라 맥락을 모른다. `행`, `축`, `몫`, `접기`처럼 맥락에
따라 맞는 단어는 warn으로만 잡는다. error만 막고 warn은 읽어 보고 판단한다.

## 파일

- `scripts/install.py` — 지침 파일에 블록을 심고 payload를 설치한다
- `scripts/check_answer.py` — 초안 검사기 (stdlib only, Python 3.10+)
- `references/term-map.json` — 금지어와 대체어 (규칙의 단일 출처)
- `references/team-terms.json` — 팀 추가·해제용 템플릿
- `references/answer-rules.md` — 규칙의 근거와 경계 사례
