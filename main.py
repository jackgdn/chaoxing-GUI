# encoding: utf-8

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QPushButton,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QComboBox,
    QProgressBar,
    QLabel,
)
from PySide6.QtCore import QThread, Signal
from core import Account, Chaoxing, RollBackManager
import sys
from loguru import logger


class LoginWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.main_window = None
        self.init_ui()
        logger.info("程序初始化完成")

    def init_ui(self):
        self.resize(600, 400)
        self.setWindowTitle("chaoxing-GUI")
        self.setFixedSize(600, 400)

        self.lineEdit_username = QLineEdit(self)
        self.lineEdit_username.setPlaceholderText("请输入用户名")
        self.lineEdit_username.move(150, 70)
        self.lineEdit_username.resize(300, 30)

        self.lineEdit_password = QLineEdit(self)
        self.lineEdit_password.setEchoMode(QLineEdit.Password)
        self.lineEdit_password.setPlaceholderText("请输入密码")
        self.lineEdit_password.move(150, 170)
        self.lineEdit_password.resize(300, 30)

        self.button_login = QPushButton("登录", self)
        self.button_login.move(250, 265)
        self.button_login.resize(100, 30)
        self.button_login.clicked.connect(self.login)

    def login(self):
        username = self.lineEdit_username.text()
        password = self.lineEdit_password.text()
        if username == "" or password == "":
            QMessageBox.warning(self, "警告", "用户名或密码不能为空！")
        else:
            account = Account(username, password)
            chaoxing = Chaoxing(account)
            login_status = chaoxing.login()

            if not login_status["status"]:
                QMessageBox.warning(self, "登录失败", login_status["message"])
            else:
                if self.main_window is None:
                    self.main_window = MainWindow(chaoxing)  # 保持对主窗口的引用
                self.main_window.show()
                self.close()


class CourseWorker(QThread):
    signal_logger = Signal(str)
    singal_progress = Signal(int)
    signal_finish = Signal(bool)
    signal_progress_reset = Signal(int)
    signal_time_updated = Signal(str)

    def __init__(self, chaoxing: Chaoxing, course: dict, parent=None):
        super().__init__(parent)
        self.chaoxing = chaoxing
        self.course = course
        self.__RB = RollBackManager()
        self.chaoxing.signal_logger.connect(self.signal_logger.emit)
        self.chaoxing.signal_progress.connect(self.singal_progress.emit)
        self.chaoxing.signal_time_updated.connect(self.signal_time_updated.emit)

    def run(self):
        # 获取当前课程的所有章节
        point_list = self.chaoxing.get_course_point(
            self.course["courseId"], self.course["clazzId"], self.course["cpi"]
        )

        # 为了支持课程任务回滚，采用下标方式遍历任务点
        __point_index = 0
        while __point_index < len(point_list["points"]):
            point = point_list["points"][__point_index]
            self.signal_logger.emit(f'当前章节: {point["title"]}')
            logger.info(f'当前章节: {point["title"]}')
            # 获取当前章节的所有任务点
            jobs = []
            jobs, job_info = self.chaoxing.get_job_list(
                self.course["clazzId"],
                self.course["courseId"],
                self.course["cpi"],
                point["id"],
            )

            # 发现未开放章节，尝试回滚上一个任务重新完成一次
            if job_info.get("notOpen", False):
                __point_index -= 1  # 默认第一个任务总是开放的
                self.__RB.add_times(point["id"])
                continue

            # 正常获取，尝试重置回滚次数
            self.__RB.reset_times(point["id"])

            # 可能存在章节无任何内容的情况
            if not jobs:
                __point_index += 1
                continue

            # 遍历所有任务点
            for job in jobs:
                # 视频任务
                if job["type"] == "video":
                    self.signal_logger.emit(
                        f"识别到视频任务，任务章节：{self.course['title']}"
                    )
                    logger.info(
                        f"识别到视频任务，任务章节：{self.course['title']} 任务ID：{job['jobid']}"
                    )
                    # 超星的接口没有返回当前任务是否为Audio音频任务
                    isAudio = False
                    try:
                        self.chaoxing.study_video(
                            self.course, job, job_info, _speed=1, _type="Video"
                        )
                    except Exception:
                        self.signal_logger.emit(
                            "当前任务非视频任务，正在尝试音频任务解码"
                        )
                        logger.info("当前任务非视频任务，正在尝试音频任务解码")
                        isAudio = True
                    if isAudio:
                        try:
                            self.chaoxing.study_video(
                                self.course, job, job_info, _speed=1, _type="Audio"
                            )
                        except Exception:
                            self.signal_logger.emit(
                                f"出现异常任务 -> 任务章节：{self.course['title']}，已跳过"
                            )
                            logger.warning(
                                f"出现异常任务 -> 任务章节：{self.course['title']} 任务ID：{job['jobid']}，已跳过"
                            )

                # 文档任务
                elif job["type"] == "document":
                    self.signal_logger.emit(
                        f"识别到文档任务，任务章节：{self.course['title']}"
                    )
                    logger.info(
                        f"识别到文档任务，任务章节：{self.course['title']} 任务ID：{job['jobid']}"
                    )
                    self.chaoxing.study_document(self.course, job)

                # 测验任务
                # elif job["type"] == "workid":
                #     logger.info(
                #         f"识别到章节检测任务，任务章节：{self.course['title']} 任务ID：{job['jobid']}"
                #     )
                #     self.chaoxing.study_work(self.course, job, job_info)

                # 阅读任务
                elif job["type"] == "read":
                    self.signal_logger.emit(
                        f"识别到阅读任务，任务章节：{self.course['title']}"
                    )
                    logger.info(
                        f"识别到阅读任务，任务章节：{self.course['title']} 任务ID：{job['jobid']}"
                    )
                    self.chaoxing.study_read(self.course, job, job_info)

                self.signal_progress_reset.emit(0)
            __point_index += 1
        self.signal_finish.emit(True)  # 任务完成

        # 一门课程结束后，断开信号和槽的连接
        self.chaoxing.signal_logger.disconnect(self.signal_logger.emit)
        self.chaoxing.signal_progress.disconnect(self.singal_progress.emit)
        self.chaoxing.signal_time_updated.disconnect(self.signal_time_updated.emit)


