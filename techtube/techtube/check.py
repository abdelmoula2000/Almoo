"""Pre-publish check against YouTube's monetization policies (inauthentic/reused content,
spam & misleading metadata, licensing). Writes check.md (in Arabic) for the creator."""

from __future__ import annotations

import difflib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .llm import LLMError, Ollama
from .meta import STOP, keywords, load_assets
from .script import Script, load_script
from .util import Project

OK, WARN, FAIL = "✅", "⚠️", "❌"

RISKY = re.compile(
    r"\b(regedit|reg (add|delete)|bcdedit|diskpart|format [a-z]:|del /[sfq]|rm -rf|"
    r"registry|bios|uefi|factory reset|reset this pc|delete (all|your)|wipe|"
    r"disable (windows )?defender|disable antivirus|overclock|flash(ing)? firmware)\b",
    re.I,
)
CLICKBAIT = re.compile(
    r"(100%|guaranteed|nobody tells you|they don'?t want you|secret hack|insane|"
    r"instantly|in 1 second|!!+|\bfree money\b)", re.I)


@dataclass
class Report:
    items: list[tuple[str, str, str]] = field(default_factory=list)   # (status, title, detail)

    def add(self, status: str, title: str, detail: str = "") -> None:
        self.items.append((status, title, detail))

    @property
    def fails(self) -> int:
        return sum(1 for s, _, _ in self.items if s == FAIL)

    @property
    def warns(self) -> int:
        return sum(1 for s, _, _ in self.items if s == WARN)


# ------------------------------------------------------------- similarity

def _tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9']+", text.lower()) if w not in STOP]


def shingles(text: str, n: int = 3) -> set[tuple[str, ...]]:
    t = re.findall(r"[a-z0-9']+", text.lower())
    return {tuple(t[i:i + n]) for i in range(max(len(t) - n + 1, 0))}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def cosine(a: str, b: str) -> float:
    ca, cb = Counter(_tokens(a)), Counter(_tokens(b))
    dot = sum(ca[k] * cb[k] for k in ca.keys() & cb.keys())
    na = math.sqrt(sum(v * v for v in ca.values()))
    nb = math.sqrt(sum(v * v for v in cb.values()))
    return dot / (na * nb) if na and nb else 0.0


def other_projects(project: Project) -> list[Project]:
    root = project.dir.parent
    out = []
    for d in sorted(root.iterdir()) if root.exists() else []:
        if d.is_dir() and d != project.dir and (d / "script.md").exists():
            out.append(Project(d))
    out.sort(key=lambda p: p.read_info().get("created", ""))
    return out


# ------------------------------------------------------------- checks

def check_originality(project: Project, script: Script, rep: Report) -> None:
    mine_sh = shingles(script.narration)
    worst_j, worst_c, worst_name = 0.0, 0.0, ""
    for other in other_projects(project):
        try:
            o = load_script(other.script)
        except Exception:
            continue
        j = jaccard(mine_sh, shingles(o.narration))
        c = cosine(script.narration, o.narration)
        if j > worst_j:
            worst_j, worst_name = j, other.name
        worst_c = max(worst_c, c)
    if worst_j > 0.25:
        rep.add(FAIL, "النص قريب جداً من فيديو سابق",
                f"تطابق بالجمل {worst_j:.0%} مع «{worst_name}». يوتيوب يعتبر هذا محتوى مكرراً. "
                "أعد كتابة الفيديو بزاوية مختلفة.")
    elif worst_j > 0.12:
        rep.add(WARN, "يوجد تشابه في الصياغة مع فيديو سابق",
                f"تطابق {worst_j:.0%} مع «{worst_name}». غيّر المقدمة والأمثلة.")
    else:
        rep.add(OK, "النص مختلف عن فيديوهاتك السابقة", f"أعلى تطابق بالجمل: {worst_j:.0%}")
    if worst_c > 0.85:
        rep.add(WARN, "نفس الموضوع تقريباً لفيديو سابق",
                "لا بأس إذا كانت الزاوية جديدة (نظام آخر، مشكلة مختلفة). وإلا اختر موضوعاً آخر.")


def check_human_touch(project: Project, script: Script, rep: Report) -> None:
    if not project.draft.exists():
        rep.add(OK, "السكريبت مكتوب أو معدّل يدوياً", "لا توجد مسودة آلية للمقارنة.")
        return
    try:
        draft = load_script(project.draft)
    except Exception:
        return
    ratio = difflib.SequenceMatcher(None, draft.narration, script.narration).ratio()
    changed = 1 - ratio
    if changed < 0.03:
        rep.add(FAIL, "لم تعدّل السكريبت الذي كتبه الذكاء الاصطناعي",
                "أضف تجربتك أو ملاحظة شخصية أو مثالاً حقيقياً، وصحّح أي خطأ. هذه «لمستك» التي "
                "تحمي القناة من تصنيف «محتوى غير أصيل».")
    elif changed < 0.10:
        rep.add(WARN, "تعديلاتك على السكريبت قليلة",
                f"غيّرت حوالي {changed:.0%} فقط. حاول إضافة جملة أو نصيحة من تجربتك.")
    else:
        rep.add(OK, "أضفت لمستك على السكريبت", f"نسبة التعديل حوالي {changed:.0%}.")


