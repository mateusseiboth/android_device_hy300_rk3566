"""Testes do configs/init/hy300-net.sh: rede e adb pela rede no userdebug, sem credencial na imagem.

O Alpine grava em /metadata/hy300-diag/ (fora do /data, ext4 sem criptografia):
- wifi.conf (modo 600): WIFI_SSID=..., WIFI_PSK=..., WIFI_SECURITY=wpa2|wpa3|open (opcional);
- adb_keys: a chave pública do PC.
Depois do boot_completed o script liga o adb pela rede (porta 5555, autenticação mantida), instala
a chave em /data/misc/adb/adb_keys, conecta o Wi-Fi com `cmd wifi connect-network` e apaga o
wifi.conf. Roda no sh do host com comandos falsos no PATH.

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
"""
import os
import shutil
import stat
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "..", "configs", "init", "hy300-net.sh")

FAKE_GETPROP = """#!/bin/sh
[ -z "$1" ] && exit 0
sed -n "s/^$1=//p" "$FAKE_PROPS"
"""


class NetTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hy300-net-")
        self.addCleanup(shutil.rmtree, self.tmp)
        self.bin = os.path.join(self.tmp, "bin")
        self.root = os.path.join(self.tmp, "metadata", "hy300-diag")
        self.adb_dir = os.path.join(self.tmp, "data", "misc", "adb")
        self.props = os.path.join(self.tmp, "props")
        self.calls = os.path.join(self.tmp, "calls")
        os.makedirs(self.bin)
        os.makedirs(self.root)
        os.makedirs(self.adb_dir)
        with open(self.props, "w") as f:
            f.write("ro.build.type=userdebug\nsys.boot_completed=1\n")
        self.fake("getprop", FAKE_GETPROP)
        for name in ("setprop", "settings", "chown", "chmod", "sleep", "sync"):
            self.fake(name, f'#!/bin/sh\necho "{name} $*" >>"$FAKE_CALLS"\n')
        self.fake("cmd", '#!/bin/sh\nfor a in "$@"; do printf "[%s]" "$a"; done >>"$FAKE_CALLS"\n'
                         'echo >>"$FAKE_CALLS"\necho "${FAKE_CMD_OUT:-}"\n')

    def fake(self, name, body):
        path = os.path.join(self.bin, name)
        with open(path, "w") as f:
            f.write(body)
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)

    def write_conf(self, text, mode=0o600):
        path = os.path.join(self.root, "wifi.conf")
        with open(path, "w") as f:
            f.write(text)
        os.chmod(path, mode)
        return path

    def env(self, **extra):
        env = {"PATH": self.bin + ":" + os.environ["PATH"], "FAKE_PROPS": self.props,
               "FAKE_CALLS": self.calls, "HY300_NET_ROOT": self.root,
               "HY300_NET_ADB_DIR": self.adb_dir, "HY300_NET_WAIT": "1"}
        env.update(extra)
        return env

    def run_lib(self, code, **extra):
        return subprocess.run(["/bin/sh", "-c", f'HY300_NET_LIB=1 . "{SCRIPT}"; {code}'],
                              env=self.env(**extra), capture_output=True, text=True, timeout=60)

    def run_main(self, **extra):
        return subprocess.run(["/bin/sh", SCRIPT], env=self.env(**extra), capture_output=True,
                              text=True, timeout=60)

    def calls_text(self):
        if not os.path.exists(self.calls):
            return ""
        with open(self.calls) as f:
            return f.read()


class WifiConfTest(NetTestBase):
    def test_reads_ssid_psk_and_default_security(self):
        conf = self.write_conf("# rede de casa\nWIFI_SSID=Minha Rede\nWIFI_PSK=senha=com=igual\n")
        r = self.run_lib(f'read_wifi_conf "{conf}" && echo "$WIFI_SSID|$WIFI_PSK|$WIFI_SECURITY"')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "Minha Rede|senha=com=igual|wpa2")

    def test_does_not_execute_the_file(self):
        conf = self.write_conf('WIFI_SSID=$(touch pwned)\nWIFI_PSK=`touch pwned2`\n')
        r = self.run_lib(f'cd "{self.tmp}"; read_wifi_conf "{conf}"; echo "$WIFI_SSID"')
        self.assertEqual(r.stdout.strip(), "$(touch pwned)")
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "pwned")))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "pwned2")))

    def test_refuses_conf_readable_by_others(self):
        conf = self.write_conf("WIFI_SSID=a\nWIFI_PSK=b\n", mode=0o644)
        self.assertNotEqual(self.run_lib(f'read_wifi_conf "{conf}"').returncode, 0)

    def test_refuses_conf_without_ssid(self):
        conf = self.write_conf("WIFI_PSK=b\n")
        self.assertNotEqual(self.run_lib(f'read_wifi_conf "{conf}"').returncode, 0)


class MainTest(NetTestBase):
    def test_connects_with_cmd_wifi_and_deletes_conf(self):
        self.write_conf("WIFI_SSID=Minha Rede\nWIFI_PSK=segredo\n")
        r = self.run_main(FAKE_CMD_OUT="Connection initiated")
        self.assertEqual(r.returncode, 0, r.stderr)
        calls = self.calls_text()
        self.assertIn("[wifi][set-wifi-enabled][enabled]", calls)
        self.assertIn("[wifi][connect-network][Minha Rede][wpa2][segredo]", calls)
        self.assertFalse(os.path.exists(os.path.join(self.root, "wifi.conf")))

    def test_log_never_has_the_password(self):
        self.write_conf("WIFI_SSID=Minha Rede\nWIFI_PSK=segredo\n")
        self.run_main()
        with open(os.path.join(self.root, "net.txt")) as f:
            log = f.read()
        self.assertNotIn("segredo", log)
        self.assertIn("conectando", log)

    def test_open_network_has_no_passphrase(self):
        self.write_conf("WIFI_SSID=Aberta\nWIFI_SECURITY=open\n")
        self.run_main()
        self.assertIn("[wifi][connect-network][Aberta][open]\n", self.calls_text())

    def test_enables_adb_over_network_keeping_authentication(self):
        self.run_main()
        calls = self.calls_text()
        self.assertIn("settings put global adb_enabled 1", calls)
        self.assertIn("setprop service.adb.tcp.port 5555", calls)
        self.assertIn("setprop ctl.restart adbd", calls)
        self.assertNotIn("ro.adb.secure", calls)
        self.assertNotIn("auth", calls)

    def test_installs_adb_key_once(self):
        key = "QAAAAexemplo= usuario@pc\n"
        with open(os.path.join(self.root, "adb_keys"), "w") as f:
            f.write(key)
        self.run_main()
        self.run_main()
        with open(os.path.join(self.adb_dir, "adb_keys")) as f:
            self.assertEqual(f.read(), key)
        self.assertIn("chmod 0640", self.calls_text())

    def test_does_nothing_on_user_build(self):
        with open(self.props, "w") as f:
            f.write("ro.build.type=user\nsys.boot_completed=1\n")
        self.write_conf("WIFI_SSID=a\nWIFI_PSK=b\n")
        self.run_main()
        self.assertEqual(self.calls_text(), "")
        self.assertTrue(os.path.exists(os.path.join(self.root, "wifi.conf")))


if __name__ == "__main__":
    unittest.main()
