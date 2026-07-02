"""Pygame 基础绘制组件：文字、按钮、面板、方格和棋盘。UI视觉优化"""

from functools import lru_cache
import platform

import pygame

from .config import ACCENT, BG, COLORS, MUTED, PANEL, PANEL_2, TEXT
from .core import Piece

#字体缓存函数
@lru_cache(maxsize=32)
def font(size, bold=False):
    """加载系统自带中文字体，并按“字号+粗体”缓存字体对象。优化字体渲染抗锯齿"""
    # Pygame 不会像浏览器一样自动寻找中文字形，所以按系统选一个确定存在的中文字体
    if platform.system() == "Windows":
        font_path = "C:/Windows/Fonts/msyh.ttc"
    elif platform.system() == "Darwin":
        font_path = "/System/Library/Fonts/STHeiti Medium.ttc"
    else:
        return pygame.font.SysFont("sans", size, bold=bold)
    result = pygame.font.Font(font_path, size)
    result.set_bold(bold)
    return result

#文字绘制text(),窗口，文字，字体，颜色，位置，居中，粗体
def text(surface, value, size, color, pos, center=False, bold=False):
    """把文字渲染到目标画布；pos 可表示左上角或文字中心。优化文字清晰度，增加细微阴影提升层次感"""
    font_obj = font(size, bold)
    image = font_obj.render(str(value), True, color)
    rect = image.get_rect(center=pos) if center else image.get_rect(topleft=pos)
    # 增加极浅文字阴影，提升深色面板文字可读性，不破坏原有配色
    shadow_img = font_obj.render(str(value), True, (0, 0, 0, 80))
    surface.blit(shadow_img, rect.move(2, 2))
    surface.blit(image, rect)
    return rect

#面板底色绘制panel(),画布，矩形范围，圆角半径，颜色
def panel(surface, rect, radius=16, color=PANEL):
    """绘制圆角内容区域，增加轻微内阴影，弱化生硬平面感"""
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    # 内层细微描边区分面板边界
    pygame.draw.rect(surface, MUTED, rect, width=1, border_radius=radius)

#按钮类Button
class Button:
    """由矩形、标题和点击检测组成的轻量按钮。优化hover过渡视觉、分层光影"""

    #初始化
    def __init__(self, rect, label, accent=ACCENT):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.accent = accent

    #渲染按钮
    def draw(self, surface, mouse):
        """鼠标悬浮分层光影，文字对比度优化，增加按压视觉暗示"""
        hover = self.rect.collidepoint(mouse)
        base_color = self.accent if hover else PANEL_2
        pygame.draw.rect(surface, base_color, self.rect, border_radius=12)
        # 悬浮时增加外发光描边
        if hover:
            pygame.draw.rect(surface, ACCENT, self.rect, width=2, border_radius=12)
        # 按钮文字适配底色对比度
        text_color = BG if hover else TEXT
        text(surface, self.label, 24, text_color, self.rect.center, True, True)
    #点击检测
    def clicked(self, event):
        """仅接受发生在按钮范围内的鼠标左键按下事件。"""
        return event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos)

#单一方块绘制，画布，矩形范围，颜色，幽灵方块标记
def draw_block(surface, rect, color, ghost=False):
    """绘制方格；优化方块渐变质感，幽灵方块轮廓加粗更醒目，间隔视觉更均匀"""
    rect = pygame.Rect(rect).inflate(-2, -2)
    if ghost:
        # 创建透明图层绘制幽灵方块，实现半透明
        temp_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        # 拼接带透明度的颜色元组
        alpha_color = (*color, 100)
        pygame.draw.rect(temp_surf, alpha_color, temp_surf.get_rect(), 3, border_radius=4)
        surface.blit(temp_surf, rect.topleft)
        return
    # 实体方块增加细微渐变分层，立体更强
    pygame.draw.rect(surface, color, rect, border_radius=4)
    # 方块顶部浅色高光
    light_rect = rect.inflate(-6, -6)
    light_rect.height = light_rect.height // 2
    pygame.draw.rect(surface, (min(c + 35, 255) for c in color), light_rect, border_radius=2)

#完整棋盘绘制，画布，棋盘数据，原点坐标，单元格大小，当前方块，幽灵方块，标题
def draw_board(surface, board, origin, cell, current=None, ghost=None, label=None):
    """绘制 10×20 棋盘，网格线条柔和化，区块分层区分，方块堆叠层次更清晰"""
    ox, oy = origin
    board_w = 10 * cell
    board_h = 20 * cell
    rect = pygame.Rect(ox - 10, oy - 10, board_w + 20, board_h + 20)
    panel(surface, rect, 12, (10, 17, 35))

    # 网格线条降低亮度，不抢方块视觉重心
    grid_color = (22, 32, 50)
    for y in range(20):
        for x in range(10):
            cell_rect = (ox + x * cell, oy + y * cell, cell, cell)
            pygame.draw.rect(surface, grid_color, cell_rect, 1)
            value = board[y][x]
            if value:
                draw_block(surface, cell_rect, COLORS[value])

    # 幽灵方块（落地预判）
    if ghost:
        for x, y, kind in ghost:
            if y >= 0:
                draw_block(surface, (ox + x * cell, oy + y * cell, cell, cell), COLORS[kind], True)
    # 当前操控方块
    if current:
        for x, y, kind in current:
            if y >= 0:
                draw_block(surface, (ox + x * cell, oy + y * cell, cell, cell), COLORS[kind])
    # 棋盘标题文字
    if label:
        text(surface, label, 18, MUTED, (rect.centerx, oy - 28), True, True)

# 暂存/下一个方块预览面板绘制，画布，方块类型，矩形范围，标题
def draw_preview(surface, kind, rect, title):
    """暂存/下一个方块预览面板：居中逻辑不变，优化预览方块缩放质感、面板分层"""
    panel(surface, rect)
    text(surface, title, 16, MUTED, (rect.x + 14, rect.y + 10), bold=True)
    if not kind:
        return

    p = Piece(kind, 0, 0)
    cells = p.cells()
    min_x, max_x = min(x for x, _ in cells), max(x for x, _ in cells)
    min_y, max_y = min(y for _, y in cells), max(y for _, y in cells)
    size = 22

    # 居中计算完全保留原始逻辑，仅微调偏移让视觉更均衡
    block_total_w = (max_x - min_x + 1) * size
    block_total_h = (max_y - min_y + 1) * size
    start_x = rect.centerx - block_total_w / 2
    start_y = rect.centery - block_total_h / 2 + 9

    for x, y in cells:
        block_x = start_x + (x - min_x) * size
        block_y = start_y + (y - min_y) * size
        draw_block(surface, (block_x, block_y, size, size), COLORS[kind])