"""Testes do configs/init/hy300-diag.sh: diagnóstico do primeiro boot do LineageOS sem rede.

O script roda no /bin/sh do host com comandos falsos no PATH (getprop, logcat, dmesg, dumpsys,
setprop...) e diretórios temporários no lugar de /metadata, /proc/uptime e /sys. As funções são
testadas uma a uma (HY300_DIAG_LIB=1 só define as funções) e o ciclo completo com tempos curtos.

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
"""
import os
import shutil
import stat
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "..", "configs", "init", "hy300-diag.sh")

FAKE_GETPROP = """#!/bin/sh
# getprop falso: lê "nome=valor" de $FAKE_PROPS; sem argumento, lista tudo.
[ -z "$1" ] && { sed 's/^\\(.*\\)=\\(.*\\)$/[\\1]: [\\2]/' "$FAKE_PROPS"; exit 0; }
sed -n "s/^$1=//p" "$FAKE_PROPS"
"""


class DiagTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hy300-diag-")
        self.addCleanup(shutil.rmtree, self.tmp)
        self.bin = os.path.join(self.tmp, "bin")
        self.root = os.path.join(self.tmp, "metadata", "hy300-diag")
        self.props = os.path.join(self.tmp, "props")
        self.uptime = os.path.join(self.tmp, "uptime")
        self.calls = os.path.join(self.tmp, "calls")
        os.makedirs(self.bin)
        self.set_props(**{"ro.build.type": "userdebug", "ro.boot.hy300.diag": "1"})
        self.set_uptime(12.5)
        self.fake("getprop", FAKE_GETPROP)
        for name in ("logcat", "dmesg", "dumpsys", "lsmod", "ps", "lshal", "iw", "ip", "insmod"):
            self.fake(name, f'#!/bin/sh\necho "{name} $*" >>"$FAKE_CALLS"\necho "saida de {name} $*"\n')
        self.fake("setprop", '#!/bin/sh\necho "setprop $*" >>"$FAKE_CALLS"\n')
        self.fake("sleep", '#!/bin/sh\nexit 0\n')
        self.fake("sync", '#!/bin/sh\necho sync >>"$FAKE_CALLS"\n')

    def fake(self, name, body):
        path = os.path.join(self.bin, name)
        with open(path, "w") as f:
            f.write(body)
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)

    def set_props(self, **props):
        with open(self.props, "w") as f:
            f.writelines(f"{k}={v}\n" for k, v in props.items())

    def set_uptime(self, seconds):
        with open(self.uptime, "w") as f:
            f.write(f"{seconds} 100.00\n")

    def env(self, **extra):
        env = {
            "PATH": self.bin + ":" + os.environ["PATH"],
            "FAKE_PROPS": self.props,
            "FAKE_CALLS": self.calls,
            "HY300_DIAG_ROOT": self.root,
            "HY300_DIAG_UPTIME": self.uptime,
            "HY300_DIAG_SYS": os.path.join(self.tmp, "sys"),
            "HY300_DIAG_PROC": os.path.join(self.tmp, "proc"),
            "HY300_DIAG_WIFI": "0",
            "HY300_DIAG_MISC": os.path.join(self.tmp, "sem-misc"),
        }
        env.update(extra)
        return env

    def run_lib(self, code, **extra):
        script = f'HY300_DIAG_LIB=1 . "{SCRIPT}"; {code}'
        env = self.env(**extra)
        return subprocess.run(["/bin/sh", "-c", script], env=env, capture_output=True,
                              text=True, timeout=60)

    def run_main(self, **extra):
        return subprocess.run(["sh", SCRIPT], env=self.env(**extra), capture_output=True, text=True,
                              timeout=60)

    def read(self, *parts):
        with open(os.path.join(*parts)) as f:
            return f.read()

    def calls_text(self):
        return self.read(self.calls) if os.path.exists(self.calls) else ""


