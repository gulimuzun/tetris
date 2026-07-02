import random
from dataclasses import dataclass
from config import COLS, ROWS

#字典
SHAPES = {
    "I": ("....", "IIII", "....", "...."),
    "O": (".OO.", ".OO.", "....", "...."),
    "T": (".T..", "TTT.", "....", "...."),
    "S": (".SS.", "SS..", "....", "...."),
    "Z": ("ZZ..", ".ZZ.", "....", "...."),
    "J": ("J...", "JJJ.", "....", "...."),
    "L": ("..L.", "LLL.", "....", "...."),
}

#方块的随机生成器
class Bag:
    def __init__(self,seed=None):
        self.random = random.Random(seed)
        self.items: list[str] = []

    def pop(self):
        if not self.items:
            self.items = list(SHAPES)
            self.random.shuffle(self.items)
        return self.items.pop()

def rotate_cells(cells: list[tuple[int, int]], turns: int) -> list[tuple[int, int]]:
    """在 4×4 模板内顺时针旋转 turns 次，返回方块相对坐标的列表"""
    result = cells
    for _ in range(turns % 4):
        result = [(3 - y, x) for x, y in result]
    return result

@dataclass
class Piece:
    kind: str
    x: int = 3  #是把 4×4 模板的 (0,0) 点 放在棋盘 (3, -1) 位置
    y: int = -1
    rotation: int = 0

    #返回绝对坐标  
    def cells(self, x=None, y=None, rotation=None):
        px = self.x if x is None else x
        py = self.y if y is None else y
        r = self.rotation if rotation is None else rotation

        # 从 4×4 字符模板中提取有方块的位置
        base = []
        for cy, row in enumerate(SHAPES[self.kind]):
            for cx, char in enumerate(row):
                if char != ".":
                    base.append((cx, cy))

        # 旋转后平移到棋盘坐标
        result = []
        for cx, cy in rotate_cells(base, r):
            result.append((px + cx, py + cy))
        return result

class ScoreSystem:
    #消行数对应的基础分
    CLEAR_POINTS={1:100,2:200,3:500,4:800}

    def __init__(self):
        self.score=0 #当前总分
        self.lines=0 #当前消行
        self.level=1 #当前等级
        self.combo=-1 #当前连击
    def award_soft_drop(self,distance=1):
        #软降每格加一分
        self.score+=max(0,distance)
    def award_hard_drop(self,distance):
        #软降每格加一分
        self.score+=max(0,distance)*2
    def apply_line_clear(self,count):
        #消行之后，更新对应的分数和状态
        if count<=0 :
            self.combo=-1
            return 0
        self.lines+=count
        self.combo+=1
        self.level=self.lines//10 +1
        cur_points=self.CLEAR_POINTS[count]*self.level+max(0,self.level)*50
        self.score+=cur_points
        return cur_points
