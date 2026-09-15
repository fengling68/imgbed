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