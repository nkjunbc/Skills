# Skills

코딩 에이전트(Claude Code, Codex)용 스킬 모음.

## Therapy

에이전트의 한국어 답변에서 억지 순우리말(갈래·잣대·꾸러미·훑다), 회계·행정
용어(원장·대장·전표·사본), 영어 관용구 직역(은탄환·바퀴를 다시 발명), 번역투를
없앤다. 한 번 설치하면 에이전트가 세션마다 자동으로 읽는 지침 파일에 규칙이
남아 이후 모든 세션에 적용된다.

```bash
git clone https://github.com/nkjunbc/Skills.git
python3 Skills/Therapy/scripts/install.py
```

Claude Code에서 스킬로 쓰려면 폴더를 스킬 경로에 둔다.

```bash
cp -r Skills/Therapy ~/.claude/skills/Therapy        # 개인 전역
cp -r Skills/Therapy <repo>/.claude/skills/Therapy   # 저장소 공유
```

자세한 내용은 [Therapy/SKILL.md](Therapy/SKILL.md)를 참고한다.

## 구조

각 스킬은 독립 폴더이며 다음을 포함한다.

- `SKILL.md` — 에이전트가 읽는 지침, frontmatter의 `description`이 트리거를 결정
- `CREATION_PROMPT.md` — 이 스킬을 만들 때 쓴 프롬프트
- `scripts/` — 실행 스크립트 (stdlib only, Python 3.10+)
- `references/` — 필요할 때 읽는 데이터와 문서
