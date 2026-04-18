import json
import os
import re
import asyncio
import config
from core.logging import logger

try:
    import frontmatter as _frontmatter
except ImportError as _e:
    _frontmatter = None
    logger.warning(f"[Persona] python-frontmatter 미설치, MD 로더 비활성 — JSON fallback만 사용 ({_e})")

_persona: dict = {}
_loaded_mtime: float = 0.0
_static_prefix_cache: str | None = None
_static_prefix_mtime: float = 0.0

ACTIONS = ("idle", "perk", "droop", "tilt", "wave", "think", "cheer", "shrug", "point", "nod", "bow", "wag")
EXPRESSIVE_ACTIONS = ("wave", "cheer", "wag", "point", "nod", "bow", "perk", "droop", "shrug", "tilt", "think")
_ACTION_RE = re.compile(r"\[action:(\w+)\]")

def load_persona():
    global _persona, _loaded_mtime, _static_prefix_cache
    path = config.PERSONA_PATH
    ext = os.path.splitext(path)[1].lower()
    if ext == ".md" and _frontmatter is not None:
        post = _frontmatter.load(path)
        _persona = {**post.metadata, "system_prompt": post.content}
    else:
        if ext == ".md" and _frontmatter is None:
            logger.warning(f"[Persona] .md 지정됐지만 frontmatter 미설치, JSON 로더로 시도")
        with open(path, encoding="utf-8") as f:
            _persona = json.load(f)
    _loaded_mtime = os.path.getmtime(path)
    _static_prefix_cache = None  # invalidate on reload
    logger.info(f"[Persona] 로드 완료: {_persona.get('name')}")

async def watch_persona():
    while True:
        await asyncio.sleep(60)
        try:
            mtime = os.path.getmtime(config.PERSONA_PATH)
            if mtime != _loaded_mtime:
                load_persona()
        except Exception as e:
            logger.warning(f"[Persona] watch 오류: {e}")

_DYNAMIC_MARKER = "지금 상황:"


def _build_ctx_str(context: dict) -> str:
    ctx_str = ""
    if context.get("cwd"):
        ctx_str += f"현재 작업 디렉토리: {context['cwd']}. "
    if context.get("last_command"):
        ctx_str += f"마지막 실행 명령어: {context['last_command']}"
        if context.get("last_exit_code") is not None:
            status = "성공" if context["last_exit_code"] == 0 else f"실패(exit {context['last_exit_code']})"
            ctx_str += f" ({status}). "
    if context.get("claude_task"):
        ctx_str += f"Claude Code 작업: {context['claude_task']}. "
    if not ctx_str:
        ctx_str = "특별한 상황 없음."
    return ctx_str


def _split_template() -> tuple[str, str]:
    """Split persona system_prompt into (prefix_before_marker, suffix_with_marker)."""
    template = _persona.get("system_prompt", "너는 {name}이야.")
    idx = template.find(_DYNAMIC_MARKER)
    if idx < 0:
        # No marker → entire template is static prefix; dynamic suffix is empty
        return template, ""
    prefix = template[:idx].rstrip()
    suffix = template[idx:]
    return prefix, suffix


def build_static_prefix() -> str:
    """Static part of system prompt (name/personality/speech_style only). Cached across turns."""
    global _static_prefix_cache, _static_prefix_mtime
    if _static_prefix_cache is not None and _static_prefix_mtime == _loaded_mtime:
        return _static_prefix_cache
    prefix_template, _ = _split_template()
    try:
        rendered = prefix_template.format(
            name=_persona.get("name", "뉴끼"),
            personality=_persona.get("personality", ""),
            speech_style=_persona.get("speech_style", ""),
        )
    except KeyError as e:
        logger.warning(f"[Persona] static prefix format 실패 (missing key {e}), raw 반환")
        rendered = prefix_template
    _static_prefix_cache = rendered
    _static_prefix_mtime = _loaded_mtime
    return rendered


def build_dynamic_suffix(context: dict, recent_memory: str = "") -> str:
    """Dynamic part — {context}/{recent_memory} 주입. 매 턴 새로 생성."""
    ctx_str = _build_ctx_str(context)
    mem_str = recent_memory if recent_memory else "(없음)"
    _, suffix_template = _split_template()
    if not suffix_template:
        # Template had no marker — emit minimal context block
        return f"{_DYNAMIC_MARKER} {ctx_str}\n\n최근 기억:\n{mem_str}\n"
    try:
        return suffix_template.format(context=ctx_str, recent_memory=mem_str)
    except KeyError:
        try:
            rendered = suffix_template.format(context=ctx_str)
        except Exception as e:
            logger.warning(f"[Persona] dynamic suffix format 실패: {e}")
            rendered = suffix_template
        return rendered + f"\n\n최근 기억:\n{mem_str}\n"


def build_system_prompt(context: dict, recent_memory: str = "") -> str:
    """Backward-compat wrapper. Returns static prefix + dynamic suffix combined."""
    return build_static_prefix() + "\n\n" + build_dynamic_suffix(context, recent_memory)

def get_persona() -> dict:
    return _persona

def classify_emotion(text: str) -> tuple[str, float]:
    t = text.lower()
    if any(k in t for k in ["에러", "실패", "오류", "걱정", "힘들"]): return "worried", 0.8
    if any(k in t for k in ["완료", "성공", "잘했", "수고", "축하"]): return "happy", 0.9
    if any(k in t for k in ["음", "글쎄", "생각", "?", "왜"]): return "thinking", 0.7
    if any(k in t for k in ["놀랍", "신기", "와", "헐"]): return "surprised", 0.8
    return "idle", 0.5


def extract_action(text: str) -> tuple[str, str | None]:
    """LLM 응답에서 [action:xxx] 태그 제거 + 액션명 반환. 없으면 emotion→action fallback."""
    m = _ACTION_RE.search(text)
    if m:
        name = m.group(1)
        cleaned = _ACTION_RE.sub("", text, count=1).lstrip()
        if name in ACTIONS:
            return cleaned, name
        return cleaned, None
    emotion, _ = classify_emotion(text)
    fallback = {"happy": "wag", "worried": "droop", "thinking": "think",
                "surprised": "perk", "idle": "idle"}.get(emotion)
    return text, fallback


class ActionTagStripper:
    """스트림 청크에서 선두 [action:xxx] 태그를 제거. 첫 태그만 처리."""
    def __init__(self):
        self._buf = ""
        self._done = False
        self.action: str | None = None

    def feed(self, chunk: str) -> str:
        if self._done:
            return chunk
        self._buf += chunk
        stripped = self._buf.lstrip()
        if not stripped:
            return ""
        if not stripped.startswith("["):
            self._done = True
            out, self._buf = self._buf, ""
            return out
        m = _ACTION_RE.match(stripped)
        if m:
            self._done = True
            name = m.group(1)
            if name in ACTIONS:
                self.action = name
            tail = stripped[m.end():]
            self._buf = ""
            return tail
        if len(self._buf) > 40:
            self._done = True
            out, self._buf = self._buf, ""
            return out
        return ""

    def flush(self) -> str:
        if self._done:
            return ""
        self._done = True
        out, self._buf = self._buf, ""
        return out