def check_variety(project: Project, script: Script, rep: Report) -> None:
    info = project.read_info()
    prev = other_projects(project)[-3:]
    prev_themes = [p.read_info().get("theme") for p in prev]
    if info.get("theme") and info.get("theme") in prev_themes:
        rep.add(WARN, "نفس الشكل (Theme) المستخدم مؤخراً",
                f"الشكل «{info['theme']}» استُخدم في آخر 3 فيديوهات. "
                "غيّره: python tt.py build <name> --theme <other>")
    else:
        rep.add(OK, "الشكل مختلف عن آخر الفيديوهات", f"الشكل الحالي: {info.get('theme', '?')}")
    my_seq = [s.visual for s in script.sections]
    for p in prev[-1:]:
        try:
            if [s.visual for s in load_script(p.script).sections] == my_seq:
                rep.add(WARN, "نفس ترتيب الشرائح للفيديو السابق",
                        "غيّر ترتيب أو نوع بعض الأقسام (مثلاً أضف لقطة شاشة أو قسم نصيحة).")
        except Exception:
            pass
    shots = sum(1 for s in script.sections if s.visual == "shot")
    if shots == 0:
        rep.add(WARN, "لا توجد لقطات شاشة حقيقية",
                "إضافة لقطة أو لقطتين من جهازك تثبت أنك جرّبت الحل وتزيد قيمة الفيديو.")
    else:
        rep.add(OK, f"يوجد {shots} لقطة شاشة حقيقية")


def check_length(script: Script, rep: Report) -> None:
    mins = script.estimated_minutes()
    if mins < 3:
        rep.add(WARN, "الفيديو قصير جداً كفيديو طويل",
                f"حوالي {mins:.1f} دقيقة. الفيديوهات أقل من 3 دقائق تربح أقل وقد تبدو ضعيفة القيمة.")
    else:
        rep.add(OK, "طول مناسب", f"حوالي {mins:.1f} دقيقة من الكلام.")


def check_title(script: Script, rep: Report) -> None:
    t = script.title
    if CLICKBAIT.search(t):
        rep.add(FAIL, "العنوان فيه مبالغة (Clickbait)",
                f"«{t}». سياسة يوتيوب تمنع العناوين المضللة، وقد يُحذف الفيديو أو تُوقف أرباحه.")
    caps = sum(1 for ch in t if ch.isupper()) / max(sum(1 for ch in t if ch.isalpha()), 1)
    if caps > 0.6:
        rep.add(WARN, "العنوان كله بحروف كبيرة", "اكتبه بشكل عادي مع تكبير كلمة أو كلمتين فقط.")
    m = re.search(r"\b(\d{1,2})\s+(?:\w+\s+)?(fixes|ways|steps|tips|methods|solutions)\b", t, re.I)
    if m:
        from .slides import split_step
        n_steps = sum(1 for s in script.sections if split_step(s.heading)[0])
        if n_steps and n_steps != int(m.group(1)):
            rep.add(FAIL, "الرقم في العنوان لا يطابق عدد الخطوات",
                    f"العنوان يقول {m.group(1)} لكن الفيديو فيه {n_steps} خطوات. هذا يُعتبر عنواناً مضللاً.")
    kws = set(keywords(t))
    body = " ".join(keywords(script.narration))
    missing = [k for k in kws if k not in body]
    if kws and len(missing) / len(kws) > 0.5:
        rep.add(WARN, "العنوان لا يطابق محتوى الفيديو جيداً",
                f"كلمات في العنوان لا تظهر في الشرح: {', '.join(missing)}")
    elif not CLICKBAIT.search(t):
        rep.add(OK, "العنوان صادق ويطابق المحتوى", t)


def check_safety(script: Script, rep: Report) -> None:
    risky = []
    for s in script.sections:
        for text in [s.narration, *s.code]:
            m = RISKY.search(text)
            if m:
                risky.append((s.heading, m.group(0)))
    if not risky:
        rep.add(OK, "لا توجد خطوات خطيرة")
        return
    has_warning = any(s.visual == "tip" and re.search(r"backup|back up|restore point|careful|"
                                                      r"warning", s.narration, re.I)
                      for s in script.sections)
    detail = "؛ ".join(f"«{h}»: {w}" for h, w in risky[:5])
    if has_warning:
        rep.add(OK, "توجد خطوات حساسة ومعها تحذير", detail)
    else:
        rep.add(WARN, "خطوات حساسة بدون تحذير واضح",
                detail + ". أضف قسم [visual: tip] ينصح بعمل نسخة احتياطية أو نقطة استعادة.")


