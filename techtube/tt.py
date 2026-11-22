#!/usr/bin/env python3
"""TechTube - turn a tech problem into a ready-to-upload YouTube video, 100% local.

    python tt.py trends                          # find trending problems
    python tt.py script "laptop overheating"     # AI writes projects/laptop-overheating/script.md
    python tt.py preview laptop-overheating      # quick PNG previews of every slide
    python tt.py all laptop-overheating          # voice + video + shorts + metadata + check

Run `python tt.py <command> -h` for options.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from techtube import themes  # noqa: E402
from techtube.llm import LLMError, Ollama  # noqa: E402
from techtube.script import load_script, parse_script, render_script, write_script  # noqa: E402
from techtube.util import Project, get_project, load_config, projects_root, slugify  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def llm_from(cfg, args) -> Ollama:
    return Ollama(getattr(args, "model", None) or cfg["model"], cfg["ollama_host"])


def need_llm(llm: Ollama) -> Ollama:
    if not llm.available():
        sys.exit(f"[x] Ollama is not running at {llm.host}.\n"
                 f"    Start the Ollama app (or run: ollama serve) and: ollama pull {llm.model}")
    return llm


def load(cfg, name):
    project = get_project(cfg, name)
    if not project.script.exists():
        sys.exit(f"[x] No script found: {project.script}\n"
                 f"    Create one with: python tt.py script \"your problem\"")
    return project, load_script(project.script)


def theme_for(project: Project, override: str | None = None):
    info = project.read_info()
    if override:
        if override not in themes.BY_NAME:
            sys.exit(f"[x] Unknown theme '{override}'. Options: {', '.join(themes.BY_NAME)}")
        info["theme"] = override
        project.write_info(info)
    if not info.get("theme"):
        info["theme"] = pick_new_theme(project)
        project.write_info(info)
    return themes.get_theme(info["theme"])


def pick_new_theme(project: Project) -> str:
    from techtube.check import other_projects
    recent = [p.read_info().get("theme", "") for p in other_projects(project)]
    return themes.pick_theme(recent, seed=project.name).name


# ------------------------------------------------------------------ commands

def cmd_trends(cfg, args):
    from techtube.trends import DEFAULT_SEEDS, DEFAULT_SUBS, run_trends
    seeds = [s.strip() for s in args.seed.split(",")] if args.seed else DEFAULT_SEEDS
    subs = [s.strip() for s in args.subs.split(",")] if args.subs else DEFAULT_SUBS
    llm = None
    if not args.no_llm:
        llm = llm_from(cfg, args)
        if not llm.available():
            print("  [!] Ollama not running: showing raw trends without AI ranking.")
            llm = None
    path = run_trends(projects_root(cfg) / "_trends", seeds, subs, llm, args.deep)
    print(f"[ok] {path}")


def cmd_script(cfg, args):
    if args.from_file:
        text = Path(args.from_file).read_text(encoding="utf-8")
        script = parse_script(text)
        name = args.name or slugify(script.problem or script.title)
    else:
        if not args.problem:
            sys.exit('[x] Give a problem, e.g.: python tt.py script "laptop overheating"')
        name = args.name or slugify(args.problem)
    project = Project(projects_root(cfg) / name)
    if project.script.exists() and not args.force:
        sys.exit(f"[x] {project.script} already exists. Use --force to overwrite or --name.")
    project.ensure()
    if not args.from_file:
        llm = need_llm(llm_from(cfg, args))
        print(f"  Writing script with {llm.model} (this can take a minute)...")
        try:
            script = write_script(llm, args.problem, args.context, args.minutes)
        except (LLMError, ValueError) as e:
            sys.exit(f"[x] {e}")
        project.draft.write_text(render_script(script), encoding="utf-8")
    project.script.write_text(render_script(script), encoding="utf-8")
    info = project.read_info()
    info.update({"problem": script.problem, "created": datetime.now().isoformat(timespec="seconds")})
    project.write_info(info)
    theme_for(project)
    print(f"[ok] {project.script}")
    print(f"     {len(script.sections)} sections, ~{script.estimated_minutes():.1f} min")
    print("     Now: read it, fix anything wrong, add your own tip. Then:")
    print(f"     python tt.py preview {project.name}   or   python tt.py all {project.name}")


def cmd_preview(cfg, args):
    from techtube.slides import Canvas, make_visual
    project, script = load(cfg, args.project)
    theme = theme_for(project, args.theme)
    out_dir = project.build_dir / "preview"
    out_dir.mkdir(parents=True, exist_ok=True)
    sizes = [(1920, 1080, "h")] + ([(1080, 1920, "v")] if args.vertical else [])
    for W, H, tag in sizes:
        canvas = Canvas(W, H, theme, channel=cfg.get("channel_name", ""))
        for i, sec in enumerate(script.sections, 1):
            if args.section and i != args.section:
                continue
            dur = max(sec.words / 2.5, 4)
            vis = make_visual(canvas, sec, dur, script, project.shots_dir)
            path = out_dir / f"{i:02d}_{tag}.png"
            vis.draw(vis.state(dur - 0.01)).save(path)
            print(f"  {path.relative_to(project.dir)}  [{sec.visual}] {sec.heading}")
    print(f"[ok] previews in {out_dir}  (theme: {theme.name})")


def cmd_voice(cfg, args):
    from techtube.voice import make_voice
    project, script = load(cfg, args.project)
    make_voice(project, script, args.engine, args.voice or cfg["voice"],
               float(cfg.get("voice_speed", 1.0)), args.force)
    print("[ok] voice ready")


def cmd_build(cfg, args):
    from techtube.build import build_video
    project, script = load(cfg, args.project)
    theme = theme_for(project, args.theme)
    out = build_video(project, script, theme, cfg, captions_mode=args.captions,
                      music=args.music)
    print(f"[ok] {out}  (theme: {theme.name})")


def cmd_shorts(cfg, args):
    from techtube.shorts import make_shorts
    project, script = load(cfg, args.project)
    theme = theme_for(project, args.theme)
    req = [int(x) for x in args.sections.split(",")] if args.sections else None
    outs = make_shorts(project, script, theme, cfg, req, args.captions)
    print(f"[ok] {len(outs)} short(s) in {project.shorts_dir}")


def cmd_meta(cfg, args):
    from techtube.meta import make_meta
    project, script = load(cfg, args.project)
    llm = None
    if not args.no_llm:
        llm = llm_from(cfg, args)
        if not llm.available():
            print("  [!] Ollama not running: writing simple metadata.")
            llm = None
    print(f"[ok] {make_meta(project, script, llm)}")


def cmd_check(cfg, args):
    from techtube.check import run_check
    project, script = load(cfg, args.project)
    theme_for(project)
    llm = None
    if args.llm:
        llm = llm_from(cfg, args)
        llm = llm if llm.available() else None
    path, rep = run_check(project, script, llm, args.music or cfg.get("music", ""))
    print(f"[ok] {path}")
    print(f"     problems: {rep.fails}   warnings: {rep.warns}")
    return rep


def cmd_all(cfg, args):
    print("1/5 voice");   cmd_voice(cfg, argparse.Namespace(project=args.project, engine=args.engine,
                                                          voice=None, force=False))
    print("2/5 video");   cmd_build(cfg, argparse.Namespace(project=args.project, theme=None,
                                                          captions=args.captions, music=None))
    print("3/5 shorts");  cmd_shorts(cfg, argparse.Namespace(project=args.project, theme=None,
                                                           sections=None, captions=args.captions))
    print("4/5 youtube metadata")
    cmd_meta(cfg, argparse.Namespace(project=args.project, no_llm=args.no_llm, model=None))
    print("5/5 policy check")
    rep = cmd_check(cfg, argparse.Namespace(project=args.project, llm=not args.no_llm,
                                            music=None, model=None))
    project = get_project(cfg, args.project)
    print(f"\nDone. Open {project.dir}: final.mp4, shorts/, youtube.txt, check.md")
    if rep.fails:
        print("Read check.md before publishing: there are problems to fix.")


def cmd_themes(cfg, args):
    for t in themes.THEMES:
        print(f"  {t.name:10s} accent {t.accent}  layout {t.layout:6s} deco {t.deco}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tt.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", help="path to config.json")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("trends", help="collect trending problems and video ideas")
    p.add_argument("--seed", help='comma list, e.g. "windows 11,laptop,android"')
    p.add_argument("--subs", help="comma list of subreddits")
    p.add_argument("--deep", action="store_true", help="many more YouTube suggestions (slower)")
    p.add_argument("--no-llm", action="store_true")
    p.add_argument("--model")
    p.set_defaults(fn=cmd_trends)

    p = sub.add_parser("script", help="write script.md for a problem (with the local AI)")
    p.add_argument("problem", nargs="?")
    p.add_argument("--name", help="project folder name")
    p.add_argument("--context", default="Windows 10/11", help='e.g. "Android 15", "macOS"')
    p.add_argument("--minutes", type=float, default=7)
    p.add_argument("--from-file", help="use your own script.md instead of the AI")
    p.add_argument("--model")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_script)

    p = sub.add_parser("preview", help="PNG preview of every slide (fast)")
    p.add_argument("project")
    p.add_argument("--section", type=int)
    p.add_argument("--vertical", action="store_true", help="also preview Shorts layout")
    p.add_argument("--theme")
    p.set_defaults(fn=cmd_preview)

    p = sub.add_parser("voice", help="make the voiceover")
    p.add_argument("project")
    p.add_argument("--engine", choices=["auto", "kokoro", "own"], default="auto",
                   help="auto: your recordings in myvoice/ if present, else Kokoro")
    p.add_argument("--voice", help="Kokoro voice, e.g. af_heart, am_michael, bf_emma")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_voice)

    for name, fn, hlp in (("build", cmd_build, "render final.mp4 (16:9)"),
                          ("shorts", cmd_shorts, "render vertical Shorts")):
        p = sub.add_parser(name, help=hlp)
        p.add_argument("project")
        p.add_argument("--theme")
        p.add_argument("--captions", choices=["auto", "whisper", "estimate", "off"],
                       default="auto")
        if name == "build":
            p.add_argument("--music", help="background music file (must be licensed!)")
        else:
            p.add_argument("--sections", help="section numbers, e.g. 2,4")
        p.set_defaults(fn=fn)

    p = sub.add_parser("meta", help="titles, description, tags, chapters -> youtube.txt")
    p.add_argument("project")
    p.add_argument("--no-llm", action="store_true")
    p.add_argument("--model")
    p.set_defaults(fn=cmd_meta)

    p = sub.add_parser("check", help="YouTube policy check -> check.md")
    p.add_argument("project")
    p.add_argument("--llm", action="store_true", help="also let the AI flag doubtful facts")
    p.add_argument("--music")
    p.add_argument("--model")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("all", help="voice + build + shorts + meta + check")
    p.add_argument("project")
    p.add_argument("--engine", choices=["auto", "kokoro", "own"], default="auto")
    p.add_argument("--captions", choices=["auto", "whisper", "estimate", "off"], default="auto")
    p.add_argument("--no-llm", action="store_true")
    p.set_defaults(fn=cmd_all)

    p = sub.add_parser("themes", help="list visual themes")
    p.set_defaults(fn=cmd_themes)

    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    try:
        args.fn(cfg, args)
    except (RuntimeError, FileNotFoundError, ValueError) as e:
        sys.exit(f"[x] {e}")


if __name__ == "__main__":
    main()
