"""Pygame 应用层：把规则、界面和网络组织成可切换的游戏场景。"""
from __future__ import annotations
import socket
import threading
import time
import pygame
from ..config import (ACCENT, BG, CELL, FPS, GREEN, HEIGHT, MATCH_SECONDS,
                     MUTED, PANEL, PINK, RED, TEXT, WIDTH)
from .core import TetrisGame
from .network import LanSession
from .ui import Button, draw_board, draw_preview, panel, text

# ========= 提取全局魔法数字常量（优化点1：消除硬编码数字，统一管理） =========
# 菜单按钮尺寸
BTN_W_MENU = 360
BTN_H_MENU_LG = 70
BTN_H_MENU_SM = 60
# 大厅按钮尺寸
LOBBY_BTN_W = 260
LOBBY_BTN_H = 62
LOBBY_BTN_WIDE_W = 370
LOBBY_BTN_WIDE_H = 64
# 输入框尺寸
INPUT_BOX_W = 260
INPUT_BOX_H = 42
# 遮罩弹窗尺寸
OVERLAY_W = 460
OVERLAY_H = 200
OVERLAY_OFFSET_Y = 100
# 刷新同步间隔
SYNC_INTERVAL = 0.08
# 对战超时等待
WAIT_OPPONENT_TIMEOUT = 2.0
# 文本字号常量
FONT_H1 = 52
FONT_H2 = 46
FONT_H3 = 30
FONT_NORMAL = 20
FONT_SMALL = 16
FONT_INPUT = 19
FONT_SCORE_BIG = 35
FONT_TIMER = 60
# 坐标偏移常量
GHOST_Y_OFFSET = 0.999
CURSOR_BLINK_CYCLE = 2
TEXT_INPUT_MAX_LEN = 15

