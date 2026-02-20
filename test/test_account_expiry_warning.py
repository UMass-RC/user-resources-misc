#!/usr/bin/env python3
import contextlib
import io
import json
import re
import unittest
from datetime import datetime, timedelta
from unittest.mock import _patch, patch

from unity_user_resources_misc.unity_account_expiry_warning import _main

"""
see CONTRIBUTING.md for instructions on how to run tests
to debug a test, use the `debug` parameter for `configure_test`
"""


def days_from_today(x: int) -> str:
    return datetime.strftime(datetime.today() + timedelta(days=x), "%Y/%m/%d")


class MockHTTPResponse:
    def __init__(self, status: int, _bytes: bytes):
        self.status = status
        self._bytes = _bytes

    def read(self) -> bytes:
        return self._bytes


class TestCleanupQuotas(unittest.TestCase):
    patches: list[_patch]
    stdout_buffer: io.StringIO | None
    stderr_buffer: io.StringIO | None

    def configure_test(
        self,
        data: dict[str, dict[str, str]],
        current_user: str,
        current_user_groups: list[str] | None = None,
        idlelock_thresh=-1,
        idlelock_red_thresh=-1,
        group_thresh=-1,
        debug=False,
    ):
        current_user_groups = [] if current_user_groups is None else current_user_groups

        def urlopen(url: str, **kwargs):
            _, query_param = url.split("?")
            query_param_key, query_param_val = query_param.split("=")
            assert query_param_key == "uid"
            return MockHTTPResponse(200, json.dumps(data[query_param_val]).encode())

        prefix = "unity_user_resources_misc.unity_account_expiry_warning"
        self.patches = [
            patch(f"{prefix}.IDLELOCK_WARNING_THRESHOLD_DAYS", idlelock_thresh),
            patch(f"{prefix}.IDLELOCK_WARNING_RED_THRESHOLD_DAYS", idlelock_red_thresh),
            patch(f"{prefix}.PI_GROUP_OWNER_DISABLE_WARNING_RED_THRESHOLD_DAYS", group_thresh),
            patch(f"{prefix}.request.urlopen", urlopen),
            patch(f"{prefix}.os.getuid", lambda: 1),
            patch(f"{prefix}.pwd.getpwuid", lambda uidnumber: [current_user]),
            patch(f"{prefix}.os.getgroups", lambda: range(len(current_user_groups))),
            patch(f"{prefix}.grp.getgrgid", lambda gid: [current_user_groups[gid]]),
            patch(f"{prefix}.DEBUG", debug),
        ]
        for p in self.patches:
            p.start()
        self.stdout_buffer = io.StringIO()
        self.stderr_buffer = io.StringIO()

    def run_test(self) -> None:
        with contextlib.redirect_stdout(self.stdout_buffer):
            with contextlib.redirect_stderr(self.stderr_buffer):
                _main()

    def _assert_test_results(
        self, idlelock_warning, group_owners_warned: list[str], stderr_regex=r""
    ):
        assert self.stdout_buffer is not None and self.stderr_buffer is not None
        stdout = self.stdout_buffer.getvalue().strip()
        stdout_lines = stdout.splitlines()
        stderr = self.stderr_buffer.getvalue().strip()
        assert re.fullmatch(stderr_regex, stderr)
        # check for headers
        idlelock_warning_headers = [x for x in stdout_lines if "Account Expiration Warning" in x]
        group_warning_headers = [x for x in stdout_lines if "Group Owner Expiration Warning" in x]
        self.assertEqual(1 if idlelock_warning else 0, len(idlelock_warning_headers))
        # mulitple group warnings share the same header
        self.assertEqual(1 if len(group_owners_warned) > 0 else 0, len(group_warning_headers))
        # check for group names
        for owner in group_owners_warned:
            assert owner in stdout
        # cleanup
        self.stdout_buffer = None
        self.stderr_buffer = None
        for p in self.patches:
            p.stop()

    def assert_test_results(
        self, idlelock_warning, group_owners_warned: list[str], stderr_regex=r""
    ):
        assert self.stdout_buffer is not None and self.stderr_buffer is not None
        stdout_lines = self.stdout_buffer.getvalue().splitlines()
        stderr_lines = self.stderr_buffer.getvalue().splitlines()
        try:
            self._assert_test_results(
                idlelock_warning, group_owners_warned, stderr_regex=stderr_regex
            )
        except AssertionError as e:
            e.add_note(
                json.dumps({"stdout_lines": stdout_lines, "stderr_lines": stderr_lines}, indent=4)
            )
            raise e

    # END TOOLING
    ################################################################################################
    # BEGIN TEST CASES

    def test_no_warnings(self):
        self.configure_test(
            {
                "foo": {"idlelock_date": days_from_today(3)},
                "bar": {"disable_date": days_from_today(2)},
            },
            current_user="foo",
            current_user_groups=["pi_bar"],
            idlelock_thresh=2,
            idlelock_red_thresh=1,
            group_thresh=1,
        )
        self.run_test()
        self.assert_test_results(idlelock_warning=False, group_owners_warned=[])

    def test_idlelock_warning_lessthan(self):
        self.configure_test(
            {"foo": {"idlelock_date": days_from_today(1)}},
            current_user="foo",
            idlelock_thresh=2,
        )
        self.run_test()
        self.assert_test_results(idlelock_warning=True, group_owners_warned=[])

    def test_idlelock_warning_equalto(self):
        self.configure_test(
            {"foo": {"idlelock_date": days_from_today(2)}},
            current_user="foo",
            idlelock_thresh=2,
        )
        self.run_test()
        self.assert_test_results(idlelock_warning=True, group_owners_warned=[])

    def test_group_warning(self):
        self.configure_test(
            {
                "foo": {"idlelock_date": days_from_today(100)},
                "bar": {"disable_date": days_from_today(1)},
            },
            current_user="foo",
            current_user_groups=["pi_bar"],
            group_thresh=1,
            debug=True,
        )
        self.run_test()
        self.assert_test_results(idlelock_warning=False, group_owners_warned=["bar"])

    def test_multiple_group_warnings(self):
        self.configure_test(
            {
                "foo": {"idlelock_date": days_from_today(100)},
                "bar": {"disable_date": days_from_today(1)},
                "baz": {"disable_date": days_from_today(1)},
            },
            current_user="foo",
            current_user_groups=["pi_bar", "pi_baz"],
            group_thresh=1,
            debug=True,
        )
        self.run_test()
        self.assert_test_results(idlelock_warning=False, group_owners_warned=["bar", "baz"])
