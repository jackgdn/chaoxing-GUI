# encoding=utf-8

import random
import re
import time
from hashlib import md5

import requests
from loguru import logger
from PySide6.QtCore import QObject, Signal
from requests.adapters import HTTPAdapter

from api.cipher import AESCipher
from api.config import GlobalConst as gc
from api.cookies import save_cookies, use_cookies
from api.decode import (
    decode_course_card,
    decode_course_folder,
    decode_course_list,
    decode_course_point,
)

requests.packages.urllib3.disable_warnings()


def init_session(isVideo: bool = False, isAudio: bool = False):
    _session = requests.session()
    _session.verify = False
    _session.mount("http://", HTTPAdapter(max_retries=1))
    _session.mount("https://", HTTPAdapter(max_retries=1))
    if isVideo:
        _session.headers = gc.VIDEO_HEADERS
    elif isAudio:
        _session.headers = gc.AUDIO_HEADERS
    else:
        _session.headers = gc.HEADERS
    _session.cookies.update(use_cookies())
    return _session


def get_timestamp():
    return str(int(time.time() * 1000))


class RollBackManager:
    def __init__(self) -> None:
        self.rollback_times = 0
        self.rollback_id = ""

    def reset_times(self, id: str) -> int:
        if id == self.rollback_id:
            self.rollback_times = 0

    def add_times(self, id: str) -> None:
        if id == self.rollback_id and self.rollback_times == 3:
            raise Exception("回滚次数已达3次，请手动检查学习通任务点完成情况")
        elif id != self.rollback_id:
            # 新job
            self.rollback_id = id
            self.rollback_times = 1
        else:
            self.rollback_times += 1


class Account:
    username = None
    password = None
    last_login = None
    isSuccess = None

    def __init__(self, _username, _password):
        self.username = _username
        self.password = _password