class EnabledTest(DiagTestBase):
    def test_enabled_by_cmdline_prop(self):
        self.assertEqual(self.run_lib("is_diag_enabled").returncode, 0)

    def test_enabled_by_file_on_metadata(self):
        self.set_props(**{"ro.build.type": "userdebug"})
        os.makedirs(self.root)
        open(os.path.join(self.root, "ativo"), "w").close()
        self.assertEqual(self.run_lib("is_diag_enabled").returncode, 0)

    def test_disabled_without_prop_or_file(self):
        self.set_props(**{"ro.build.type": "userdebug"})
        self.assertNotEqual(self.run_lib("is_diag_enabled").returncode, 0)

    def test_disabled_on_user_build(self):
        self.set_props(**{"ro.build.type": "user", "ro.boot.hy300.diag": "1"})
        self.assertNotEqual(self.run_lib("is_diag_enabled").returncode, 0)

    def test_enabled_on_userdebug_even_with_ro_debuggable_0(self):
        # O LineageOS liga PRODUCT_NOT_DEBUGGABLE_IN_USERDEBUG: no userdebug, ro.debuggable=0.
        self.set_props(**{"ro.build.type": "userdebug", "ro.debuggable": "0",
                          "ro.boot.hy300.diag": "1"})
        self.assertEqual(self.run_lib("is_diag_enabled").returncode, 0)

    def test_disabled_on_user_build_with_file(self):
        self.set_props(**{"ro.build.type": "user"})
        os.makedirs(self.root)
        open(os.path.join(self.root, "ativo"), "w").close()
        self.assertNotEqual(self.run_lib("is_diag_enabled").returncode, 0)

    def test_main_does_nothing_when_disabled(self):
        self.set_props(**{"ro.build.type": "userdebug"})
        r = self.run_main()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(self.root))
        self.assertNotIn("setprop", self.calls_text())


class PathTest(DiagTestBase):
    def test_path_reaches_system_binaries(self):
        # logcat, ip e iw ficam em /system/bin; o diag não pode depender do PATH de quem o chamou.
        r = self.run_lib('echo "$PATH"', PATH="/vendor/bin:/vendor/xbin:" + self.bin)
        entries = r.stdout.strip().split(":")
        self.assertIn("/system/bin", entries)
        self.assertLess(entries.index("/system/bin"), entries.index("/vendor/bin"))


class BootDirTest(DiagTestBase):
    def test_first_boot_is_1_and_counter_grows(self):
        first = self.run_lib('next_boot_dir "$HY300_DIAG_ROOT"').stdout.strip()
        second = self.run_lib('next_boot_dir "$HY300_DIAG_ROOT"').stdout.strip()
        self.assertEqual(first, os.path.join(self.root, "1"))
        self.assertEqual(second, os.path.join(self.root, "2"))
        self.assertTrue(os.path.isdir(second))
        self.assertEqual(self.read(self.root, "contador").strip(), "2")

    def test_garbage_counter_restarts_at_1(self):
        os.makedirs(self.root)
        with open(os.path.join(self.root, "contador"), "w") as f:
            f.write("abc\n")
        out = self.run_lib('next_boot_dir "$HY300_DIAG_ROOT"').stdout.strip()
        self.assertEqual(out, os.path.join(self.root, "1"))


class PruneTest(DiagTestBase):
    def test_keeps_only_last_boots(self):
        # O metadata tem 16 MiB: só as últimas 3 coletas ficam.
        for _ in range(5):
            self.run_lib('next_boot_dir "$HY300_DIAG_ROOT"')
        r = self.run_lib('prune_old_boots "$HY300_DIAG_ROOT" 3')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(os.listdir(self.root)), ["3", "4", "5", "contador"])

    def test_prune_keeps_unknown_files(self):
        os.makedirs(os.path.join(self.root, "outro"))
        open(os.path.join(self.root, "ativo"), "w").close()
        for _ in range(4):
            self.run_lib('next_boot_dir "$HY300_DIAG_ROOT"')
        self.run_lib('prune_old_boots "$HY300_DIAG_ROOT" 3')
        self.assertEqual(sorted(os.listdir(self.root)), ["2", "3", "4", "ativo", "contador", "outro"])


class UptimeTest(DiagTestBase):
    def test_uptime_seconds_is_integer(self):
        self.set_uptime(481.93)
        self.assertEqual(self.run_lib("uptime_seconds").stdout.strip(), "481")


