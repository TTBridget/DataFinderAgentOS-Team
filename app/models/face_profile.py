"""人脸登录模板仓储（多模板版本）。

保存 face-api.js 输出的原始 128 维描述向量，不保存照片或视频。
"""

import json
import math
import statistics
from contextlib import closing
from typing import Iterable, List, Sequence, Tuple

from app.models.db import get_connection

DESCRIPTOR_SIZE = 128
MODEL_VERSION = "face-api.js-0.22.2-multi-v2"


def validate_descriptor(values: Iterable[float]) -> List[float]:
    """校验一个原始 128 维描述向量，不改变模型原始空间。"""
    if not isinstance(values, (list, tuple)) or len(values) != DESCRIPTOR_SIZE:
        raise ValueError("人脸特征必须是 128 维数组")

    result = []
    for value in values:
        if isinstance(value, bool):
            raise ValueError("人脸特征包含非法值")
        number = float(value)
        if not math.isfinite(number) or abs(number) > 10:
            raise ValueError("人脸特征包含非法值")
        result.append(number)

    norm = math.sqrt(sum(value * value for value in result))
    if not 0.25 <= norm <= 3.0:
        raise ValueError("人脸特征范数异常")
    return result


def validate_descriptor_set(
    values: Sequence[Sequence[float]],
    *,
    min_count: int = 1,
    max_count: int = 8,
) -> List[List[float]]:
    if not isinstance(values, (list, tuple)):
        raise ValueError("人脸模板格式错误")
    if not min_count <= len(values) <= max_count:
        raise ValueError(f"人脸模板数量必须在 {min_count} 到 {max_count} 之间")
    return [validate_descriptor(value) for value in values]


def descriptor_distance(left: Iterable[float], right: Iterable[float]) -> float:
    """在 face-api.js 原始描述空间计算欧氏距离。"""
    left_values = validate_descriptor(left)
    right_values = validate_descriptor(right)
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left_values, right_values)))


def match_descriptor_sets(
    stored: Sequence[Sequence[float]],
    probes: Sequence[Sequence[float]],
    threshold: float,
) -> Tuple[bool, float, List[float], int]:
    """多模板匹配。

    每个实时样本必须至少接近两个已录入模板；三个实时样本中至少两个通过，
    且三个支持距离的中位数不超过阈值。
    """
    stored_values = validate_descriptor_set(stored, min_count=2, max_count=8)
    probe_values = validate_descriptor_set(probes, min_count=3, max_count=5)

    scores: List[float] = []
    passed = 0
    for probe in probe_values:
        distances = sorted(descriptor_distance(template, probe) for template in stored_values)
        support_distance = distances[1]  # 至少两个模板支持，避免单模板偶然命中
        scores.append(support_distance)
        if support_distance <= threshold:
            passed += 1

    median_score = float(statistics.median(scores))
    required = max(2, math.ceil(len(probe_values) * 2 / 3))
    accepted = passed >= required and median_score <= threshold
    return accepted, median_score, scores, passed


class FaceProfileRepository:
    """用户人脸模板的数据访问层。"""

    @staticmethod
    def ensure_table() -> None:
        with closing(get_connection()) as conn:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_face_profiles(
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL UNIQUE,
                        descriptor_json TEXT NOT NULL,
                        model_version TEXT NOT NULL DEFAULT 'face-api.js-0.22.2',
                        created_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
                        updated_at TEXT NOT NULL DEFAULT(datetime('now','localtime')),
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_face_profile_user "
                    "ON user_face_profiles(user_id)"
                )

    @staticmethod
    def upsert(user_id: int, descriptors: Sequence[Sequence[float]]) -> bool:
        FaceProfileRepository.ensure_table()
        values = validate_descriptor_set(descriptors, min_count=5, max_count=5)
        payload = json.dumps(values, separators=(",", ":"))
        with closing(get_connection()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO user_face_profiles(user_id, descriptor_json, model_version)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        descriptor_json=excluded.descriptor_json,
                        model_version=excluded.model_version,
                        updated_at=datetime('now','localtime')
                    """,
                    (int(user_id), payload, MODEL_VERSION),
                )
        return True

    @staticmethod
    def get_by_user_id(user_id: int):
        FaceProfileRepository.ensure_table()
        with closing(get_connection()) as conn:
            row = conn.execute(
                """
                SELECT p.*, u.username, u.is_disabled
                FROM user_face_profiles p
                JOIN users u ON u.id = p.user_id
                WHERE p.user_id = ?
                """,
                (int(user_id),),
            ).fetchone()
        return row

    @staticmethod
    def get_by_username(username: str):
        FaceProfileRepository.ensure_table()
        with closing(get_connection()) as conn:
            row = conn.execute(
                """
                SELECT p.*, u.username, u.is_disabled
                FROM user_face_profiles p
                JOIN users u ON u.id = p.user_id
                WHERE u.username = ?
                """,
                (username,),
            ).fetchone()
        return row

    @staticmethod
    def get_descriptors_by_username(username: str):
        row = FaceProfileRepository.get_by_username(username)
        if not row or row["model_version"] != MODEL_VERSION:
            return None
        try:
            return validate_descriptor_set(
                json.loads(row["descriptor_json"]), min_count=5, max_count=5
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    @staticmethod
    def has_current_profile(user_id: int) -> bool:
        row = FaceProfileRepository.get_by_user_id(user_id)
        return bool(row and row["model_version"] == MODEL_VERSION)

    @staticmethod
    def delete(user_id: int) -> bool:
        FaceProfileRepository.ensure_table()
        with closing(get_connection()) as conn:
            with conn:
                cursor = conn.execute(
                    "DELETE FROM user_face_profiles WHERE user_id = ?",
                    (int(user_id),),
                )
        return cursor.rowcount > 0