def check_assets(project: Project, rep: Report, music: str = "") -> None:
    assets = load_assets(project)
    files = []
    if project.shots_dir.exists():
        files += [f"shots/{p.name}" for p in sorted(project.shots_dir.iterdir()) if p.is_file()]
    if music:
        files.append(f"music/{Path(music).name}")
    changed = False
    for f in files:
        if f not in assets:
            assets[f] = {"source": "", "license": ""}
            changed = True
    if changed:
        project.assets_json.write_text(json.dumps(assets, indent=2, ensure_ascii=False),
                                       encoding="utf-8")
    unknown = [f for f in files if not (assets.get(f) or {}).get("source", "").strip()]
    if unknown:
        rep.add(FAIL, "مواد بدون مصدر أو ترخيص",
                "اكتب المصدر في assets.json لكل ملف (لقطاتك: \"source\": \"own\"): "
                + ", ".join(unknown))
    elif files:
        rep.add(OK, "كل المواد مسجّل مصدرها وترخيصها", f"{len(files)} ملف")
    else:
        rep.add(OK, "لا توجد مواد خارجية", "الشرائح مصنوعة بالأداة.")


def facts_to_verify(script: Script, llm: Ollama | None) -> list[str]:
    items = [f"الأمر: `{c}`" for s in script.sections for c in s.code]
    for s in script.sections:
        for sent in re.split(r"(?<=[.!?])\s+", s.narration):
            if re.search(r"(\d|>|settings|control panel|menu|click|press|ctrl|alt|win\+)",
                         sent, re.I) and len(items) < 25:
                items.append(sent.strip())
    if llm is not None:
        try:
            data = llm.chat_json(
                "List statements in this tech tutorial that might be wrong, outdated or "
                "platform-specific and must be checked by a human. Return JSON "
                '{"items": ["..."]} with at most 8 items.\n\n' + script.narration[:6000],
                temperature=0.2)
            for it in (data or {}).get("items", [])[:8]:
                items.append(f"🤖 {it}")
        except LLMError as e:
            items.append(f"(تعذّرت المراجعة بالذكاء الاصطناعي: {e})")
    return items


# ------------------------------------------------------------- report

HUMAN_CHECKLIST = [
    "جرّبت الحل بنفسك على جهاز حقيقي وتأكدت أنه يعمل.",
    "أضفت ملاحظة أو تجربة شخصية واحدة على الأقل.",
    "الصورة المصغرة والعنوان يعكسان محتوى الفيديو بصدق.",
    "إذا أظهر الفيديو أشخاصاً أو أحداثاً واقعية مصنوعة بالذكاء الاصطناعي: فعّل خيار "
    "«محتوى معدّل أو اصطناعي» عند الرفع. (التعليق الصوتي الآلي على شرائح لا يحتاجه عادةً.)",
    "لا توجد موسيقى أو صور أو مقاطع من مصدر لا تملك حق استخدامه.",
    "لم تنشر اليوم فيديوهات كثيرة متشابهة؛ الجودة أهم من الكمية.",
]


def run_check(project: Project, script: Script, llm: Ollama | None = None,
              music: str = "") -> tuple[Path, Report]:
    rep = Report()
    check_originality(project, script, rep)
    check_human_touch(project, script, rep)
    check_variety(project, script, rep)
    check_length(script, rep)
    check_title(script, rep)
    check_safety(script, rep)
    check_assets(project, rep, music)
    facts = facts_to_verify(script, llm)

    if rep.fails:
        verdict = f"{FAIL} لا تنشر بعد: يوجد {rep.fails} مشكلة يجب إصلاحها."
    elif rep.warns:
        verdict = f"{WARN} يمكن النشر، لكن راجع {rep.warns} ملاحظة لتحسين الفيديو."
    else:
        verdict = f"{OK} الفيديو جاهز من ناحية السياسات (بعد إكمال القائمة اليدوية)."
    lines = [f"# فحص ما قبل النشر: {script.title}", "", f"**النتيجة:** {verdict}", "",
             "## الفحوصات التلقائية", ""]
    for status, title, detail in rep.items:
        lines.append(f"- {status} **{title}**" + (f" — {detail}" if detail else ""))
    lines += ["", "## معلومات يجب أن تتأكد منها بنفسك", ""]
    lines += [f"- [ ] {f}" for f in facts] or ["- لا شيء."]
    lines += ["", "## قائمة يدوية قبل الضغط على «نشر»", ""]
    lines += [f"- [ ] {item}" for item in HUMAN_CHECKLIST]
    out = project.dir / "check.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out, rep
