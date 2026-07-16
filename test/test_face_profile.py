import math
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest import mock

from app.models import face_profile


def unit_vector(first, second=0.0):
    values = [0.0] * 128
    values[0] = first
    values[1] = second
    norm = math.sqrt(sum(value * value for value in values))
    return [value / norm for value in values]


class FaceProfileTests(unittest.TestCase):
    def test_validate_descriptor_keeps_raw_space(self):
        values = [0.1] * 128
        checked = face_profile.validate_descriptor(values)
        self.assertEqual(checked, values)

    def test_invalid_descriptor(self):
        with self.assertRaises(ValueError):
            face_profile.validate_descriptor([1.0] * 127)
        with self.assertRaises(ValueError):
            face_profile.validate_descriptor([0.0] * 128)

    def test_distance(self):
        left = unit_vector(1.0, 0.0)
        right = unit_vector(1.0, 0.0)
        self.assertAlmostEqual(face_profile.descriptor_distance(left, right), 0.0)

    def test_multi_template_match(self):
        stored = [
            unit_vector(1.0, offset)
            for offset in (0.00, 0.02, -0.02, 0.04, -0.04)
        ]
        genuine = [unit_vector(1.0, offset) for offset in (0.01, -0.01, 0.03)]
        impostor = [unit_vector(0.05, 1.0 + offset) for offset in (0.00, 0.02, -0.02)]
        accepted, _, _, _ = face_profile.match_descriptor_sets(stored, genuine, 0.42)
        rejected, _, _, _ = face_profile.match_descriptor_sets(stored, impostor, 0.42)
        self.assertTrue(accepted)
        self.assertFalse(rejected)

    def test_repository_round_trip(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        def connection():
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            return conn

        try:
            with closing(connection()) as conn:
                with conn:
                    conn.execute(
                        """
                        CREATE TABLE users(
                            id INTEGER PRIMARY KEY,
                            username TEXT UNIQUE,
                            is_disabled INTEGER DEFAULT 0
                        )
                        """
                    )
                    conn.execute("INSERT INTO users(id, username) VALUES(1, 'alice')")

            descriptors = [
                unit_vector(1.0, offset)
                for offset in (0.00, 0.02, -0.02, 0.04, -0.04)
            ]
            with mock.patch.object(face_profile, "get_connection", connection):
                self.assertTrue(face_profile.FaceProfileRepository.upsert(1, descriptors))
                loaded = face_profile.FaceProfileRepository.get_descriptors_by_username("alice")
                self.assertEqual(len(loaded), 5)
                self.assertEqual(len(loaded[0]), 128)
                self.assertTrue(face_profile.FaceProfileRepository.delete(1))
        finally:
            if os.path.exists(path):
                os.remove(path)


if __name__ == "__main__":
    unittest.main()
