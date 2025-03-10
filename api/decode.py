# -*- coding: utf-8 -*-
import re
import json
from bs4 import BeautifulSoup
from loguru import logger


def decode_course_list(_text):
    logger.info("开始解码课程列表")
    _soup = BeautifulSoup(_text, "lxml")
    _raw_courses = _soup.select("div.course")
    _course_list = list()
    for course in _raw_courses:
        if not course.select_one("a.not-open-tip") and not course.select_one(
            "div.not-open-tip"
        ):
            _course_detail = {}
            _course_detail["id"] = course.attrs["id"]
            _course_detail["info"] = course.attrs["info"]
            _course_detail["roleid"] = course.attrs["roleid"]

            _course_detail["clazzId"] = course.select_one("input.clazzId").attrs[
                "value"
            ]
            _course_detail["courseId"] = course.select_one("input.courseId").attrs[
                "value"
            ]
            _course_detail["cpi"] = re.findall(
                r"cpi=(.*?)&", course.select_one("a").attrs["href"]
            )[0]
            _course_detail["title"] = course.select_one("span.course-name").attrs[
                "title"
            ]
            if course.select_one("p.margint10") is None:
                _course_detail["desc"] = ""
            else:
                _course_detail["desc"] = course.select_one("p.margint10").attrs["title"]
            _course_detail["teacher"] = course.select_one("p.color3").attrs["title"]
            _course_list.append(_course_detail)
    return _course_list


def decode_course_folder(_text):
    logger.info("开始解码二级课程列表")
    _soup = BeautifulSoup(_text, "lxml")
    _raw_courses = _soup.select("ul.file-list>li")
    _course_folder_list = list()
    for course in _raw_courses:
        if course.attrs["fileid"]:
            _course_folder_detail = {}
            _course_folder_detail["id"] = course.attrs["fileid"]
            _course_folder_detail["rename"] = course.select_one(
                "input.rename-input"
            ).attrs["value"]
            _course_folder_list.append(_course_folder_detail)
    return _course_folder_list


def decode_course_point(_text):
    logger.info("开始解码章节列表")
    _soup = BeautifulSoup(_text, "lxml")
    _course_point = {
        "hasLocked": False,  # 用于判断该课程任务是否是需要解锁
        "points": [],
    }

    for _chapter_unit in _soup.find_all("div", class_="chapter_unit"):
        _point_list = []
        _raw_points = _chapter_unit.find_all("li")
        for _point in _raw_points:
            _point = _point.div
            if not "id" in _point.attrs:
                continue
            _point_detail = {}
            _point_detail["id"] = re.findall(r"^cur(\d{1,20})$", _point.attrs["id"])[0]
            _point_detail["title"] = (
                _point.select_one("a.clicktitle").text.replace("\n", "").strip(" ")
            )
            _point_detail["jobCount"] = 1  # 默认为1
            if _point.select_one("input.knowledgeJobCount"):
                _point_detail["jobCount"] = _point.select_one(
                    "input.knowledgeJobCount"
                ).attrs["value"]
            else:
                # 判断是不是因为需要解锁
                if "解锁" in _point.select_one("span.bntHoverTips").text:
                    _course_point["hasLocked"] = True

            _point_list.append(_point_detail)
        _course_point["points"] += _point_list
    return _course_point


def decode_course_card(_text: str):
    _job_info = {}
    _job_list = []
    # 对于未开放章节检测
    if "章节未开放" in _text:
        _job_info["notOpen"] = True
        return [], _job_info

    _temp = re.findall(r"mArg=\{(.*?)\};", _text.replace(" ", ""))
    if _temp:
        _temp = _temp[0]
    else:
        return [], {}
    _cards = json.loads("{" + _temp + "}")

    if _cards:
        _job_info = {}
        _job_info["ktoken"] = _cards["defaults"]["ktoken"]
        _job_info["mtEnc"] = _cards["defaults"]["mtEnc"]
        _job_info["reportTimeInterval"] = _cards["defaults"]["reportTimeInterval"]  # 60
        _job_info["defenc"] = _cards["defaults"]["defenc"]
        _job_info["cardid"] = _cards["defaults"]["cardid"]
        _job_info["cpi"] = _cards["defaults"]["cpi"]
        _job_info["qnenc"] = _cards["defaults"]["qnenc"]
        _job_info["knowledgeid"] = _cards["defaults"]["knowledgeid"]
        _cards = _cards["attachments"]
        _job_list = []
        for _card in _cards:
            # 已经通过的任务
            if "isPassed" in _card and _card["isPassed"] is True:
                continue
            # 不属于任务点的任务
            if "job" not in _card or _card["job"] is False:
                if _card.get("type") and _card["type"] == "read":
                    # 发现有在视频任务下掺杂阅读任务，不完成可能会导致无法开启下一章节
                    if _card["property"].get("read", False):
                        # 已阅读，跳过
                        continue
                    _job = {}
                    _job["title"] = _card["property"]["title"]
                    _job["type"] = "read"
                    _job["id"] = _card["property"]["id"]
                    _job["jobid"] = _card["jobid"]
                    _job["jtoken"] = _card["jtoken"]
                    _job["mid"] = _card["mid"]
                    _job["otherinfo"] = _card["otherInfo"]
                    _job["enc"] = _card["enc"]
                    _job["aid"] = _card["aid"]
                    _job_list.append(_job)
                continue
            # 视频任务
            if _card["type"] == "video":
                _job = {}
                _job["type"] = "video"
                _job["jobid"] = _card["jobid"]
                _job["name"] = _card["property"]["name"]
                _job["otherinfo"] = _card["otherInfo"]
                try:
                    _job["mid"] = _card["mid"]
                except KeyError:
                    logger.warning("出现转码失败视频，已跳过...")
                    continue
                _job["objectid"] = _card["objectId"]
                _job["aid"] = _card["aid"]
                # _job["doublespeed"] = _card["property"]["doublespeed"]
                _job_list.append(_job)
                continue
            if _card["type"] == "document":
                _job = {}
                _job["type"] = "document"
                _job["jobid"] = _card["jobid"]
                _job["otherinfo"] = _card["otherInfo"]
                _job["jtoken"] = _card["jtoken"]
                _job["mid"] = _card["mid"]
                _job["enc"] = _card["enc"]
                _job["aid"] = _card["aid"]
                _job["objectid"] = _card["property"]["objectid"]
                _job_list.append(_job)
                continue
            if _card["type"] == "workid":
                # 章节检测
                _job = {}
                _job["type"] = "workid"
                _job["jobid"] = _card["jobid"]
                _job["otherinfo"] = _card["otherInfo"]
                _job["mid"] = _card["mid"]
                _job["enc"] = _card["enc"]
                _job["aid"] = _card["aid"]
                _job_list.append(_job)
                continue

            if _card["type"] == "vote":
                # 调查问卷 同上
                continue
        return _job_list, _job_info
