import sys
import time
from functools import partial
from threading import Thread
import threading
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5 import QtCore
import bisect
from enum import Enum


class STATE(Enum):
    UP = 1  # 向上运行，包括暂停在某一层开门
    STOP = 0  # 完全停止，没有任务
    DOWN = -1


height = 20
elev_cnt = 5
floors = [i for i in range(1, height + 1)]  # 楼层序号1——height
# 共享数据
request = {STATE.UP: {floor: False for floor in floors}, STATE.DOWN: {floor: False for floor in floors}}  # 上下是否有请求
out_button = {}  # out_button{'up' | 'down'}{floor}


class Elev(Thread, QtCore.QObject):
    move_state = STATE.STOP
    req_state = STATE.STOP
    runLock = threading.Lock()  # 当STOP时，用来锁住线程
    DOOR_RUN = False  # 暂停, 不论向上，向下，停止，pause都表示开关门
    floor = 1
    door_time = 1.5
    move_time = 1
    in_button = {}  # elev_button{floor}  # floor序号 1——max
    lcd = None
    label = None
    '''
        电梯状态：运行（向上，向下，（运动，停止）），停止（） ？静止但有向上趋势？
        1. 电梯i运行方向上、有（内+外）请求，加入到目标goal[i]
        2. 电梯i静止
        if moving

        https://gitee.com/BeanInJ/elevator-scheduling
        资源消费表：对于每个电梯可消费的资源来自三张表， 
        一张是每个电梯内部存储到达楼层表，仅供当前电梯消费， 
        一张是外部的上行楼层表，每个电梯抢夺消费， 
        一张是外部的下行楼层表，每个电梯抢夺消费。
    '''

    def __init__(self):
        Thread.__init__(self)
        self.in_goal = []
        self.out_req = {STATE.UP: [], STATE.DOWN: []}
        QtCore.QObject.__init__(self)

    # 重写run()方法
    # 按下向下的，在按下更高层的向下的？？？？？？？？？？？？？？？？？？？
    def run(self):  # 电梯自身上下运行，相关参数为state，goal
        while True:  # 移动一层、开门一次循环
            if self.DOOR_RUN:  # 如果需要开门
                self.label.setText("DOOR\n⟦▬⟧\nOPEN")
                time.sleep(self.door_time)
                self.DOOR_RUN = False  # 门关了
                self.in_button[self.floor].setEnabled(True)  # 按钮恢复

                # 开门时的外部按钮恢复逻辑
                if self.req_state != STATE.STOP:
                    request[self.req_state][self.floor] = False
                    out_button[self.req_state][self.floor].setEnabled(True)  # 同时外部按钮恢复

                # 门改变后更改状态（因为按钮等部分需要用到状态
                if len(self.out_req[STATE.UP]) == len(self.out_req[STATE.DOWN]) == 0:
                    self.req_state = STATE.STOP
                    if len(self.in_goal) == 0:
                        self.move_state = STATE.STOP
                        self.label.setText("STOP")
            else:  # 门没有运行
                if self.floor in self.in_goal:  # 到达开门层
                    self.in_goal.remove(self.floor)  # 到达该层，从目标中删除
                    self.DOOR_RUN = True  # 设置为开门态
                elif self.move_state == STATE.UP:  # 向上移动一层
                    self.label.setText("UP\n▲")
                    time.sleep(self.move_time)
                    self.floor = self.floor + 1
                elif self.move_state == STATE.DOWN:  # 向下移动一层
                    self.label.setText("DOWN\n▼")
                    time.sleep(self.move_time)
                    self.floor = self.floor - 1

                # 外部处理
                if self.move_state != STATE.STOP and self.floor in self.out_req[self.move_state]:  # 当前运行方向的同向请求
                    self.out_req[self.move_state].remove(self.floor)  # 移除该方向该请求-----------------req_state恢复？
                    self.DOOR_RUN = True  # 设置为开门态
                elif self.move_state == STATE.DOWN and self.req_state == STATE.UP and self.floor == \
                        self.out_req[self.req_state][0]:
                    # 当前运行方向向下，但向上有请求，并且到达最低的一层
                    self.out_req[self.req_state].remove(self.floor)  # 移除该请求
                    self.DOOR_RUN = True  # 设置为开门态-------------------?state怎么办
                    self.move_state = self.req_state
                    # out_button[self.req_state][self.floor].setEnabled(True)  # 同时外部按钮恢复
                elif self.move_state == STATE.UP and self.req_state == STATE.DOWN and self.floor == \
                        self.out_req[self.req_state][-1]:
                    # 当前运行方向向上，但向下有请求，并且到达最高的一层
                    self.out_req[self.req_state].remove(self.floor)  # 移除该请求
                    self.DOOR_RUN = True  # 设置为开门态-------------------?state怎么办
                    self.move_state = self.req_state
                    # out_button[self.req_state][self.floor].setEnabled(True)  # 同时外部按钮恢复

                self.lcd.display(self.floor)

                if len(self.out_req[STATE.UP]) == len(self.out_req[STATE.DOWN]) == 0:
                    # self.req_state = STATE.STOP
                    if len(self.in_goal) == 0:
                        # self.move_state = STATE.STOP
                        time.sleep(2)
            self.check_after_run()

    def open_fun(self):
        if self.move_state == STATE.STOP:
            self.DOOR_RUN = True

    def check_after_run(self):
        if (self.floor < min(floors) and self.move_state == STATE.DOWN or
                self.floor > max(floors) and self.move_state == STATE.UP):
            self.move_state = STATE.STOP
            for floor in floors:
                self.in_button[floor].setEnabled(True)
            self.in_goal.clear()
            self.floor = self.floor - self.move_state.value

    def state_startToMove(self, goal):
        if self.move_state == STATE.STOP:  # 按下非当前，且本身是停止状态，修改状态为趋向
            if goal > self.floor:
                self.move_state = STATE.UP
            elif goal < self.floor:
                self.move_state = STATE.DOWN

    def set_goal(self, goal):
        if (self.move_state == STATE.STOP or
                self.move_state == STATE.UP and goal >= self.floor and goal not in self.in_goal or
                self.move_state == STATE.DOWN and goal <= self.floor and goal not in self.in_goal):

            self.in_button[goal].setEnabled(False)  # 按下去了，变灰

            if goal != self.floor:  # 按下的不是当前层
                bisect.insort(self.in_goal, goal)  # 有序插入目标数组

                self.state_startToMove(goal)  # 从停止到运行
            else:  # 按下的是当前层
                self.DOOR_RUN = True  # 在当前层则开关门
            return True
        else:
            return False

    def set_out(self, goal, req_dir):
        if (self.move_state == STATE.STOP or
                self.move_state == STATE.UP and goal >= self.floor and goal not in self.out_req[req_dir] or
                self.move_state == STATE.DOWN and goal <= self.floor and goal not in self.out_req[req_dir]):

            if goal != self.floor:  # 按下的不是当前层
                if self.req_state == STATE.STOP or self.req_state == req_dir:
                    # if (req_dir == STATE.UP and len(self.out_req[STATE.DOWN]) == 0 or  # 有向上请求，向下队列为空
                    #         req_dir == STATE.DOWN and len(self.out_req[STATE.UP]) == 0):  # 有向下请求，向上队列为空
                    bisect.insort(self.out_req[req_dir], goal)  # 有序插入该方向上的请求
                    self.req_state = req_dir
                    # print(self.out_req)
                    print(self.out_req)
                    print(self.req_state)
                else:
                    return False

                self.state_startToMove(goal)  # 从停止到运行
            else:  # 按下的是当前层
                self.DOOR_RUN = True  # 在当前层则开关门
            return True
        else:
            return False