class MainWindow(QMainWindow):

    def __init__(self, chaoxing: Chaoxing):
        super().__init__()
        self.chaoxing = chaoxing
        self.init_ui()

    def init_ui(self):
        self.resize(600, 400)
        self.setWindowTitle("chaoxing-GUI")
        self.setFixedSize(600, 400)

        self.outputArea = QTextEdit(self)  # 输出区
        self.outputArea.setReadOnly(True)
        self.outputArea.setLineWrapMode(QTextEdit.NoWrap)
        self.outputArea.move(10, 10)
        self.outputArea.resize(580, 300)

        self.course_list = self.chaoxing.get_course_list()  # 课程列表
        self.outputArea.append("课程列表：")
        for course in self.course_list:
            self.outputArea.append(f"{course['title']} —— {course['teacher']}")

        self.progressBar = QProgressBar(self)  # 进度条
        self.progressBar.move(10, 320)
        self.progressBar.resize(480, 30)
        self.progressBar.setValue(0)

        self.label_progress = QLabel(self)  # 进度显示
        self.label_progress.move(500, 320)
        self.label_progress.resize(100, 30)
        self.label_progress.setText("--:--/--:--")

        self.comboBox_course_selection = QComboBox(self)  # 课程选择框
        self.comboBox_course_selection.move(10, 360)
        self.comboBox_course_selection.resize(360, 30)
        for course in self.course_list:
            self.comboBox_course_selection.addItem(course["title"], course["courseId"])

        self.button_select_course = QPushButton("选择课程", self)  # 选择按钮
        self.button_select_course.move(380, 360)
        self.button_select_course.resize(100, 30)
        self.button_select_course.clicked.connect(self.select_course)

        self.button_exit = QPushButton("退出", self)  # 退出按钮
        self.button_exit.move(490, 360)
        self.button_exit.resize(100, 30)
        self.button_exit.clicked.connect(sys.exit)

    def select_course(self):
        course_id = self.comboBox_course_selection.currentData()
        for course in self.course_list:
            if course["courseId"] == course_id:
                self.course = course
                break
        self.button_select_course.setEnabled(False)
        self.outputArea.append(f"\n当前选择的课程：{course['title']}")
        logger.info(f"当前选择的课程：{self.course['title']}")

        self.courseWorker = CourseWorker(self.chaoxing, self.course)
        self.courseWorker.signal_logger.connect(self.outputArea.append)
        self.courseWorker.start()
        self.courseWorker.singal_progress.connect(self.progressBar.setValue)
        self.courseWorker.signal_time_updated.connect(self.label_progress.setText)
        self.courseWorker.signal_progress_reset.connect(self.progressBar.setValue)
        self.courseWorker.signal_finish.connect(self.button_select_course.setEnabled)
        self.courseWorker.signal_finish.connect(self.message_box_finish)

    def message_box_finish(self, status):
        if status:
            QMessageBox.information(self, "提示", "课程学习完成！")


if __name__ == "__main__":
    logger.add("chaoxing.log", rotation="10 KB", encoding="utf-8")
    app = QApplication()
    font = app.font()
    font.setPointSize(13)
    app.setFont(font)
    window = LoginWindow()
    window.show()
    app.exec()
