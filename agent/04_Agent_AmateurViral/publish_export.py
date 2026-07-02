# -*- coding: utf-8 -*-
"""
发布版打包（Agent4 固定能力）—— ⚠️ 默认不自动执行，仅在用户明确要求"导出/生成发布版"时运行。

把一个 run 的笔记打包成「发布版」：
  - 不按大类分文件夹；每篇一个以角度编号(A1/A2/B1/C1…)打头的文件夹
  - 文件夹内含 <标题>.md（文案，无"标题/正文"标签）+ <标题>.png（大字报封面，如有）
  - 大类用 A/B/C 区分，细分用编号（与 writer4.PROPERTY_ANGLES 的标签前缀一致）

角度识别顺序（可靠优先）：note 文件夹内 _angle.txt → drafts/*.json 的 _category（按标题匹配）→ 关键词兜底。

用法（在 agent/ 目录下）：
  python -m 04_Agent_AmateurViral.publish_export --run-dir "/path/to/<run_id>" [--out "/path/发布版"] [--include-photos]
  # run 目录需含 notes/（每篇一个子文件夹，含 note.txt，封面命名 photo_1.*）
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 角度 → 编号（与 writer4.PROPERTY_ANGLES 标签前缀一致；此处内联以保持本模块自包含）
ANGLE_CODE = {
    "放弃叙事": "A1", "意外种草": "A2", "纠结对比": "A3",
    "决赛圈对比": "A4", "住得下吗": "A5", "召唤过来人": "A6",
    "优缺点总结": "B1", "看房日记": "B2", "看房踩坑": "B3",
    "长啥样开箱": "B4", "单价你会买吗": "B5",
    "预算现实吗": "C1",
}

_KW = [  # 关键词兜底（仅用于既无 _angle.txt 又无 drafts 的老 run）
    (["长啥样", "看看", "开箱"], "长啥样开箱"),
    (["单价", "一呎", "你会买"], "单价你会买吗"),
    (["意外", "本来没", "居然心动", "看对眼", "没想到", "差点"], "意外种草"),
    (["放弃"], "放弃叙事"),
    (["看麻", "踩坑", "勉强及格", "算正常"], "看房踩坑"),
    (["优缺点", "直白", "测评"], "优缺点总结"),
    (["看房日记", "今天去看", "能买吗"], "看房日记"),
    (["决赛圈"], "决赛圈对比"),
    (["住得下", "一家", "住不住"], "住得下吗"),
    (["后悔吗", "住过", "买过"], "召唤过来人"),
    (["现实吗", "离谱", "能上车吗", "靠谱吗", "有戏"], "预算现实吗"),
]


MAX_PHOTOS = 4          # A/B 每篇最多配几张实拍图
_IMG_EXT = (".jpg", ".jpeg", ".png")


def _real_photos(d: Path) -> list:
    """房源目录里的实拍图（排除大字报封面 photo_1 / *cover*）。"""
    return sorted(
        f for f in d.iterdir()
        if f.suffix.lower() in _IMG_EXT
        and "cover" not in f.name.lower()
        and f.stem not in ("photo_1",)
    )


def _gather_photos(folder: Path) -> list:
    """给一篇 A/B 笔记凑实拍图：优先从 _property.txt 记录的源房源图库取，
    对比篇有多套则每套轮流取；不足再用 note 文件夹里已复制的 photo_2/3 兜底。"""
    picked: list = []
    prop_file = folder / "_property.txt"
    if prop_file.exists():
        src_dirs = [Path(l.strip()) for l in prop_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        pools = [_real_photos(d) for d in src_dirs if d.is_dir()]
        # 每套轮流取一张，直到取满 MAX_PHOTOS
        idx = 0
        while len(picked) < MAX_PHOTOS and any(idx < len(pool) for pool in pools):
            for pool in pools:
                if idx < len(pool) and len(picked) < MAX_PHOTOS:
                    picked.append(pool[idx])
            idx += 1
    if not picked:  # 兜底：note 文件夹里已随机复制的 photo_2/3…
        picked = [p for p in sorted(folder.glob("photo_*")) if p.stem != "photo_1"][:MAX_PHOTOS]
    return picked[:MAX_PHOTOS]


def _norm(s: str) -> str:
    return re.sub(r"[^\w一-鿿]", "", s)


def _safe(s: str) -> str:
    return re.sub(r"[/:\\]", "_", s).strip()[:45]


def _fix_tags_line(line: str) -> str:
    """把 '#a,b,c' 这种规范成 '#a #b #c'。"""
    parts = [t for t in re.split(r"[,，、\s#]+", line) if t.strip()]
    return " ".join(f"#{t}" for t in dict.fromkeys(parts))


def _load_drafts(run_dir: Path) -> dict:
    m = {}
    for jf in (run_dir / "drafts").glob("*.json"):
        try:
            d = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            continue
        t = (d.get("hook_title") or "").strip()
        if t:
            m[t] = d.get("_category", "")
    return m


def _resolve_angle(folder: Path, title: str, drafts: dict, drafts_norm: dict) -> str:
    # 1) _angle.txt（最可靠）
    af = folder / "_angle.txt"
    if af.exists():
        ang = af.read_text(encoding="utf-8").strip()
        if ang in ANGLE_CODE:
            return ang
    # 2) drafts 精确 / 归一化匹配
    ang = drafts.get(title) or drafts_norm.get(_norm(title))
    if ang in ANGLE_CODE:
        return ang
    # 3) 关键词兜底
    for kws, ang in _KW:
        if any(k in title for k in kws):
            return ang
    return ""


def export(run_dir: Path, out_dir: Path, include_photos: bool = False) -> None:
    notes_dir = run_dir / "notes"
    if not notes_dir.is_dir():
        print(f"✗ 找不到 notes 目录：{notes_dir}")
        sys.exit(1)
    drafts = _load_drafts(run_dir)
    drafts_norm = {_norm(k): v for k, v in drafts.items()}

    out_dir.mkdir(parents=True, exist_ok=True)
    ok, skipped = 0, []
    for folder in sorted(d for d in notes_dir.iterdir() if d.is_dir() and (d / "note.txt").exists()):
        raw = (folder / "note.txt").read_text(encoding="utf-8")
        title = raw.splitlines()[0].strip()
        ang = _resolve_angle(folder, title, drafts, drafts_norm)
        if not ang:
            skipped.append(title)
            continue
        code = ANGLE_CODE[ang]
        base = _safe(title)
        dst = out_dir / f"{code}_{base}"
        dst.mkdir(parents=True, exist_ok=True)

        # 文案 .md（顺手规范 tag 行）
        lines = raw.splitlines()
        lines = [_fix_tags_line(ln) if ln.startswith("#") and re.search(r"[,，、]", ln) else ln for ln in lines]
        (dst / f"{base}.md").write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

        # 封面 photo_1.* → 01_封面_<标题>
        covers = sorted(folder.glob("photo_1.*"))
        if covers:
            shutil.copy2(covers[0], dst / f"01_封面_{base}{covers[0].suffix}")

        # 实拍图：A/B 类要配（指向具体房源），命名 0N_实拍_<源图原名>；C 询问类不配（需求口吻，不指向房源）
        if code[0] in ("A", "B"):
            for j, ph in enumerate(_gather_photos(folder), start=2):
                shutil.copy2(ph, dst / f"{j:02d}_实拍_{ph.name}")
        ok += 1

    print(f"✅ 发布版导出完成：{ok} 篇 → {out_dir}")
    # 分大类计数
    from collections import Counter
    dist = Counter(p.name.split("_")[0] for p in out_dir.iterdir() if p.is_dir())
    print("   编号分布：" + "  ".join(f"{k}×{v}" for k, v in sorted(dist.items())))
    if skipped:
        print(f"   ⚠ 未能识别角度、已跳过 {len(skipped)} 篇：")
        for t in skipped:
            print("     -", t)


def main():
    ap = argparse.ArgumentParser(description="Agent4 发布版打包（仅在用户明确要求时使用）")
    ap.add_argument("--run-dir", required=True, help="run 目录（含 notes/，可选 drafts/）")
    ap.add_argument("--out", default=None, help="发布版输出目录（默认 <run-dir>/发布版）")
    ap.add_argument("--include-photos", action="store_true", help="同时复制房图 photo_2/3（默认只 md+封面）")
    args = ap.parse_args()
    run_dir = Path(args.run_dir).resolve()
    out_dir = Path(args.out).resolve() if args.out else run_dir / "发布版"
    export(run_dir, out_dir, include_photos=args.include_photos)


if __name__ == "__main__":
    main()