elevs = [Elev() for _ in range(elev_cnt)]  # 电梯序号0——cnt-1


def out_request(direct, flr):
    if not request[direct][flr]:  # 把请求加入到request列表里
        request[direct][flr] = True
        out_button[direct][flr].setEnabled(False)
        # print(request)
    print()
    for elev in elevs:
        if elev.set_out(flr, direct):
            return
    #
    #     print("in-goal", end='')
    #     print(elev.in_goal)
    #     print(elev.move_state)
    #     print('out_req', end='')
    #     print(elev.out_req)
    #     print(elev.req_state)
    # print('req', end='')
    # print(request)
    # print()
    # 都插入不了的话
    request[direct][flr] = False
    out_button[direct][flr].setEnabled(True)


def start():
    for i in range(elev_cnt):
        elevs[i].start()


def join():
    for i in range(elev_cnt):
        elevs[i].join()


class GUI(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        """最常用的还是栅格布局了。这种布局是把窗口分为行和列。创建和使用栅格布局，需要使用QGridLayout模块。"""
        screens = QGridLayout()  # 楼层显示
        inButtons = QGridLayout()  # 内部按钮
        openButtons = QGridLayout()  # 开门按钮
        outButtons = QGridLayout()  # 外部按钮
        grid = QGridLayout()  # 显示和按钮在一个表格布局中

        # 间距设置
        screens.setHorizontalSpacing(20)  # 设置楼层显示之间的间距
        inButtons.setHorizontalSpacing(20)  # 设置电梯内按钮列之间的间距
        outButtons.setHorizontalSpacing(20)  # 设置电梯外按钮列之间的间距
        grid.setHorizontalSpacing(100)  # 设置内外按钮列之间的间距

        # 整体是一个栅格布局，分别加入进去
        grid.addLayout(inButtons, 1, 0)  # 内部按钮加入整体布局
        grid.addLayout(openButtons, 2, 0)  # 开门按钮加入整体布局
        grid.addLayout(outButtons, 1, 1)  # 外部按钮加入整体布局
        grid.addLayout(screens, 0, 0)  # 显示楼层加入整体布局
        self.setLayout(grid)

        '''按钮操作：
            setStyleSheet设置图形界面的外观
            setEnabled(False) 设置按钮安不了
            clicked.connect注意事项，必须用partial——https://zhuanlan.zhihu.com/p/354262850
        '''
        up_button = {}
        down_button = {}
        for floor in floors:
            # 外部按钮：20层楼-20行，上下-2列---------------------------
            text = QLabel(str(floor))  # 按钮的楼层
            text.setFont(QFont("MV BoLi"))  # 字体
            text.setAlignment(QtCore.Qt.AlignRight)
            outButtons.addWidget(text, height - floor + 1, 0)

            button = QPushButton('▲')
            button.setFont(QFont("MV BoLi"))  # 字体
            outButtons.addWidget(button, height - floor + 1, 1)
            button.clicked.connect(partial(out_request, STATE.UP, floor))
            up_button[floor] = button

            button = QPushButton('▼')
            button.setFont(QFont("MV BoLi"))  # 字体
            outButtons.addWidget(button, height - floor + 1, 2)
            button.clicked.connect(partial(out_request, STATE.DOWN, floor))
            down_button[floor] = button
        out_button[STATE.UP] = up_button  # out_button{'up'}{floor}
        out_button[STATE.DOWN] = down_button  # out_button{'down'}{floor}

        # 内部按钮----------------------------------------------
        for elev in range(elev_cnt):
            in_button = {}
            for floor in floors:
                button = QPushButton(str(floor))  # 楼层按钮
                button.setFont(QFont("MV BoLi"))  # 字体
                inButtons.addWidget(button, height - floor + 1, elev)  # 加到栅格布局里
                button.clicked.connect(partial(elevs[elev].set_goal, floor))  # 按下的楼层添加到目标列表里
                in_button[floor] = button  # 一个电梯内部的按钮加入到集合
            elevs[elev].in_button = in_button  # 电梯elev的内部按钮字典in_button

            open_but = QPushButton("OPEN")
            open_but.setFont(QFont("MV BoLi"))  # 字体
            open_but.clicked.connect(elevs[elev].open_fun)
            openButtons.addWidget(open_but, 0, elev)
            elevs[elev].open_but = open_but

        # 当前楼层显示-------------------------------------------
        for i in range(elev_cnt):
            Show = QGridLayout()
            # 数字显示
            lcd = QLCDNumber()
            lcd.display(elevs[i].floor)
            lcd.setDigitCount(2)
            lcd.setFixedWidth(50)
            lcd.setStyleSheet("border: 2px solid black; background: silver; ")  # 设计样式
            elevs[i].lcd = lcd
            Show.addWidget(lcd, 0, 1)
            Show.setRowMinimumHeight(0, 50)
            # 上下行和暂停显示
            stateShow = QLabel("STOP")
            stateShow.setAlignment(QtCore.Qt.AlignRight)
            elevs[i].label = stateShow
            Show.addWidget(stateShow, 0, 0)
            # 作为整体加入到screens
            screens.addLayout(Show, 0, i)

        self.setWindowTitle('Elevator')
        self.show()


if __name__ == "__main__":  # 可以管理共享数据
    app = QApplication(sys.argv)

    w = GUI()
    start()
    sys.exit(app.exec_())
    # elevSys.join()