class Chaoxing(QObject):
    signal_logger = Signal(str)
    signal_progress = Signal(int)
    signal_time_updated = Signal(str)

    def __init__(self, account):
        super().__init__()
        self.account = account
        self.cipher = AESCipher()
        self.update_signal = Signal(str)

    def login(self):
        _session = requests.session()
        _session.verify = False
        _url = "https://passport2.chaoxing.com/fanyalogin"
        _data = {
            "fid": "-1",
            "uname": self.cipher.encrypt(self.account.username),
            "password": self.cipher.encrypt(self.account.password),
            "refer": "https%3A%2F%2Fi.chaoxing.com",
            "t": True,
            "forbidotherlogin": 0,
            "validate": "",
            "doubleFactorLogin": 0,
            "independentId": 0,
        }

        try:
            resp = _session.post(_url, headers=gc.HEADERS, data=_data)
        except Exception as e:
            logger.error(f"登录失败: {e}")
            return {"status": False, "message": "连接超时\n请检查网络连接"}

        if resp.json()["status"]:
            save_cookies(_session)
            logger.info(f"登录成功")
            return {"status": True}
        else:
            logger.error(f"登录失败: {str(resp.json()["msg2"])}")
            return {"status": False, "message": str(resp.json()["msg2"])}

    def get_fid(self):
        _session = init_session()
        return _session.cookies.get("fid")

    def get_uid(self):
        _session = init_session()
        return _session.cookies.get("_uid")

    def get_course_list(self):
        _session = init_session()
        _url = "https://mooc2-ans.chaoxing.com/mooc2-ans/visit/courselistdata"
        _data = {"courseType": 1, "courseFolderId": 0, "query": "", "superstarClass": 0}
        logger.info("正在读取所有的课程列表")
        # 接口突然抽风，增加headers
        _headers = {
            "Host": "mooc2-ans.chaoxing.com",
            "sec-ch-ua-platform": '"Windows"',
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
            "Accept": "text/html, */*; q=0.01",
            "sec-ch-ua": '"Microsoft Edge";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "sec-ch-ua-mobile": "?0",
            "Origin": "https://mooc2-ans.chaoxing.com",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://mooc2-ans.chaoxing.com/mooc2-ans/visit/interaction?moocDomain=https://mooc1-1.chaoxing.com/mooc-ans",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,ja;q=0.5",
        }
        _resp = _session.post(_url, headers=_headers, data=_data)
        logger.info("课程列表读取完毕")
        course_list = decode_course_list(_resp.text)

        _interaction_url = "https://mooc2-ans.chaoxing.com/mooc2-ans/visit/interaction"
        _interaction_resp = _session.get(_interaction_url)
        course_folder = decode_course_folder(_interaction_resp.text)
        for folder in course_folder:
            _data = {
                "courseType": 1,
                "courseFolderId": folder["id"],
                "query": "",
                "superstarClass": 0,
            }
            _resp = _session.post(_url, data=_data)
            course_list += decode_course_list(_resp.text)
        return course_list

    def get_course_point(self, _courseid, _clazzid, _cpi):
        _session = init_session()
        _url = f"https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/studentcourse?courseid={_courseid}&clazzid={_clazzid}&cpi={_cpi}&ut=s"
        logger.info("开始读取课程所有章节")
        _resp = _session.get(_url)
        logger.info("课程章节读取成功")
        return decode_course_point(_resp.text)

    def get_job_list(self, _clazzid, _courseid, _cpi, _knowledgeid):
        _session = init_session()
        job_list = []
        job_info = {}
        logger.info("开始读取章节所有任务点")
        info_flag = True
        for _possible_num in [
            "0",
            "1",
            "2",
        ]:  # 学习界面任务卡片数，很少有3个的，但是对于章节解锁任务点少一个都不行，可以从API /mooc-ans/mycourse/studentstudyAjax获取值，或者干脆直接加，但二者都会造成额外的请求
            _url = f"https://mooc1.chaoxing.com/mooc-ans/knowledge/cards?clazzid={_clazzid}&courseid={_courseid}&knowledgeid={_knowledgeid}&num={_possible_num}&ut=s&cpi={_cpi}&v=20160407-3&mooc2=1"
            _resp = _session.get(_url)
            if info_flag:
                logger.info("开始解码任务点列表")
                info_flag = False
            _job_list, _job_info = decode_course_card(_resp.text)
            if _job_info.get("notOpen", False):
                # 直接返回，节省一次请求
                logger.warning("该章节未开放")
                return [], _job_info
            job_list += _job_list
            job_info.update(_job_info)
            # if _job_list and len(_job_list) != 0:
            #     break
        # logger.trace(f"原始任务点列表内容:\n{_resp.text}")
        logger.info("章节任务点读取成功")
        return job_list, job_info

    def study_video(
        self, _course, _job, _job_info, _speed: float = 1.0, _type: str = "Video"
    ):
        if _type == "Video":
            _session = init_session(isVideo=True)
        else:
            _session = init_session(isAudio=True)
        _session.headers.update()
        _info_url = f"https://mooc1.chaoxing.com/ananas/status/{_job['objectid']}?k={self.get_fid()}&flag=normal"
        _video_info = _session.get(_info_url).json()
        if _video_info["status"] == "success":
            _dtoken = _video_info["dtoken"]
            _duration = _video_info["duration"]
            _crc = _video_info["crc"]
            _key = _video_info["key"]
            _isPassed = False
            _isFinished = False
            _playingTime = 0
            self.signal_logger.emit(f"开始任务：{_job['name']}，总时长：{_duration} 秒")
            logger.info(f"开始任务：{_job['name']}，总时长：{_duration} 秒")
            while not _isFinished:
                if _isFinished:
                    _playingTime = _duration
                _isPassed = self.video_progress_log(
                    _session,
                    _course,
                    _job,
                    _job_info,
                    _dtoken,
                    _duration,
                    _playingTime,
                    _type,
                )
                if not _isPassed or (_isPassed and _isPassed["isPassed"]):
                    break
                _wait_time = random.randint(30, 90)
                if _playingTime + _wait_time >= int(_duration):
                    _wait_time = int(_duration) - _playingTime
                    _isFinished = True
                # 播放进度条
                self.show_progress(_playingTime, _wait_time, _duration, _speed)
                _playingTime += _wait_time
            self.signal_logger.emit(f"任务完成: {_job['name']}")
            logger.info(f"任务完成: {_job['name']}")

    def get_enc(self, clazzId, jobid, objectId, playingTime, duration, userid):
        return md5(
            f"[{clazzId}][{userid}][{jobid}][{objectId}][{playingTime * 1000}][d_yHJ!$pdA~5][{duration * 1000}][0_{duration}]".encode()
        ).hexdigest()

    def video_progress_log(
        self,
        _session,
        _course,
        _job,
        _job_info,
        _dtoken,
        _duration,
        _playingTime,
        _type: str = "Video",
    ):
        if "courseId" in _job["otherinfo"]:
            _mid_text = f"otherInfo={_job['otherinfo']}&"
        else:
            _mid_text = f"otherInfo={_job['otherinfo']}&courseId={_course['courseId']}&"
        _success = False
        for _possible_rt in ["0.9", "1"]:
            _url = (
                f"https://mooc1.chaoxing.com/mooc-ans/multimedia/log/a/"
                f"{_course['cpi']}/"
                f"{_dtoken}?"
                f"clazzId={_course['clazzId']}&"
                f"playingTime={_playingTime}&"
                f"duration={_duration}&"
                f"clipTime=0_{_duration}&"
                f"objectId={_job['objectid']}&"
                f"{_mid_text}"
                f"jobid={_job['jobid']}&"
                f"userid={self.get_uid()}&"
                f"isdrag=3&"
                f"view=pc&"
                f"enc={self.get_enc(_course['clazzId'], _job['jobid'], _job['objectid'], _playingTime, _duration, self.get_uid())}&"
                f"rt={_possible_rt}&"
                f"dtype={_type}&"
                f"_t={str(int(time.time() * 1000))}"
            )
            resp = _session.get(_url)
            if resp.status_code == 200:
                _success = True
                break  # 如果返回为200正常，则跳出循环
            elif resp.status_code == 403:
                continue  # 如果出现403无权限报错，则继续尝试不同的rt参数
        if _success:
            return resp.json()
        else:
            # 若出现两个rt参数都返回403的情况，则跳过当前任务
            logger.warning("出现403报错，尝试修复无效，正在跳过当前任务点")
            return False

    def show_progress(self, start: int, span: int, total: int, speed=1):

        def sec2time(sec):
            h = int(sec / 3600)
            m = int(sec % 3600 / 60)
            s = int(sec % 60)
            if h != 0:
                return f"{h}:{m:02}:{s:02}"
            if sec != 0:
                return f"{m:02}:{s:02}"
            return "--:--"

        start_time = time.time()
        while int(time.time() - start_time) < int(span / speed):
            current = start + int((time.time() - start_time) * speed)
            percent = int(current / total * 100)
            self.signal_progress.emit(percent)
            # self.signal_time_updated.emit(
            #     self.sec2time(current) + "/" + self.sec2time(total)
            # )
            self.signal_time_updated.emit(f"{sec2time(current)}/{sec2time(total)}")
            time.sleep(1)

    def study_document(self, _course, _job):
        _session = init_session()
        _url = f"https://mooc1.chaoxing.com/ananas/job/document?jobid={_job['jobid']}&knowledgeid={re.findall(r'nodeId_(.*?)-', _job['otherinfo'])[0]}&courseid={_course['courseId']}&clazzid={_course['clazzId']}&jtoken={_job['jtoken']}&_dc={get_timestamp()}"
        _resp = _session.get(_url)

    def study_read(self, _course, _job, _job_info) -> None:
        """
        阅读任务学习，仅完成任务点，并不增长时长
        """
        _session = init_session()
        _resp = _session.get(
            url="https://mooc1.chaoxing.com/ananas/job/readv2",
            params={
                "jobid": _job["jobid"],
                "knowledgeid": _job_info["knowledgeid"],
                "jtoken": _job["jtoken"],
                "courseid": _course["courseId"],
                "clazzid": _course["clazzId"],
            },
        )
        if _resp.status_code != 200:
            self.signal_logger.emit(
                f"阅读任务学习失败 -> [{_resp.status_code}]{_resp.text}"
            )
            logger.warning(f"阅读任务学习失败 -> [{_resp.status_code}]{_resp.text}")
        else:
            _resp_json = _resp.json()
            self.signal_logger.emit(f"阅读任务学习 -> {_resp_json['msg']}")
            logger.info(f"阅读任务学习 -> {_resp_json['msg']}")
