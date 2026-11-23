"""Testes do configs/init/hy300-wifi-modules.sh: carrega os módulos do AIC8800 no boot (init) com o
firmware do /vendor, espera a interface e avisa por propriedade. Funções do Wi-Fi vêm do
hy300-wifi.sh (repositório do projeto), aqui trocadas por versões falsas.

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
"""
import os
import shutil
import stat
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "..", "configs", "init", "hy300-wifi-modules.sh")


class WifiModulesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hy300-wifimod-")
        self.addCleanup(shutil.rmtree, self.tmp)
        self.bin = os.path.join(self.tmp, "bin")
        os.makedirs(self.bin)
        self.calls = os.path.join(self.tmp, "calls")
        path = os.path.join(self.bin, "setprop")
        with open(path, "w") as f:
            f.write('#!/bin/sh\necho "setprop $*" >>"$FAKE_CALLS"\n')
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
        path = os.path.join(self.bin, "insmod")
        with open(path, "w") as f:
            f.write('#!/bin/sh\necho "insmod ${1##*/}" >>"$FAKE_CALLS"\n')
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
        self.with_btlpm = True

    def run_script(self, iface_found, load_rc=0):
        lib = os.path.join(self.tmp, "lib.sh")
        wait = "echo wlan0" if iface_found else "return 1"
        with open(lib, "w") as f:
            f.write(f'load_wifi_modules() {{ echo "load $1 $2" >>"$FAKE_CALLS"; return {load_rc}; }}\n'
                    f"wait_for_wireless_iface() {{ {wait}; }}\n")
        modules = os.path.join(self.tmp, "modules")
        os.makedirs(modules, exist_ok=True)
        if self.with_btlpm:
            open(os.path.join(modules, "aic8800_btlpm.ko"), "w").close()
        env = {"PATH": self.bin + ":" + os.environ["PATH"], "FAKE_CALLS": self.calls,
               "HY300_WIFI_LIB": lib, "HY300_WIFI_MODULE_DIR": modules}
        return subprocess.run(["/bin/sh", SCRIPT], env=env, capture_output=True, text=True,
                              timeout=60)

    def calls_text(self):
        with open(self.calls) as f:
            return f.read()

    def test_loads_with_vendor_firmware_and_reports_ready(self):
        r = self.run_script(True)
        self.assertEqual(r.returncode, 0, r.stderr)
        calls = self.calls_text()
        self.assertIn("/vendor/etc/firmware/aic8800", calls)
        self.assertIn("setprop vendor.hy300.wifi.iface wlan0", calls)

    def test_reports_failure_without_interface(self):
        r = self.run_script(False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("setprop vendor.hy300.wifi.iface falhou", self.calls_text())


    def test_loads_bluetooth_lpm_after_the_bsp(self):
        # aic8800_btlpm (rfkill do Bluetooth) depende do aic8800_bsp.
        self.run_script(True)
        calls = self.calls_text().splitlines()
        load = next(i for i, c in enumerate(calls) if c.startswith("load "))
        self.assertGreater(calls.index("insmod aic8800_btlpm.ko"), load)

    def test_wifi_does_not_depend_on_bluetooth(self):
        self.with_btlpm = False
        r = self.run_script(True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("insmod", self.calls_text())
        self.assertIn("setprop vendor.hy300.wifi.iface wlan0", self.calls_text())

    def test_no_bluetooth_module_when_the_bsp_failed(self):
        self.run_script(True, load_rc=1)
        self.assertNotIn("insmod aic8800_btlpm.ko", self.calls_text())


if __name__ == "__main__":
    unittest.main()
