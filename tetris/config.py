WIDTH, HEIGHT = 1100, 760
FPS = 60

# 标准俄罗斯方块棋盘为 10 列、20 行；CELL 是单机棋盘每格像素数。
COLS, ROWS = 10, 20
CELL = 30
BOARD_W, BOARD_H = COLS * CELL, ROWS * CELL

# UI颜色
BG = (8, 12, 27)
PANEL = (17, 25, 48)
PANEL_2 = (24, 35, 65)
TEXT = (232, 241, 255)
MUTED = (127, 148, 184)
ACCENT = (56, 220, 255)
PINK = (255, 72, 180)
GREEN = (76, 235, 170)
RED = (255, 88, 100)

# 俄罗斯方块七种形状的颜色
COLORS = {
    "I": (52, 214, 255), "O": (255, 218, 73), "T": (183, 95, 255),
    "S": (81, 224, 118), "Z": (255, 86, 98), "J": (76, 122, 255),
    "L": (255, 156, 65),
}

#UDP和TCP的端口

DISCOVERY_PORT =45678
GAME_PORT=45679
MATCH_SECONDS=60