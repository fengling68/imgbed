# WebP 图片批量压缩说明

## 一、背景

`imgbed` 文件夹中存放博客使用的 `.webp` 图片，共 365 张。这些图片原本已接近 q85 的压缩率，为进一步减小体积，在不明显损画质的前提下统一压缩。

- **压缩策略**：`quality=80`、`method=6`（Pillow 最大压缩强度）
- **安全性**：仅当重压后文件**变小**才原地替换；无法变小的图片保持不变
- **保留信息**：保留 ICC 色彩配置、EXIF、XMP 等元数据；支持带透明通道（alpha）的图片
- **文件名不变**，博客引用的 URL 依然有效

## 二、本次结果

| 项 | 数值 |
|---|---|
| 已处理文件 | 365 张 |
| 重压后变小并替换 | 307 张 |
| q80 无法变小、保留原样 | 58 张 |
| 动画文件 | 0 张 |
| 压缩前总大小 | 157.32 MB |
| 压缩后总大小 | 131.49 MB |
| **节省空间** | **25.83 MB（16.4%）** |

不同目标质量的平均节省对比（抽样实测）：

| 目标质量 | 平均节省 | 画质影响 |
|---|---|---|
| q80 | ~10%（总体约 16%） | 几乎无损 |
| q75 | ~20%-25% | 轻微损失 |
| q70 | ~27%-30% | 可感知损失 |

## 三、复用步骤

### 1. 安装依赖

需要 Python 3 + Pillow（自带 libwebp）：

```bash
python3 -m pip install --user Pillow
python3 -c "from PIL import features; print(features.check('webp'))"  # 应输出 True
```

### 2. 批量压缩脚本

修改 `QUALITY` 可切换档位（默认 80，想更省可改 75）。

```python
import io, os, glob
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

files = sorted(glob.glob('/Users/lv/Desktop/Github/imgbed/**/*.webp', recursive=True))
QUALITY = 80   # 视觉几乎无损；75 可省更多

total_before = 0
total_after = 0
changed = 0
kept = 0

for f in files:
    sz0 = os.path.getsize(f)
    total_before += sz0
    try:
        im = Image.open(f)
        if getattr(im, 'is_animated', False):   # 跳过动图
            total_after += sz0
            continue
        info = {k: im.info[k] for k in ('xmp','icc_profile','exif','metadata') if k in im.info}
        buf = io.BytesIO()
        im.save(buf, 'WEBP', quality=QUALITY, method=6, alpha_q=100, **info)
        new = len(buf.getvalue())
        if new < sz0:                           # 只有变小才替换
            tmp = f + '.tmp.webp'
            with open(tmp, 'wb') as fh:
                fh.write(buf.getvalue())
            os.replace(tmp, f)
            changed += 1
            total_after += new
        else:
            kept += 1
            total_after += sz0
    except Exception as e:
        print(f"ERR {f}: {e}")
        total_after += sz0

print(f"processed={len(files)} replaced={changed} kept={kept}")
print(f"before={total_before/1024/1024:.2f}MB after={total_after/1024/1024:.2f}MB "
      f"saved={(total_before-total_after)/1024/1024:.2f}MB ({(1-total_after/total_before)*100:.1f}%)")
```

### 3. 运行

```bash
python3 /path/to/script.py
```

## 四、注意

- 若图片在 git 仓库中，压缩会改变文件内容，属正常改动，可按需提交。
- 若以后新增图片想保持同样压缩，可在上传前就按 `quality=80` 输出。