"""Testes do configs/init/hy300-alpine.sh: ir do LineageOS ao Alpine e ficar nele, pelo adb.

Sem adb root (ro.debuggable=0) o shell não grava a misc, e um reboot normal cai no autoboot do
Alpine, que volta ao Lineage em 5 s. O shell pode setar debug.*: `setprop debug.hy300.alpine 1`
dispara o serviço root hy300-alpine (só no userdebug, com o adbd no ar), que grava a marca de ficar
na misc (0x10000, o mesmo formato do diag e do reboot-to-alpine.sh) e faz um reboot normal.

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
"""
import os
import shutil
import stat
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INIT = os.path.join(HERE, "..", "..", "configs", "init")
SCRIPT = os.path.join(INIT, "hy300-alpine.sh")
DIAG = os.path.join(INIT, "hy300-diag.sh")
MARK = b"hy300-ficar\0\x01\0\0\0"
MARK_OFFSET = 0x10000

FAKE_GETPROP = """#!/bin/sh
sed -n "s/^$1=//p" "$FAKE_PROPS"
"""


class AlpineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hy300-alpine-")
        self.addCleanup(shutil.rmtree, self.tmp)
        self.bin = os.path.join(self.tmp, "bin")
        self.log_dir = os.path.join(self.tmp, "metadata", "hy300-diag")
        self.props = os.path.join(self.tmp, "props")
        self.calls = os.path.join(self.tmp, "calls")
        os.makedirs(self.bin)
        self.set_build_type("userdebug")
        self.fake("getprop", FAKE_GETPROP)
        self.fake("setprop", '#!/bin/sh\necho "setprop $*" >>"$FAKE_CALLS"\n')
        self.fake("sync", '#!/bin/sh\necho sync >>"$FAKE_CALLS"\n')

    def fake(self, name, body):
        path = os.path.join(self.bin, name)
        with open(path, "w") as f:
            f.write(body)
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)

    def set_build_type(self, build_type):
        with open(self.props, "w") as f:
            f.write(f"ro.build.type={build_type}\ndebug.hy300.alpine=1\n")

    def make_misc(self, area=bytes(16)):
        misc = os.path.join(self.tmp, "misc")
        data = bytearray(4 * 1024 * 1024)
        data[MARK_OFFSET:MARK_OFFSET + 16] = area
        with open(misc, "wb") as f:
            f.write(data)
        return misc, bytes(data)

    def run_script(self, misc):
        env = {"PATH": self.bin + ":" + os.environ["PATH"], "FAKE_PROPS": self.props,
               "FAKE_CALLS": self.calls, "HY300_DIAG_MISC": misc,
               "HY300_ALPINE_DIAG_LIB": DIAG, "HY300_ALPINE_LOG_DIR": self.log_dir}
        return subprocess.run(["/bin/sh", SCRIPT], env=env, capture_output=True, text=True,
                              timeout=60)

    def calls_text(self):
        return open(self.calls).read() if os.path.exists(self.calls) else ""

    def read_bytes(self, path):
        with open(path, "rb") as f:
            return f.read()

    def test_marks_misc_and_reboots_normally(self):
        misc, before = self.make_misc()
        r = self.run_script(misc)
        self.assertEqual(r.returncode, 0, r.stderr)
        after = self.read_bytes(misc)
        self.assertEqual(after[MARK_OFFSET:MARK_OFFSET + 16], MARK)
        self.assertEqual(after[:MARK_OFFSET], before[:MARK_OFFSET])
        self.assertEqual(after[MARK_OFFSET + 16:], before[MARK_OFFSET + 16:])
        calls = self.calls_text()
        self.assertIn("setprop sys.powerctl reboot\n", calls)
        self.assertNotIn("recovery", calls)
        self.assertLess(calls.index("sync"), calls.index("setprop sys.powerctl"))

    def test_resets_the_trigger_property(self):
        misc, _ = self.make_misc()
        self.run_script(misc)
        self.assertIn("setprop debug.hy300.alpine 0", self.calls_text())

    def test_does_not_reboot_when_the_mark_area_is_taken(self):
        misc, before = self.make_misc(b"hy300-boots \x02\0\0\0")
        r = self.run_script(misc)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.read_bytes(misc), before)
        self.assertNotIn("sys.powerctl", self.calls_text())
        with open(os.path.join(self.log_dir, "alpine.txt")) as f:
            self.assertIn("marca de ficar NÃO gravada", f.read())

    def test_logs_the_request(self):
        misc, _ = self.make_misc()
        self.run_script(misc)
        with open(os.path.join(self.log_dir, "alpine.txt")) as f:
            self.assertIn("marca de ficar gravada", f.read())

    def test_does_nothing_on_user_build(self):
        self.set_build_type("user")
        misc, before = self.make_misc()
        self.run_script(misc)
        self.assertEqual(self.read_bytes(misc), before)
        self.assertNotIn("sys.powerctl", self.calls_text())


if __name__ == "__main__":
    unittest.main()