class TetrisGame:
    # 简化墙踢：原地旋转失败后，依次尝试水平或向上偏移。
    KICKS = [(0, 0), (-1, 0), (1, 0), (-2, 0), (2, 0), (0, -1)]

    def __init__(self, seed=None):
        # board 只保存已经锁定的格子；当前方块单独保存在 current。
        self.bag = Bag(seed)
        self.board = [[None for _ in range(COLS)] for _ in range(ROWS)]

        self.queue = [self.bag.pop() for _ in range(5)]
        self.current = Piece(self.queue.pop(0))
        self.queue.append(self.bag.pop())

        self.hold: str | None = None
        self.can_hold = True
        self.scoring = ScoreSystem()
        self.game_over = False
        self.paused = False
        self.fall_timer = 0.0
        self.lock_timer = 0.0 #方块底部碰东西后开始计时，满 0.5 秒就锁定，水平移动会把计时清零，所以你可以一直平移来拖延锁定

    @property
    def fall_interval(self):
        return max(0.07, 0.8 * (0.86 ** (self.level - 1)))
    
    # 保留这些只读属性，让 UI 和网络无需知道计分器的内部结构。
    @property
    def score(self):
        return self.scoring.score

    @property
    def lines(self):
        return self.scoring.lines

    @property
    def level(self):
        return self.scoring.level

    @property
    def combo(self):
        return self.scoring.combo

    #检验左右边界（0到COL）下边界（ROW）和方块碰撞（位置重叠）
    def valid(self, piece=None, x=None, y=None, rotation=None):
        piece = piece or self.current
        for cx, cy in piece.cells(x, y, rotation):
            if cx < 0 or cx >= COLS or cy >= ROWS:
                return False
            if cy >= 0 and self.board[cy][cx] is not None:
                return False
        return True

    #方块自动下落或玩家主动下移时的平移
    def move(self, dx, dy):
        if self.game_over or self.paused:
            return False
        if self.valid(x=self.current.x + dx, y=self.current.y + dy):
            self.current.x += dx
            self.current.y += dy
            if dx:
                self.lock_timer = 0
            return True
        return False

    def rotate(self, direction=1): #1顺时针-1逆时针
        if self.game_over or self.paused or self.current.kind == "O": #正方形不用真转
            return False
        target = (self.current.rotation + direction) % 4
        for dx, dy in self.KICKS:
            if self.valid(x=self.current.x + dx, y=self.current.y + dy, rotation=target):
                self.current.x += dx
                self.current.y += dy
                self.current.rotation = target
                self.lock_timer = 0
                return True
        return False

    #主动下降👇＋1分
    def soft_drop(self):
        if self.move(0, 1):
            self.scoring.award_soft_drop()
            return True
        return False

    def ghost_y(self):
        """返回当前方块不发生碰撞时能够到达的最低 y 坐标。"""
        y = self.current.y
        while self.valid(y=y + 1):
            y += 1
        return y
    
    def hard_drop(self):
        """直接沉底每格+2分同时锁定方块"""
        if self.game_over or self.paused:
            return
        distance = self.ghost_y() - self.current.y
        self.current.y += distance
        self.scoring.award_hard_drop(distance)
        self.lock()

    def swap_hold(self):
        """暂存或交换方块；同一个活动块只能使用一次暂存。"""
        if not self.can_hold or self.game_over or self.paused:
            return
        old = self.current.kind
        if self.hold is None:
            self.hold = old
            self.spawn()
        else:
            self.current = Piece(self.hold)
            self.hold = old
            if not self.valid():
                self.game_over = True
        self.can_hold = False

    def spawn(self):
        """从预览队列生成新方块，并补入一个新的 7-bag 方块。"""
        self.current = Piece(self.queue.pop(0))
        self.queue.append(self.bag.pop())
        self.can_hold = True
        self.lock_timer = 0 #保证每个新方块都享有完整的 0.5 秒锁前调整时间，不继承上一个方块的残留状态
        if not self.valid():
            self.game_over = True

    def lock(self):
        """把活动块写入棋盘、处理消行和得分，然后生成下一块。"""
        for x, y in self.current.cells():
            if y < 0:
                self.game_over = True
                return
            self.board[y][x] = self.current.kind
        full = [y for y, row in enumerate(self.board) if all(row)] #记录着已满行号的列表
        if full:
            # 倒序删除可避免前面行删除后导致后续下标移动。
            for y in reversed(full):
                del self.board[y]
            self.board[0:0] = [[None] * COLS for _ in full]
            self.scoring.apply_line_clear(len(full))
        else:
            self.scoring.apply_line_clear(0)
        self.spawn()

    def update(self, dt):
        """按实际经过时间推进自动下落和 0.5 秒落地锁定计时。"""
        if self.game_over or self.paused:
            return
        self.fall_timer += dt
        if self.fall_timer >= self.fall_interval:
            self.fall_timer %= self.fall_interval
            self.move(0, 1)
        if not self.valid(y=self.current.y + 1):
            self.lock_timer += dt
            if self.lock_timer >= 0.5:
                self.lock()
        else:
            self.lock_timer = 0

    def snapshot(self):
        """生成可 JSON 序列化的显示快照，供对手棋盘同步。"""
        # 网络端需要看到活动块，因此在副本上临时合并 current，
        # 不修改本地真正用于碰撞的 board。
        board = [[cell or "" for cell in row] for row in self.board]
        if not self.game_over:
            for x, y in self.current.cells():
                if 0 <= y < ROWS and 0 <= x < COLS:
                    board[y][x] = self.current.kind
        return {"board": board, "score": self.score, "lines": self.lines,
                "level": self.level, "game_over": self.game_over}