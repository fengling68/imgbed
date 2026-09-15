#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
imgbed 批量转 WebP 工具
========================
把仓库内的所有位图（jpg/jpeg/png/gif/webp/bmp/tiff）转成 .webp 格式，
在尽量保留清晰度的前提下压缩体积：
  - 自动按 EXIF 方向校正（手机拍的照片不再歪）
  - PNG 带透明通道时保留 alpha
  - 动态 GIF 转为动态 WebP（保留帧与时长）
  - SVG 无法被 Pillow 光栅化，自动跳过并提示
  - 转换成功后校验输出有效，再原地替换原文件（删除原格式）

“绝不增大”策略（默认开启）：
  若生成的 WebP 比原图更大（多见于已高度优化的 JPEG/PNG），会自动用更低质量
  再试一次；若仍大于原图，则【保留原格式文件不动】，绝不为了转 WebP 而把体积撑大。
  可用 --force-webp 关闭该策略，强制全部转为 WebP（个别文件可能略大）。

用法：
  python3 convert_to_webp.py                      # 转换全部，开启“绝不增大”
  python3 convert_to_webp.py --force-webp         # 强制全部转 WebP（允许个别变大）
  python3 convert_to_webp.py --quality 90         # 调高质量（默认 85）
  python3 convert_to_webp.py --files a.jpg b.png  # 仅处理指定文件
  python3 convert_to_webp.py --dry-run            # 只统计，不真正转换
  python3 convert_to_webp.py --keep               # 保留原文件，仅新增 .webp

依赖：Pillow  (pip install Pillow)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    from PIL import Image, ImageOps, UnidentifiedImageError
    from PIL import ImageSequence
except ImportError:  # pragma: no cover
    sys.stderr.write("缺少依赖 Pillow，请先执行: pip install Pillow\n")
    raise

# 仓库根目录（脚本所在目录）
ROOT = Path(__file__).resolve().parent

# 需要扫描的子目录
SCAN_DIRS = ["images", "images-upic-blogs", "images-upic-picture"]

# 可处理的位图扩展名（小写，不含点）
RASTER_EXTS = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "tif", "tiff"}

DEFAULT_QUALITY = 85
METHOD = 6  # WebP 压缩算法搜索深度，6 为最高质量（最慢但压得最好）


@dataclass
class Result:
    path: str
    src_ext: str
    orig_size: int
    webp_size: int
    status: str  # ok / kept / kept-original / skipped / error
    note: str = ""


def human_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    for unit in ("KB", "MB", "GB"):
        n /= 1024.0
        if n < 1024:
            return f"{n:.1f} {unit}"
    return f"{n:.1f} TB"


def collect_images(files: list[str] | None) -> list[Path]:
    if files:
        out: list[Path] = []
        for f in files:
            p = (ROOT / f).resolve()
            if p.is_file():
                out.append(p)
            else:
                print(f"[警告] 找不到文件: {f}")
        return out
    out = []
    for d in SCAN_DIRS:
        base = ROOT / d
        if not base.exists():
            print(f"[跳过] 目录不存在: {base}")
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix.lower().lstrip(".") in RASTER_EXTS:
                out.append(p)
    return out


def _encode_webp(im: Image.Image, tmp_name: str, quality: int, is_animated: bool) -> None:
    if is_animated:
        frames = [ImageOps.exif_transpose(fr.convert("RGBA")) for fr in ImageSequence.Iterator(im)]
        frames[0].save(
            tmp_name, "WEBP", save_all=True, append_images=frames[1:],
            duration=im.info.get("duration", 80), loop=im.info.get("loop", 0),
            quality=quality, method=METHOD,
        )
    else:
        has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
        im2 = im.convert("RGBA") if has_alpha else im.convert("RGB")
        im2.save(tmp_name, "WEBP", quality=quality, method=METHOD)