class SnapshotTest(DiagTestBase):
    def test_snapshot_writes_dmesg_logcat_and_props_and_syncs(self):
        d = os.path.join(self.tmp, "boot")
        os.makedirs(d)
        r = self.run_lib(f'snapshot "{d}"')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("saida de dmesg", self.read(d, "dmesg.txt"))
        self.assertIn("saida de logcat -b all -d -v threadtime", self.read(d, "logcat.txt"))
        self.assertIn("[ro.boot.hy300.diag]: [1]", self.read(d, "getprop.txt"))
        self.assertIn("sync", self.calls_text())

    def test_snapshot_keeps_interrupt_counts(self):
        # Para conferir a tempestade de IRQ (a "GPIO Key Home" com as células do DT trocadas).
        d = os.path.join(self.tmp, "boot")
        os.makedirs(d)
        proc = os.path.join(self.tmp, "proc")
        os.makedirs(proc)
        with open(os.path.join(proc, "interrupts"), "w") as f:
            f.write(" 87:          3   GPIO Key Home\n")
        self.run_lib(f'snapshot "{d}"')
        self.assertIn("GPIO Key Home", self.read(d, "interrupts.txt"))

    def test_after_boot_collects_system_state(self):
        d = os.path.join(self.tmp, "boot")
        os.makedirs(d)
        proc = os.path.join(self.tmp, "proc")
        os.makedirs(proc)
        with open(os.path.join(proc, "meminfo"), "w") as f:
            f.write("MemTotal: 1500000 kB\n")
        cpufreq = os.path.join(self.tmp, "sys", "devices", "system", "cpu", "cpufreq", "policy0")
        os.makedirs(cpufreq)
        with open(os.path.join(cpufreq, "scaling_cur_freq"), "w") as f:
            f.write("1800000\n")
        r = self.run_lib(f'collect_after_boot "{d}"')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("dumpsys SurfaceFlinger", self.calls_text())
        self.assertIn("dumpsys media.player", self.calls_text())
        self.assertIn("MemTotal", self.read(d, "meminfo.txt"))
        self.assertIn("1800000", self.read(d, "freq.txt"))
        self.assertIn("saida de lsmod", self.read(d, "lsmod.txt"))
        self.assertIn("saida de ps -A", self.read(d, "ps.txt"))


class MainLoopTest(DiagTestBase):
    def test_reboots_normally_after_deadline_without_boot_completed(self):
        self.set_uptime(500)
        r = self.run_main(HY300_DIAG_REBOOT_AFTER="480")
        self.assertEqual(r.returncode, 0, r.stderr)
        calls = self.calls_text()
        self.assertIn("setprop sys.powerctl reboot\n", calls)
        self.assertNotIn("recovery", calls)
        self.assertNotIn("bootloader", calls)
        log = self.read(self.root, "1", "diag.txt")
        self.assertIn("reinício normal", log)
        self.assertIn("saida de dmesg", self.read(self.root, "1", "dmesg.txt"))

    def test_collects_once_after_boot_completed(self):
        self.set_props(**{"ro.build.type": "userdebug", "ro.boot.hy300.diag": "1",
                          "sys.boot_completed": "1"})
        self.set_uptime(500)
        self.run_main(HY300_DIAG_REBOOT_AFTER="480")
        self.assertEqual(self.calls_text().count("dumpsys SurfaceFlinger"), 1)
        self.assertTrue(os.path.exists(os.path.join(self.root, "1", "meminfo.txt")))


MARK = b"hy300-ficar\0\x01\0\0\0"
MARK_OFFSET = 0x10000


