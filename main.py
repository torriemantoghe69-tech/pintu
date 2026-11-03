import math
import random
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox

import pygame
from PIL import Image, ImageOps

WIDTH, HEIGHT = 1120, 760
BOARD = pygame.Rect(24, 82, 660, 660)
PANEL = pygame.Rect(710, 82, 386, 660)
BG = (20, 25, 38)
PANEL_BG = (31, 39, 57)
ACCENT = (104, 167, 255)
WHITE = (240, 244, 252)
MUTED = (160, 173, 194)


def choose_image():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askopenfilename(
        title="选择一张图片",
        filetypes=[("图片文件", "*.png *.jpg *.jpeg *.bmp *.webp"), ("所有文件", "*.*")]
    )
    root.destroy()
    return path


class PuzzleGame:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("拼图工坊")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Microsoft YaHei, SimHei, Arial", 22)
        self.small = pygame.font.SysFont("Microsoft YaHei, SimHei, Arial", 16)
        self.big = pygame.font.SysFont("Microsoft YaHei, SimHei, Arial", 30, bold=True)
        self.image = None
        self.image_path = ""
        self.rows = 3
        self.cols = 3
        self.pieces = []
        self.dragging = None
        self.drag_offset = (0, 0)
        self.moves = 0
        self.started = None
        self.elapsed = 0
        self.show_preview = False
        self.mode = "drag"  # drag: 拖放拼图；slide: 格子滑动拼图
        self.sliding_order = []
        self.message = "先选择一张图片，开始你的拼图挑战！"
        self.buttons = {}
        self.running = True
        self.new_game(None)

    def make_button(self, name, rect, label, enabled=True):
        color = (57, 83, 124) if enabled else (54, 60, 72)
        pygame.draw.rect(self.screen, color, rect, border_radius=10)
        pygame.draw.rect(self.screen, (86, 111, 151), rect, 1, border_radius=10)
        txt = self.small.render(label, True, WHITE if enabled else MUTED)
        self.screen.blit(txt, txt.get_rect(center=rect.center))
        self.buttons[name] = rect

    def new_game(self, path):
        if path:
            try:
                self.image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
                self.image_path = path
            except Exception as exc:
                messagebox.showerror("无法打开图片", str(exc))
                return
        if self.image is None:
            self.pieces = []
            return
        self.build_pieces()
        if self.mode == "slide":
            self.shuffle_sliding()
        self.moves = 0
        self.started = time.time()
        self.elapsed = 0
        self.message = "拖动右侧拼块，放到左侧对应位置。"
        
    def _edge_points(self, start, end, normal, protrudes, tab):
        """返回一条带圆弧凸起/凹槽的边界点。"""
        points = [start]
        if protrudes is None:
            points.append(end)
            return points
        dx, dy = end[0] - start[0], end[1] - start[1]
        direction = 1 if protrudes else -1
        depth = tab * 0.92 * direction
        for i in range(17):
            u = 0.34 + i * (0.32 / 16)
            bulge = math.sin(math.pi * (i / 16)) ** 0.72
            points.append((start[0] + dx * u + normal[0] * depth * bulge,
                           start[1] + dy * u + normal[1] * depth * bulge))
        points.append(end)
        return points

    def make_jigsaw_surface(self, image, row, col, cell_w, cell_h, tab):
        """裁出带透明凸起/凹槽轮廓的拼图块；相邻边使用互补形状。"""
        from PIL import ImageDraw

        x0, y0 = col * cell_w, row * cell_h
        x1, y1 = x0 + cell_w, y0 + cell_h
        canvas_w, canvas_h = cell_w + 2 * tab, cell_h + 2 * tab
        crop = image.crop((x0 - tab, y0 - tab, x1 + tab, y1 + tab)).convert("RGBA")

        def horizontal_edge(r, boundary):
            return ((r * 37 + boundary * 19 + 11) % 2) == 0

        def vertical_edge(boundary, c):
            return ((boundary * 29 + c * 43 + 7) % 2) == 0

        top = None if row == 0 else not vertical_edge(row, col)
        right = None if col == self.cols - 1 else horizontal_edge(row, col)
        bottom = None if row == self.rows - 1 else vertical_edge(row + 1, col)
        left = None if col == 0 else not horizontal_edge(row, col - 1)

        scale = 4
        mask = Image.new("L", (canvas_w * scale, canvas_h * scale), 0)
        draw = ImageDraw.Draw(mask)
        t, cw, ch = tab * scale, cell_w * scale, cell_h * scale
        points = [(t, t)]
        edges = [
            ((t, t), (t + cw, t), (0, -1), top),
            ((t + cw, t), (t + cw, t + ch), (1, 0), right),
            ((t + cw, t + ch), (t, t + ch), (0, 1), bottom),
            ((t, t + ch), (t, t), (-1, 0), left),
        ]
        for a, b, normal, protrudes in edges:
            points.extend(self._edge_points(a, b, normal, protrudes, t)[1:])
        draw.polygon(points, fill=255)
        mask = mask.resize((canvas_w, canvas_h), Image.Resampling.LANCZOS)
        crop.putalpha(mask)
        return pygame.image.fromstring(crop.tobytes(), crop.size, "RGBA").convert_alpha()

    def build_pieces(self):
        image = ImageOps.fit(self.image, (600, 600), method=Image.Resampling.LANCZOS)
        self.preview_image = pygame.image.fromstring(image.tobytes(), image.size, "RGB")
        cell_w = 600 // self.cols
        cell_h = 600 // self.rows
        tab = max(12, int(min(cell_w, cell_h) * 0.17))
        pieces = []
        ids = list(range(self.rows * self.cols))
        random.shuffle(ids)
        thumb_size = min(90, (340 - (self.cols - 1) * 8) // self.cols, (300 - (self.rows - 1) * 8) // self.rows)
        for tray_index, idx in enumerate(ids):
            row, col = divmod(idx, self.cols)
            surface = self.make_jigsaw_surface(image, row, col, cell_w, cell_h, tab)
            thumb = pygame.transform.smoothscale(surface, (thumb_size, thumb_size))
            tray_col = tray_index % self.cols
            tray_row = tray_index // self.cols
            pieces.append({
                "id": idx, "row": row, "col": col, "surface": surface,
                "thumb": thumb, "thumb_size": thumb_size, "tab": tab,
                "tx": 730 + tray_col * (thumb_size + 8),
                "ty": 265 + tray_row * (thumb_size + 8),
                "w": surface.get_width(), "h": surface.get_height(),
                "x": 0, "y": 0, "placed": False
            })
        self.pieces = pieces
        self.reference_thumb = pygame.transform.smoothscale(self.preview_image, (112, 112))

    def shuffle_sliding(self):
        """生成可解的滑块排列，0 代表空格。"""
        count = self.rows * self.cols
        order = list(range(1, count)) + [0]
        blank = count - 1
        previous = -1
        for _ in range(max(120, count * 35)):
            r, c = divmod(blank, self.cols)
            choices = []
            if r > 0: choices.append(blank - self.cols)
            if r < self.rows - 1: choices.append(blank + self.cols)
            if c > 0: choices.append(blank - 1)
            if c < self.cols - 1: choices.append(blank + 1)
            if previous in choices and len(choices) > 1:
                choices.remove(previous)
            nxt = random.choice(choices)
            order[blank], order[nxt] = order[nxt], order[blank]
            previous, blank = blank, nxt
        self.sliding_order = order

    def slide_tile(self, index):
        if index < 0 or index >= len(self.sliding_order):
            return
        blank = self.sliding_order.index(0)
        r1, c1 = divmod(index, self.cols)
        r2, c2 = divmod(blank, self.cols)
        if abs(r1-r2) + abs(c1-c2) != 1:
            return
        self.sliding_order[blank], self.sliding_order[index] = self.sliding_order[index], self.sliding_order[blank]
        self.moves += 1
        if self.sliding_order == list(range(1, self.rows*self.cols)) + [0]:
            self.elapsed = int(time.time() - self.started) if self.started else 0
            self.started = None
            self.message = "恭喜！滑块拼图完成！"

    def board_piece_rect(self, piece):
        cell_w = 600 // self.cols
        cell_h = 600 // self.rows
        tab = piece["tab"]
        return pygame.Rect(BOARD.x + 30 + piece["col"] * cell_w - tab,
                           BOARD.y + 30 + piece["row"] * cell_h - tab,
                           piece["w"], piece["h"])

    def draw(self):
        self.screen.fill(BG)
        title = self.big.render("拼图工坊", True, WHITE)
        self.screen.blit(title, (26, 22))
        subtitle = self.small.render("把喜欢的图片，变成一场拼图挑战", True, MUTED)
        self.screen.blit(subtitle, (185, 34))
        pygame.draw.rect(self.screen, PANEL_BG, BOARD, border_radius=16)
        pygame.draw.rect(self.screen, PANEL_BG, PANEL, border_radius=16)
        pygame.draw.rect(self.screen, (65, 78, 103), BOARD, 1, border_radius=16)
        pygame.draw.rect(self.screen, (65, 78, 103), PANEL, 1, border_radius=16)

        board_area = pygame.Rect(BOARD.x + 30, BOARD.y + 30, 600, 600)
        if self.image:
            pygame.draw.rect(self.screen, (12, 16, 25), board_area)
            cell_w, cell_h = 600 // self.cols, 600 // self.rows
            for row in range(self.rows):
                for col in range(self.cols):
                    rect = pygame.Rect(board_area.x + col * cell_w, board_area.y + row * cell_h, cell_w, cell_h)
                    pygame.draw.rect(self.screen, (48, 58, 78), rect, 1)
            if self.mode == "slide":
                for slot, tile_id in enumerate(self.sliding_order):
                    if tile_id == 0:
                        continue
                    rr, cc = divmod(slot, self.cols)
                    src_r, src_c = divmod(tile_id - 1, self.cols)
                    x0, y0 = src_c * cell_w, src_r * cell_h
                    crop = self.preview_image.subsurface(pygame.Rect(x0, y0, cell_w, cell_h))
                    dest = pygame.Rect(board_area.x + cc * cell_w, board_area.y + rr * cell_h, cell_w, cell_h)
                    self.screen.blit(crop, dest)
                    pygame.draw.rect(self.screen, (220, 230, 246), dest, 2)
            elif self.show_preview:
                preview = pygame.transform.smoothscale(self.preview_image, (600, 600))
                preview.set_alpha(75)
                self.screen.blit(preview, board_area)
            if self.mode == "drag":
              for piece in self.pieces:
                if piece["placed"]:
                    rect = self.board_piece_rect(piece)
                    self.screen.blit(piece["surface"], rect)
                    pygame.draw.rect(self.screen, (220, 230, 246), rect, 1)
            if self.dragging:
                p = self.dragging
                self.screen.blit(p["surface"], (p["x"], p["y"]))
        else:
            text = self.font.render("请先选择图片", True, MUTED)
            self.screen.blit(text, text.get_rect(center=board_area.center))

        self.screen.blit(self.font.render("参考图", True, WHITE), (735, 102))
        if self.image:
            self.screen.blit(self.reference_thumb, (950, 98))
            pygame.draw.rect(self.screen, (215, 225, 242), pygame.Rect(950, 98, 112, 112), 1)
        self.screen.blit(self.font.render("拼块区" if self.mode == "drag" else "滑块模式", True, WHITE), (735, 225))
        self.screen.blit(self.small.render("拖动拼块到左侧" if self.mode == "drag" else "点击空格旁边的拼块移动", True, MUTED), (735, 255))
        for piece in self.pieces if self.mode == "drag" else []:
            if piece["placed"] or piece is self.dragging:
                continue
            self.screen.blit(piece["thumb"], (piece["tx"], piece["ty"]))
        if self.dragging:
            piece = self.dragging
            self.screen.blit(piece["surface"], (piece["x"], piece["y"]))
            pygame.draw.rect(self.screen, (255, 255, 255),
                             pygame.Rect(piece["x"], piece["y"], piece["w"], piece["h"]), 2)

        elapsed = int(time.time() - self.started) if self.started else self.elapsed
        stats = f"难度：{self.rows} × {self.cols}     步数：{self.moves}     用时：{elapsed // 60:02d}:{elapsed % 60:02d}"
        self.screen.blit(self.small.render(stats, True, WHITE), (735, 575))
        self.screen.blit(self.small.render(self.message, True, ACCENT), (735, 608))
        self.make_button("image", pygame.Rect(735, 680, 104, 42), "选择图片")
        self.make_button("easy", pygame.Rect(850, 680, 72, 42), "3×3")
        self.make_button("medium", pygame.Rect(930, 680, 72, 42), "4×4")
        self.make_button("hard", pygame.Rect(1010, 680, 72, 42), "5×5")
        self.make_button("shuffle", pygame.Rect(735, 630, 104, 38), "重新打乱", bool(self.image))
        self.make_button("preview", pygame.Rect(850, 630, 104, 38), "参考图提示", bool(self.image))
        self.make_button("mode", pygame.Rect(965, 630, 117, 38), "切换：滑块" if self.mode == "drag" else "切换：拖放", bool(self.image))
        pygame.display.flip()

    def handle_click(self, pos):
        for name, rect in self.buttons.items():
            if not rect.collidepoint(pos):
                continue
            if name == "image":
                path = choose_image()
                if path:
                    self.new_game(path)
            elif name in ("easy", "medium", "hard"):
                self.rows = self.cols = {"easy": 3, "medium": 4, "hard": 5}[name]
                if self.image:
                    self.new_game(None)
            elif name == "shuffle" and self.image:
                self.new_game(None)
            elif name == "preview" and self.image:
                self.show_preview = not self.show_preview
            elif name == "mode" and self.image:
                self.mode = "slide" if self.mode == "drag" else "drag"
                self.new_game(None)
            return True
        return False

    def run(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.handle_click(event.pos):
                        continue
                    if self.mode == "slide" and self.image:
                        board_area = pygame.Rect(BOARD.x + 30, BOARD.y + 30, 600, 600)
                        if board_area.collidepoint(event.pos):
                            cell_w, cell_h = 600 // self.cols, 600 // self.rows
                            cc = min(self.cols - 1, max(0, (event.pos[0] - board_area.x) // cell_w))
                            rr = min(self.rows - 1, max(0, (event.pos[1] - board_area.y) // cell_h))
                            self.slide_tile(rr * self.cols + cc)
                        continue
                    for piece in reversed(self.pieces):
                        if piece["placed"]:
                            continue
                        rect = pygame.Rect(piece["tx"], piece["ty"], piece["thumb_size"], piece["thumb_size"])
                        if rect.collidepoint(event.pos):
                            self.dragging = piece
                            self.drag_offset = (piece["w"] // 2, piece["h"] // 2)
                            piece["x"] = event.pos[0] - self.drag_offset[0]
                            piece["y"] = event.pos[1] - self.drag_offset[1]
                            break
                elif event.type == pygame.MOUSEMOTION and self.dragging and self.mode == "drag":
                    self.dragging["x"] = event.pos[0] - self.drag_offset[0]
                    self.dragging["y"] = event.pos[1] - self.drag_offset[1]
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging and self.mode == "drag":
                    piece = self.dragging
                    target = self.board_piece_rect(piece)
                    current = pygame.Rect(piece["x"], piece["y"], piece["w"], piece["h"])
                    snap_distance = max(42, min(piece["w"], piece["h"]) * 0.32)
                    if target.colliderect(BOARD) and math.dist(current.center, target.center) < snap_distance:
                        piece["x"], piece["y"] = target.topleft
                        piece["placed"] = True
                        self.moves += 1
                        if all(p["placed"] for p in self.pieces):
                            self.elapsed = int(time.time() - self.started) if self.started else 0
                            self.started = None
                            self.message = "恭喜！拼图完成！你真棒！"
                    self.dragging = None
            self.draw()
            self.clock.tick(60)
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    PuzzleGame().run()