def convert_one(path: Path, quality: int, dry_run: bool, keep: bool,
                no_grow: bool) -> Result:
    rel = str(path.relative_to(ROOT))
    src_ext = path.suffix.lower().lstrip(".")
    orig_size = path.stat().st_size

    if src_ext == "svg":
        return Result(rel, src_ext, orig_size, orig_size, "skipped", "SVG 无法光栅化，已跳过")
    if dry_run:
        return Result(rel, src_ext, orig_size, -1, "ok", "dry-run")

    try:
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im)
            is_animated = getattr(im, "is_animated", False) and im.n_frames > 1
            webp_path = path.with_suffix(".webp")

            tmp_fd, tmp_name = tempfile.mkstemp(suffix=".webp")
            os.close(tmp_fd)
            _encode_webp(im, tmp_name, quality, is_animated)
            webp_size = os.path.getsize(tmp_name)
            with Image.open(tmp_name) as check:
                check.verify()

            # “绝不增大”：WebP 比原图大时，尝试更低质量；仍大则保留原格式
            if no_grow and webp_size > orig_size:
                q2 = max(40, quality - 20)
                if q2 < quality:
                    tmp2_fd, tmp2_name = tempfile.mkstemp(suffix=".webp")
                    os.close(tmp2_fd)
                    try:
                        _encode_webp(im, tmp2_name, q2, is_animated)
                        s2 = os.path.getsize(tmp2_name)
                        with Image.open(tmp2_name) as c2:
                            c2.verify()
                        if s2 < webp_size:
                            os.replace(tmp2_name, tmp_name)
                            webp_size = s2
                    except Exception:
                        if os.path.exists(tmp2_name):
                            os.remove(tmp2_name)
                if webp_size > orig_size:
                    # 保留原文件，删除可能残留的更大 webp
                    if webp_path.exists() and webp_path != path:
                        os.remove(webp_path)
                    return Result(
                        rel, src_ext, orig_size, orig_size, "kept-original",
                        f"转 WebP 反而更大（{human_size(webp_size)}），已保留原格式",
                    )

            if keep:
                os.replace(tmp_name, webp_path)
                return Result(rel, src_ext, orig_size, webp_size, "kept", "已生成同名 .webp（原文件保留）")

            os.replace(tmp_name, webp_path)
            # 关键：仅当输出文件名与原文件不同（即确为转格式）时才删除原文件。
            # 若源本身就是 .webp（webp_path == path），绝不删除，否则会误删刚写好的文件。
            if webp_path != path:
                try:
                    os.remove(path)
                except OSError:
                    pass
            return Result(rel, src_ext, orig_size, webp_size, "ok", "")

    except UnidentifiedImageError:
        return Result(rel, src_ext, orig_size, orig_size, "error", "无法识别的图片格式")
    except Exception as e:  # noqa: BLE001
        return Result(rel, src_ext, orig_size, orig_size, "error", str(e)[:200])


def main() -> None:
    ap = argparse.ArgumentParser(description="imgbed 批量转 WebP")
    ap.add_argument("--quality", type=int, default=DEFAULT_QUALITY,
                    help=f"WebP 质量 0-100（默认 {DEFAULT_QUALITY}）")
    ap.add_argument("--no-grow", action="store_true", default=True,
                    help="开启“绝不增大”策略（默认开启）")
    ap.add_argument("--force-webp", action="store_true",
                    help="强制全部转 WebP，关闭“绝不增大”")
    ap.add_argument("--keep", action="store_true", help="保留原文件，仅新增 .webp")
    ap.add_argument("--dry-run", action="store_true", help="只统计，不转换")
    ap.add_argument("--files", nargs="*", default=None, help="仅处理指定的文件（相对仓库根目录）")
    args = ap.parse_args()

    if not (0 < args.quality <= 100):
        ap.error("quality 需在 1-100 之间")

    no_grow = (not args.force_webp) and args.no_grow

    files = collect_images(args.files)
    if not files:
        print("没有找到可转换的图片。")
        return

    print(f"待处理图片: {len(files)} 张 | 质量={args.quality} | "
          f"{'dry-run' if args.dry_run else ('保留原文件' if args.keep else '原地替换')} | "
          f"绝不增大={no_grow}")

    results: list[Result] = []
    total_orig = 0
    total_now = 0
    counts = {"ok": 0, "kept": 0, "kept-original": 0, "skipped": 0, "error": 0}

    for i, p in enumerate(files, 1):
        r = convert_one(p, args.quality, args.dry_run, args.keep, no_grow)
        results.append(r)
        total_orig += r.orig_size
        final = r.webp_size if r.status in ("ok", "kept") else r.orig_size
        total_now += final if not args.dry_run else 0
        if r.status in counts:
            counts[r.status] += 1
        if not args.dry_run:
            bar = "#" * int(40 * i / len(files))
            print(f"\r[{i:>3}/{len(files)}] {bar:<40}", end="", flush=True)

    print()

    print("\n================ 转换报告 ================")
    print(f"成功转 WebP : {counts['ok'] + counts['kept']}")
    print(f"保留原格式  : {counts['kept-original']}")
    print(f"跳过        : {counts['skipped']}")
    print(f"失败        : {counts['error']}")
    if not args.dry_run:
        saved = total_orig - total_now
        pct = (saved / total_orig * 100) if total_orig else 0
        print(f"原始总大小: {human_size(total_orig)}")
        print(f"现在总大小: {human_size(total_now)}")
        print(f"节省体积  : {human_size(saved)} ({pct:.1f}%)")

    report = {
        "quality": args.quality,
        "no_grow": no_grow,
        "dry_run": args.dry_run,
        "keep": args.keep,
        "total_original_bytes": total_orig,
        "total_now_bytes": total_now if not args.dry_run else None,
        "counts": counts,
        "items": [asdict(r) for r in results],
    }
    out_json = ROOT / "webp_convert_report.json"
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n明细已写入: {out_json}")

    kept = [r for r in results if r.status == "kept-original"]
    if kept:
        print(f"\n[说明] 以下 {len(kept)} 个文件转 WebP 后体积反而更大，已保留原格式以避免膨胀：")
        for r in kept:
            print(f"  - {r.path}: {r.note}")
    failed = [r for r in results if r.status == "error"]
    if failed:
        print("\n失败明细:")
        for r in failed:
            print(f"  - {r.path}: {r.note}")


if __name__ == "__main__":
    main()
