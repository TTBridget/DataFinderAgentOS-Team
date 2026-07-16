"""人脸注册、状态查询和登录接口。"""

import json
import math
import os
import time
from collections import defaultdict, deque

import tornado.web

from app.controllers.base import BaseHandler
from app.models.face_profile import (
    MODEL_VERSION,
    FaceProfileRepository,
    descriptor_distance,
    match_descriptor_sets,
    validate_descriptor_set,
)
from app.models.user import UserRepository


class _AttemptLimiter:
    """轻量级进程内限流，避免人脸登录接口被高频尝试。"""

    def __init__(self, limit=6, window_seconds=60):
        self.limit = limit
        self.window_seconds = window_seconds
        self._attempts = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.time()
        queue = self._attempts[key]
        while queue and now - queue[0] > self.window_seconds:
            queue.popleft()
        if len(queue) >= self.limit:
            return False
        queue.append(now)
        return True

    def clear(self, key: str) -> None:
        self._attempts.pop(key, None)


_LOGIN_LIMITER = _AttemptLimiter()


def _json_body(handler):
    if not handler.request.body:
        return {}
    try:
        data = json.loads(handler.request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise tornado.web.HTTPError(400, reason="请求格式错误")
    if not isinstance(data, dict):
        raise tornado.web.HTTPError(400, reason="请求格式错误")
    return data


def _write_json(handler, code, msg="", data=None, status=200):
    handler.set_status(status)
    handler.set_header("Content-Type", "application/json; charset=UTF-8")
    handler.set_header("Cache-Control", "no-store")
    payload = {"code": code, "msg": msg}
    if data is not None:
        payload["data"] = data
    handler.finish(payload)


def _current_user(handler):
    username = handler.current_user
    if not username:
        return None
    return UserRepository.get_user_by_username(username)


def _max_pair_distance(descriptors):
    maximum = 0.0
    for index, left in enumerate(descriptors):
        for right in descriptors[index + 1:]:
            maximum = max(maximum, descriptor_distance(left, right))
    return maximum


class FaceStatusHandler(BaseHandler):
    """查询当前用户是否已录入新版人脸模板。"""

    @tornado.web.authenticated
    def get(self):
        user = _current_user(self)
        if not user:
            return _write_json(self, 1, "用户不存在", status=404)
        row = FaceProfileRepository.get_by_user_id(user["id"])
        current = bool(row and row["model_version"] == MODEL_VERSION)
        return _write_json(
            self,
            0,
            data={
                "enrolled": current,
                "needs_reenroll": bool(row and not current),
                "updated_at": row["updated_at"] if row else None,
            },
        )


class FaceEnrollHandler(BaseHandler):
    """当前登录用户录入或更新五个人脸模板。"""

    @tornado.web.authenticated
    def post(self):
        user = _current_user(self)
        if not user:
            return _write_json(self, 1, "用户不存在", status=404)

        body = _json_body(self)
        password = str(body.get("password") or "")
        if not password or not UserRepository.verify_user(user["username"], password):
            return _write_json(self, 1, "当前密码验证失败", status=403)

        try:
            descriptors = validate_descriptor_set(
                body.get("descriptors"), min_count=5, max_count=5
            )
        except (TypeError, ValueError) as exc:
            return _write_json(self, 1, str(exc), status=400)

        # 防止录入过程中换人；这里使用较宽松的内部一致性上限。
        if _max_pair_distance(descriptors) > 0.62:
            return _write_json(self, 1, "五次采集差异过大，请由同一人重新录入", status=400)

        FaceProfileRepository.upsert(user["id"], descriptors)
        return _write_json(self, 0, "人脸录入成功")


class FaceDeleteHandler(BaseHandler):
    """删除当前登录用户的人脸模板。"""

    @tornado.web.authenticated
    def post(self):
        user = _current_user(self)
        if not user:
            return _write_json(self, 1, "用户不存在", status=404)

        body = _json_body(self)
        password = str(body.get("password") or "")
        if not password or not UserRepository.verify_user(user["username"], password):
            return _write_json(self, 1, "当前密码验证失败", status=403)

        FaceProfileRepository.delete(user["id"])
        return _write_json(self, 0, "人脸模板已删除")


class FaceLoginHandler(BaseHandler):
    """使用用户名和三次实时人脸样本登录。"""

    def post(self):
        body = _json_body(self)
        username = str(body.get("username") or "").strip()
        remote_ip = self.request.remote_ip or "unknown"
        limiter_key = f"{remote_ip}:{username.lower()}"

        if not username or len(username) > 32:
            return _write_json(self, 1, "人脸识别失败", status=401)
        if not _LOGIN_LIMITER.allow(limiter_key):
            return _write_json(self, 1, "尝试次数过多，请稍后再试", status=429)

        row = FaceProfileRepository.get_by_username(username)
        if not row or row["is_disabled"] == 1:
            return _write_json(self, 1, "人脸识别失败", status=401)
        if row["model_version"] != MODEL_VERSION:
            return _write_json(self, 1, "请先使用密码登录并重新录入人脸", status=409)

        stored = FaceProfileRepository.get_descriptors_by_username(username)
        try:
            probes = validate_descriptor_set(
                body.get("descriptors"), min_count=3, max_count=3
            )
        except (TypeError, ValueError):
            return _write_json(self, 1, "人脸识别失败", status=401)

        if stored is None:
            return _write_json(self, 1, "人脸识别失败", status=401)
        if _max_pair_distance(probes) > 0.48:
            return _write_json(self, 1, "实时采集不稳定，请保持同一人并重新尝试", status=401)

        threshold = float(os.environ.get("FACE_LOGIN_THRESHOLD", "0.42"))
        threshold = min(max(threshold, 0.32), 0.55)
        accepted, score, scores, passed = match_descriptor_sets(
            stored, probes, threshold
        )
        print(
            f"[FaceLogin] user={username!r} score={score:.4f} "
            f"samples={[round(value, 4) for value in scores]} "
            f"passed={passed}/{len(probes)} threshold={threshold:.2f}"
        )
        if not accepted:
            return _write_json(self, 1, "人脸识别失败", status=401)

        _LOGIN_LIMITER.clear(limiter_key)
        self.set_secure_cookie(
            "username",
            username,
            httponly=True,
            samesite="Lax",
            secure=self.request.protocol == "https",
        )
        return _write_json(
            self,
            0,
            "登录成功",
            data={"redirect": "/index", "score": round(score, 4)},
        )
