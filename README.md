# imgbed

`imgbed` 文件夹中存放博客使用的 `.webp` 图片。

## 图片转格式和压缩

- **压缩策略**：`quality=80`、`method=6`（Pillow 最大压缩强度）
- **安全性**：仅当重压后文件**变小**才原地替换；无法变小的图片保持不变
- **保留信息**：保留 ICC 色彩配置、EXIF、XMP 等元数据；支持带透明通道（alpha）的图片
- **文件名不变**，博客引用的 URL 依然有效

### 1. 安装依赖

需要 Python 3 + Pillow：

```bash
python3 -m pip install --user Pillow
python3 -c "from PIL import features; print(features.check('webp'))"  # 应输出 True
```

### 2. 批量压缩脚本

修改 `QUALITY` 可切换档位。

### 3. 运行

```bash
python3 ./py/convert_to_webp.py
python3 ./py/webp_to_webp.py
```