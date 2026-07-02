from __future__ import annotations
import random
from dataclasses import dataclass

from .config import COLS, ROWS

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
    