class StayMarkTest(DiagTestBase):
    """Antes do reboot o diag grava a marca de "ficar" do Alpine (misc 0x10000), para ele não
    voltar sozinho ao Lineage e os logs poderem ser lidos. Mesmo formato do
    scripts/reboot-to-alpine.sh do hy300-alpine; só grava se a área estiver zerada ou já marcada."""

    def make_misc(self, area=bytes(16)):
        misc = os.path.join(self.tmp, "misc")
        data = bytearray(4 * 1024 * 1024)
        data[:13] = b"boot-recovery"
        data[MARK_OFFSET:MARK_OFFSET + 16] = area
        with open(misc, "wb") as f:
            f.write(data)
        return misc, bytes(data)

    def read_bytes(self, path):
        with open(path, "rb") as f:
            return f.read()

    def test_writes_mark_on_zero_area_and_nothing_else(self):
        misc, before = self.make_misc()
        r = self.run_lib(f'write_stay_mark "{misc}"')
        self.assertEqual(r.returncode, 0, r.stderr)
        after = self.read_bytes(misc)
        self.assertEqual(after[MARK_OFFSET:MARK_OFFSET + 16], MARK)
        self.assertEqual(after[:MARK_OFFSET], before[:MARK_OFFSET])
        self.assertEqual(after[MARK_OFFSET + 16:], before[MARK_OFFSET + 16:])

    def test_keeps_existing_mark(self):
        misc, before = self.make_misc(MARK)
        self.assertEqual(self.run_lib(f'write_stay_mark "{misc}"').returncode, 0)
        self.assertEqual(self.read_bytes(misc), before)

    def test_refuses_unknown_data(self):
        misc, before = self.make_misc(b"hy300-boots \x02\0\0\0")
        self.assertNotEqual(self.run_lib(f'write_stay_mark "{misc}"').returncode, 0)
        self.assertEqual(self.read_bytes(misc), before)

    def test_main_marks_before_reboot(self):
        misc, _ = self.make_misc()
        self.set_uptime(500)
        self.run_main(HY300_DIAG_REBOOT_AFTER="480", HY300_DIAG_MISC=misc)
        self.assertEqual(self.read_bytes(misc)[MARK_OFFSET:MARK_OFFSET + 16], MARK)
        self.assertIn("marca de ficar", self.read(self.root, "1", "diag.txt"))


class WifiTest(DiagTestBase):
    """Os módulos do AIC8800 sobem pelo init (hy300-wifi-modules) e o Wi-Fi é do Android. O diag só
    registra o estado; carrega os módulos ele mesmo só se a interface não aparecer."""

    def write_lib(self, iface_found):
        lib = os.path.join(self.tmp, "hy300-wifi.sh")
        wait = "echo wlan0" if iface_found else "return 1"
        with open(lib, "w") as f:
            f.write("has_wifi_card() { return 0; }\n"
                    "load_wifi_modules() { echo \"load $1 $2\" >>\"$FAKE_CALLS\"; }\n"
                    f"wait_for_wireless_iface() {{ {wait}; }}\n"
                    "dump_sdio_state() { echo estado-sdio; }\n"
                    "recover_wifi_chip() { echo religado; }\n"
                    "unload_wifi_modules() { return 0; }\n")
        return lib

    def test_records_state_without_loading_or_scanning_when_init_loaded_the_driver(self):
        self.fake("iw", '#!/bin/sh\necho "iw $*" >>"$FAKE_CALLS"\n'
                        'printf "Connected to aa:bb:cc:dd:ee:01 (on wlan0)\\n\\tSSID: Casa\\n'
                        '\\tsignal: -50 dBm\\n"\n')
        d = os.path.join(self.tmp, "boot")
        os.makedirs(d)
        r = self.run_lib(f'run_wifi_test "{d}"', HY300_DIAG_WIFI_LIB=self.write_lib(True))
        self.assertEqual(r.returncode, 0, r.stderr)
        report = self.read(d, "wifi.txt")
        self.assertIn("interface wlan0", report)
        self.assertIn("signal: -50 dBm", report)
        self.assertNotIn("Casa", report)
        self.assertNotIn("aa:bb:cc", report)
        calls = self.calls_text()
        self.assertNotIn("load ", calls)
        self.assertNotIn("scan", calls)

    def test_loads_and_recovers_when_the_interface_never_shows_up(self):
        d = os.path.join(self.tmp, "boot")
        os.makedirs(d)
        self.run_lib(f'run_wifi_test "{d}"', HY300_DIAG_WIFI_LIB=self.write_lib(False))
        report = self.read(d, "wifi.txt")
        self.assertIn("sem interface sem fio", report)
        self.assertIn("estado-sdio", report)
        self.assertIn("religado", report)
        self.assertIn("load ", self.calls_text())


