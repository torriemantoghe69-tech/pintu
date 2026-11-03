# 拼图工坊（Puzzle Workshop）

一个可以把本地图片变成拼图挑战的 Windows 桌面小游戏。

## 功能

- 选择 PNG、JPG、JPEG、BMP、WEBP 图片
- 3×3、4×4、5×5 三种难度
- 随机打乱拼块，鼠标拖动并自动吸附到正确位置
- 计步、计时、参考图预览
- 支持重新打乱和更换图片

## 直接下载 Windows 程序

每次推送代码后，GitHub Actions 会自动构建 Windows 单文件程序。

1. 打开仓库的 **Actions** 页面。
2. 进入最新的 **Build Windows EXE** 工作流。
3. 在页面底部的 **Artifacts** 下载 `PuzzleWorkshop-Windows`。
4. 解压后双击 `PuzzleWorkshop.exe` 即可运行。

也可以在仓库的 Releases 页面发布正式版本。

## 本地运行（可选）

```bash
python -m pip install -r requirements.txt
python main.py
```

## 技术

Python、Pygame、Pillow、PyInstaller、GitHub Actions。
