import unittest

import ee

from app.services.gee.gee_service import gee_get_info


class DummyComputedObject:
    def __init__(self):
        self.calls = 0

    def getInfo(self):
        self.calls += 1
        if self.calls == 1:
            raise ee.ee_exception.EEException("Too many concurrent aggregations.")
        return {"ok": True}


class GeeRetryTests(unittest.TestCase):
    def test_gee_get_info_retries_transient_concurrency_errors(self):
        result = gee_get_info(DummyComputedObject())
        self.assertEqual(result, {"ok": True})


if __name__ == "__main__":
    unittest.main()