class NetworkAdbTest(DiagTestBase):
    """O retorno aos 480 s só acontece se o adb pela rede NÃO estiver de pé: com o adbd na porta
    5555 e IP no wlan0, quem conduz é o adb."""

    def set_network_adb(self, adbd, port, ip_output):
        self.set_props(**{"ro.build.type": "userdebug", "ro.boot.hy300.diag": "1",
                          "init.svc.adbd": adbd, "service.adb.tcp.port": port})
        self.fake("ip", f'#!/bin/sh\necho "ip $*" >>"$FAKE_CALLS"\nprintf "{ip_output}"\n')

    def test_up_with_adbd_port_and_ipv4(self):
        self.set_network_adb("running", "5555", "    inet 192.0.2.10/24 brd 192.0.2.255 scope global wlan0\\n")
        self.assertEqual(self.run_lib("is_network_adb_up").returncode, 0)

    def test_down_without_ipv4(self):
        self.set_network_adb("running", "5555", "")
        self.assertNotEqual(self.run_lib("is_network_adb_up").returncode, 0)

    def test_down_without_tcp_port(self):
        self.set_network_adb("running", "", "    inet 192.0.2.10/24 scope global wlan0\\n")
        self.assertNotEqual(self.run_lib("is_network_adb_up").returncode, 0)

    def test_main_does_not_reboot_when_network_adb_is_up(self):
        self.set_network_adb("running", "5555", "    inet 192.0.2.10/24 scope global wlan0\\n")
        self.set_uptime(500)
        r = self.run_main(HY300_DIAG_REBOOT_AFTER="480", HY300_DIAG_MAX_LOOPS="1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("setprop sys.powerctl reboot", self.calls_text())
        self.assertIn("adb pela rede no ar", self.read(self.root, "1", "diag.txt"))


    def test_stops_collecting_after_boot_when_network_adb_is_up(self):
        # Rodada 6: com o boot completo e o adb pela rede no ar, o dmesg como root a cada 20 s
        # deixava o processo em estado D e gastava CPU. Quem conduz é o adb: as coletas param.
        self.set_network_adb("running", "5555", "    inet 192.0.2.10/24 scope global wlan0\\n")
        with open(self.props, "a") as f:
            f.write("sys.boot_completed=1\n")
        self.set_uptime(100)
        r = self.run_main(HY300_DIAG_REBOOT_AFTER="480", HY300_DIAG_MAX_LOOPS="5")
        self.assertEqual(r.returncode, 0, r.stderr)
        calls = self.calls_text()
        self.assertEqual(calls.count("dmesg"), 1, calls)
        self.assertEqual(calls.count("logcat -b all"), 1, calls)
        self.assertNotIn("setprop sys.powerctl reboot", calls)
        self.assertIn("coletas suspensas", self.read(self.root, "1", "diag.txt"))

    def test_exits_after_deadline_when_network_adb_is_up(self):
        # Depois do prazo, com o adb no ar, o diag termina em vez de continuar em laço.
        self.set_network_adb("running", "5555", "    inet 192.0.2.10/24 scope global wlan0\\n")
        with open(self.props, "a") as f:
            f.write("sys.boot_completed=1\n")
        self.set_uptime(500)
        r = self.run_main(HY300_DIAG_REBOOT_AFTER="480")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("setprop sys.powerctl reboot", self.calls_text())
        self.assertIn("diag encerrado", self.read(self.root, "1", "diag.txt"))

    def test_keeps_collecting_while_network_adb_is_down(self):
        self.set_network_adb("running", "5555", "")
        with open(self.props, "a") as f:
            f.write("sys.boot_completed=1\n")
        self.set_uptime(100)
        r = self.run_main(HY300_DIAG_REBOOT_AFTER="480", HY300_DIAG_MAX_LOOPS="3")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.calls_text().count("dmesg"), 3)


if __name__ == "__main__":
    unittest.main()