class TetrisApp:
    """程序控制器：管理场景、输入、绘制以及局域网比赛流程。"""
    def __init__(self):
        # Pygame 窗口、时钟、场景状态
        pygame.init()
        pygame.display.set_caption("俄罗斯方块：局域网对战")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.running = True
        self.scene = "menu"
        self.game: TetrisGame | None = None
        # 网络对战相关
        self.session = LanSession()
        self.remote: dict | None = None
        self.match_start: float | None = None
        self.match_finished = False
        self.result = ""
        # IP输入框状态
        self.address = ""
        self.address_active = False
        self.discovery_status = ""
        self.last_sync = 0.0
        self.local_final_sent = False
        self.remote_final_score: int | None = None
        self.finish_wait_started: float | None = None

    def run(self):
        """运行固定帧率主循环，异常统一释放资源"""
        try:
            while self.running:
                dt = min(self.clock.tick(FPS) / 1000, 0.05)
                events = pygame.event.get()
                self.handle_global(events)
                # 场景分发（简化if分支结构，无逻辑改动）
                scene_handler = {
                    "menu": self.menu,
                    "single": lambda ev: self.play(ev, dt, False),
                    "network": self.network_lobby,
                    "battle": lambda ev: self.play(ev, dt, True)
                }
                if self.scene in scene_handler:
                    scene_handler[self.scene](events)
                pygame.display.flip()
        finally:
            self.session.close()
            pygame.quit()

    def handle_global(self, events):
        """全局统一事件：窗口关闭"""
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False

    def background(self):
        """全局填充背景底色"""
        self.screen.fill(BG)

    def _draw_menu_buttons(self, mouse_pos):
        """【封装重复代码】菜单三个按钮创建+绘制，无业务改动"""
        mid_x = WIDTH // 2
        single_btn = Button((mid_x - BTN_W_MENU//2, 310, BTN_W_MENU, BTN_H_MENU_LG), "单机模式")
        net_btn = Button((mid_x - BTN_W_MENU//2, 405, BTN_W_MENU, BTN_H_MENU_LG), "联机模式", PINK)
        quit_btn = Button((mid_x - BTN_W_MENU//2, 500, BTN_W_MENU, BTN_H_MENU_SM), "退出游戏", RED)
        btn_list = [single_btn, net_btn, quit_btn]
        for btn in btn_list:
            btn.draw(self.screen, mouse_pos)
        return btn_list

    def menu(self, events):
        """主菜单界面渲染与交互"""
        self.background()
        mid_x = WIDTH // 2
        # 标题文本
        text(self.screen, "俄罗斯方块", FONT_H1, TEXT, (mid_x, 155), True, True)
        text(self.screen, "单机游戏与局域网对战", FONT_NORMAL, MUTED, (mid_x, 220), True)
        # 绘制按钮
        mouse_pos = pygame.mouse.get_pos()
        single, network, quit_btn = self._draw_menu_buttons(mouse_pos)
        # 按钮点击判断
        for event in events:
            if single.clicked(event):
                self.start_single()
            elif network.clicked(event):
                self.scene = "network"
            elif quit_btn.clicked(event):
                self.running = False
        # 底部操作提示
        text(self.screen, "方向键移动  Z/X旋转  空格硬降  C暂存  P暂停", FONT_SMALL, MUTED, (mid_x, 635), True)

    def start_single(self):
        """初始化单机对局"""
        self.game = TetrisGame()
        self.scene = "single"

    def _create_lobby_buttons(self, mouse_pos):
        """【封装重复代码】联机大厅按钮批量创建绘制"""
        host_btn = Button((265, 205, LOBBY_BTN_W, LOBBY_BTN_H), "创建房间", ACCENT)
        search_btn = Button((575, 205, LOBBY_BTN_W, LOBBY_BTN_H), "搜索局域网", PINK)
        connect_btn = Button((575, 370, LOBBY_BTN_W, LOBBY_BTN_H), "连接 IP", GREEN)
        start_btn = Button((365, 500, LOBBY_BTN_WIDE_W, LOBBY_BTN_WIDE_H), "开始 60 秒对战", GREEN)
        back_btn = Button((40, 40, 120, 48), "返回", RED)
        base_btns = [host_btn, search_btn, connect_btn, back_btn]
        for btn in base_btns:
            btn.draw(self.screen, mouse_pos)
        draw_start = False
        if self.session.is_host and self.session.connected:
            start_btn.draw(self.screen, mouse_pos)
            draw_start = True
        return base_btns, start_btn if draw_start else None

    def network_lobby(self, events):
        """局域网大厅界面、房间创建/搜索/连接逻辑"""
        self.background()
        mid_x = WIDTH // 2
        text(self.screen, "局域网对战", FONT_H2, TEXT, (mid_x, 80), True, True)
        panel(self.screen, pygame.Rect(205, 140, 690, 500))
        mouse_pos = pygame.mouse.get_pos()
        base_btns, start_btn = self._create_lobby_buttons(mouse_pos)
        host, search, connect, back = base_btns
        # IP输入框绘制
        addr_rect = pygame.Rect(575, 326, INPUT_BOX_W, INPUT_BOX_H)
        pygame.draw.rect(self.screen, (10, 17, 35), addr_rect, border_radius=8)
        border_color = ACCENT if self.address_active else MUTED
        border_width = 2 if self.address_active else 1
        pygame.draw.rect(self.screen, border_color, addr_rect, border_width, border_radius=8)
        # 输入框文字
        display_text = self.address if self.address else "输入 IPv4 地址"
        text_color = TEXT if self.address else MUTED
        value_rect = text(self.screen, display_text, FONT_INPUT, text_color, (590, 335))
        # 闪烁光标
        if self.address_active and int(time.monotonic() * CURSOR_BLINK_CYCLE) % 2 == 0:
            cursor_x = min(value_rect.right + 2, addr_rect.right - 8)
            pygame.draw.line(self.screen, TEXT, (cursor_x, 334), (cursor_x, 359), 2)
        # 状态文本
        text(self.screen, "主机地址", 17, MUTED, (575, 300))
        text(self.screen, self.session.status, FONT_NORMAL, ACCENT, (mid_x, 458), True)
        if self.discovery_status:
            text(self.screen, self.discovery_status, FONT_SMALL, MUTED, (mid_x, 590), True)
        # 事件处理
        for event in events:
            # 鼠标点击切换输入框焦点
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.address_active = addr_rect.collidepoint(event.pos)
                if self.address_active:
                    pygame.key.start_text_input()
                    pygame.key.set_text_input_rect(addr_rect)
                else:
                    pygame.key.stop_text_input()
            # 键盘输入处理
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.leave_network()
                elif self.address_active:
                    if event.key == pygame.K_BACKSPACE:
                        self.address = self.address[:-1]
                    elif event.unicode and event.unicode in "0123456789.":
                        self.address = (self.address + event.unicode)[:TEXT_INPUT_MAX_LEN]
            # 按钮点击分发
            if back.clicked(event):
                self.leave_network()
            elif host.clicked(event):
                self.session.host(socket.gethostname())
            elif connect.clicked(event) and self.address:
                self.session.connect(self.address, socket.gethostname())
            elif search.clicked(event):
                self.discovery_status = "正在搜索房间..."
                threading.Thread(target=self._discover, args=(self.session,), daemon=True).start()
            elif start_btn and start_btn.clicked(event) and self.session.is_host and self.session.connected:
                delay = 1.5
                self.session.send({"type": "start", "delay": delay})
                self.start_battle(time.monotonic() + delay)
        # 处理网络推送消息
        for msg in self.session.poll():
            msg_type = msg.get("type")
            if msg_type == "start":
                delay = max(0.0, float(msg.get("delay", 0.0)))
                self.start_battle(time.monotonic() + delay)
                return
            if msg_type in ("disconnect", "error"):
                self.discovery_status = msg.get("message", "连接断开")

    def _discover(self, session: LanSession):
        """后台线程搜索局域网房间，不阻塞UI"""
        rooms = LanSession.discover()
        if self.scene != "network" or self.session is not session:
            return
        if rooms:
            ip, name = rooms[0]
            self.address = ip
            self.discovery_status = f"发现 {name}（{ip}），正在连接"
            self.session.connect(ip, socket.gethostname())
        else:
            self.discovery_status = "未找到房间，可手动输入主机 IP"

    def start_battle(self, start_at: float):
        """初始化对战对局状态"""
        self.game = TetrisGame()
        self.remote = {
            "board": [[""] * 10 for _ in range(20)],
            "score": 0,
            "lines": 0,
            "level": 1,
            "game_over": False
        }
        self.match_start = start_at
        self.match_finished = False
        self.result = ""
        self.local_final_sent = False
        self.remote_final_score = None
        self.finish_wait_started = None
        self.last_sync = 0.0
        self.address_active = False
        pygame.key.stop_text_input()
        self.scene = "battle"

    def leave_network(self):
        """关闭网络会话，清空输入状态返回菜单"""
        self.session.close()
        self.session = LanSession()
        self.address_active = False
        pygame.key.stop_text_input()
        self.scene = "menu"

    def input_game(self, events, battle: bool):
        """统一键盘输入映射到核心游戏逻辑"""
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            if event.key == pygame.K_ESCAPE:
                self.leave_network() if battle else setattr(self, "scene", "menu")
                return
            if event.key == pygame.K_p and not battle:
                self.game.paused = not self.game.paused
            if self.match_finished:
                if event.key == pygame.K_RETURN:
                    if battle:
                        self.leave_network()
                    else:
                        self.start_single()
                continue
            # 方向与操作映射
            key_map = {
                pygame.K_LEFT: lambda: self.game.move(-1, 0),
                pygame.K_RIGHT: lambda: self.game.move(1, 0),
                pygame.K_DOWN: self.game.soft_drop,
                pygame.K_UP: lambda: self.game.rotate(1),
                pygame.K_x: lambda: self.game.rotate(1),
                pygame.K_z: lambda: self.game.rotate(-1),
                pygame.K_SPACE: self.game.hard_drop,
                pygame.K_c: self.game.swap_hold
            }
            if event.key in key_map:
                key_map[event.key]()

    def play(self, events, dt: float, battle: bool):
        """单机/对战共用帧更新、渲染入口"""
        self.input_game(events, battle)
        if self.scene not in ("single", "battle"):
            return
        now = time.monotonic()
        # 倒计时与剩余时间计算
        countdown = max(0, self.match_start - now) if battle else 0
        remaining = max(0, MATCH_SECONDS - (now - self.match_start)) if battle else 0
        active = not battle or (countdown <= 0 and remaining > 0 and not self.match_finished)
        if active:
            self.game.update(dt)
        if battle:
            self.network_update(now, remaining)
        self.draw_game(battle, countdown, remaining)

    def network_update(self, now: float, remaining: float):
        """对战网络同步、分数结算逻辑"""
        # 接收对手消息
        for msg in self.session.poll():
            msg_type = msg.get("type")
            if msg_type == "state":
                self.remote = msg["data"]
            elif msg_type == "final":
                self.remote_final_score = int(msg.get("score", 0))
            elif msg_type == "disconnect":
                self.match_finished = True
                self.result = "对手已断开连接"
        # 定时同步本地状态
        if remaining > 0 and now - self.last_sync >= SYNC_INTERVAL:
            self.session.send({"type": "state", "data": self.game.snapshot()})
            self.last_sync = now
        # 比赛结束结算
        if remaining <= 0 and not self.match_finished:
            if not self.local_final_sent:
                self.session.send({"type": "final", "score": self.game.score})
                self.local_final_sent = True
                self.finish_wait_started = now
            # 等待对手分数，超时兜底
            timeout = now - self.finish_wait_started >= WAIT_OPPONENT_TIMEOUT
            if self.remote_final_score is None and not timeout:
                return
            self.match_finished = True
            opp_score = self.remote_final_score if self.remote_final_score is not None else self.remote.get("score", 0)
            if self.game.score > opp_score:
                self.result = "胜利！"
            elif self.game.score < opp_score:
                self.result = "惜败"
            else:
                self.result = "平局"

    def draw_game(self, battle: bool, countdown: float, remaining: float):
        """游戏画面总渲染分发"""
        self.background()
        if battle:
            self.draw_battle(countdown, remaining)
        else:
            self.draw_single()
        # 覆盖弹窗
        if self.game.paused:
            self.overlay("已暂停", "按 P 继续")
        elif self.game.game_over and not battle:
            self.overlay("游戏结束", f"最终得分 {self.game.score} · Esc 返回")
        if self.match_finished:
            opp_score = self.remote_final_score if self.remote_final_score is not None else self.remote.get("score", 0)
            self.overlay(self.result, f"你 {self.game.score} : {opp_score} 对手 · Enter 返回")

    def current_cells(self):
        """获取当前方块坐标类型列表，供给UI绘制"""
        return [(x, y, self.game.current.kind) for x, y in self.game.current.cells()]

    def ghost_cells(self):
        """获取幽灵下落预览方块坐标"""
        ghost_y = self.game.ghost_y()
        return [(x, y, self.game.current.kind) for x, y in self.game.current.cells(y=ghost_y)]

    def draw_single(self):
        """单机界面绘制：棋盘、暂存、下一个、数据面板"""
        text(self.screen, "单机模式", FONT_H3, TEXT, (55, 28), bold=True)
        draw_board(self.screen, self.game.board, (235, 90), CELL, self.current_cells(), self.ghost_cells())
        draw_preview(self.screen, self.game.hold, pygame.Rect(55, 120, 140, 130), "暂存  C")
        draw_preview(self.screen, self.game.queue[0], pygame.Rect(575, 120, 155, 130), "下一个")
        panel(self.screen, pygame.Rect(575, 280, 210, 250))
        # 统计数据批量渲染
        stat_list = [
            ("分数", self.game.score, ACCENT),
            ("消行", self.game.lines, TEXT),
            ("等级", self.game.level, PINK),
            ("连击", max(0, self.game.combo), GREEN)
        ]
        base_y = 300
        line_step = 55
        for idx, (name, val, color) in enumerate(stat_list):
            y = base_y + idx * line_step
            text(self.screen, name, 16, MUTED, (600, y))
            text(self.screen, val, FONT_SCORE_BIG, color, (755, y - 5), center=True, bold=True)
        text(self.screen, "Esc 返回  ·  P 暂停", FONT_SMALL, MUTED, (575, 565))

    def draw_battle(self, countdown: float, remaining: float):
        """对战双棋盘、倒计时、双方分数渲染"""
        local_cell_size, remote_cell_size = 26, 22
        base_x, base_y = 135, 110
        draw_board(self.screen, self.game.board, (base_x, base_y), local_cell_size,
                   self.current_cells(), self.ghost_cells(), "你")
        # 对手棋盘
        remote_board = self.remote["board"] if self.remote else [[""] * 10 for _ in range(20)]
        draw_board(self.screen, remote_board, (745, 150), remote_cell_size, label=self.session.peer_name)
        mid_x = WIDTH // 2
        text(self.screen, "60 秒计分对战", 27, TEXT, (mid_x, 36), True, True)
        # 倒计时数字
        show_sec = MATCH_SECONDS if countdown > 0 else int(remaining + GHOST_Y_OFFSET)
        timer_color = RED if show_sec <= 10 else ACCENT
        text(self.screen, f"{show_sec:02d}", FONT_TIMER, timer_color, (mid_x, 120), True, True)
        # 双方分数文本
        score_y_base = 210
        text(self.screen, "你的分数", 15, MUTED, (515, score_y_base), True)
        text(self.screen, self.game.score, FONT_SCORE_BIG, ACCENT, (515, score_y_base + 35), True, True)
        text(self.screen, "对手分数", 15, MUTED, (515, score_y_base + 110), True)
        opp_score = self.remote.get("score", 0) if self.remote else 0
        text(self.screen, opp_score, FONT_SCORE_BIG, PINK, (515, score_y_base + 145), True, True)
        # 开局倒计时弹窗
        if countdown > 0:
            self.overlay(str(max(1, int(countdown + GHOST_Y_OFFSET))), "准备")

    def overlay(self, title: str, subtitle: str):
        """全局半透明弹窗（暂停/结算/开局倒计时共用）"""
        # 全屏遮罩
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((3, 7, 18, 185))
        self.screen.blit(shade, (0, 0))
        # 居中弹窗面板
        popup_rect = pygame.Rect(
            WIDTH//2 - OVERLAY_W//2,
            HEIGHT//2 - OVERLAY_OFFSET_Y,
            OVERLAY_W,
            OVERLAY_H
        )
        panel(self.screen, popup_rect)
        mid_x = WIDTH // 2
        mid_y = HEIGHT // 2
        text(self.screen, title, 46, ACCENT, (mid_x, mid_y - 25), True, True)
        text(self.screen, subtitle, 18, TEXT, (mid_x, mid_y + 42), True)