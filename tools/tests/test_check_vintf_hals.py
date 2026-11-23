"""Testes do tools/check_vintf_hals.py: os HALs sem os quais o system_server do LineageOS 24 cai
precisam estar declarados no VINTF montado (vendor, odm e os APEX de vendor), antes de gastar um
boot no aparelho. No primeiro boot faltou o IPower e o system_server morreu no HintManagerService.

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import check_vintf_hals  # noqa: E402

REQUIRED = os.path.join(HERE, "..", "..", "configs", "vintf", "required_hals.txt")

AIDL_FQNAME = """<manifest version="1.0" type="device">
    <hal format="aidl">
        <name>android.hardware.power</name>
        <version>7</version>
        <fqname>IPower/default</fqname>
    </hal>
</manifest>
"""

AIDL_INTERFACE = """<manifest version="1.0" type="device">
    <hal format="aidl">
        <name>android.hardware.health</name>
        <interface>
            <name>IHealth</name>
            <instance>default</instance>
        </interface>
    </hal>
    <hal format="hidl">
        <name>android.hardware.media.c2</name>
        <transport>hwbinder</transport>
        <version>1.1</version>
        <interface>
            <name>IComponentStore</name>
            <instance>default</instance>
            <instance>software</instance>
        </interface>
    </hal>
</manifest>
"""


class CheckVintfTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = self.tmp.name

    def write(self, rel, text):
        path = os.path.join(self.out, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)

    def test_reads_fqname_and_interface_forms(self):
        self.write("vendor/etc/vintf/manifest/power.xml", AIDL_FQNAME)
        self.write("vendor/etc/vintf/manifest.xml", AIDL_INTERFACE)
        found = check_vintf_hals.find_declared(self.out)
        self.assertIn("android.hardware.power.IPower/default", found)
        self.assertIn("android.hardware.health.IHealth/default", found)
        self.assertIn("android.hardware.media.c2.IComponentStore/software", found)

    def test_reads_hidl_fqname_and_native_hal_without_interface_name(self):
        self.write("vendor/etc/vintf/manifest/x.xml", """<manifest version="1.0" type="device">
    <hal format="hidl">
        <name>android.hardware.media.c2</name>
        <transport>hwbinder</transport>
        <fqname>@1.1::IComponentStore/default</fqname>
    </hal>
    <hal format="native">
        <name>mapper</name>
        <version>5.0</version>
        <interface>
            <instance>minigbm</instance>
        </interface>
        <fqname>minigbm</fqname>
    </hal>
</manifest>
""")
        found = check_vintf_hals.find_declared(self.out)
        self.assertIn("android.hardware.media.c2.IComponentStore/default", found)
        self.assertIn("mapper./minigbm", found)

    def test_reads_vendor_apex_fragments_extracted_by_the_build(self):
        self.write("obj/PACKAGING/check_vintf_all_intermediates/apex/com.android.hardware.audio/"
                   "etc/vintf/audio.xml",
                   AIDL_FQNAME.replace("android.hardware.power", "android.hardware.audio.core")
                   .replace("IPower", "IModule"))
        found = check_vintf_hals.find_declared(self.out)
        self.assertIn("android.hardware.audio.core.IModule/default", found)

    def test_missing_reports_each_required_instance_with_reason(self):
        self.write("vendor/etc/vintf/manifest.xml", AIDL_INTERFACE)
        required = [("android.hardware.power.IPower/default", "HintManagerService")]
        missing = check_vintf_hals.find_missing(self.out, required)
        self.assertEqual(missing, required)

    def test_parse_required_ignores_comments(self):
        path = os.path.join(self.out, "req.txt")
        with open(path, "w") as f:
            f.write("# comentário\n\nandroid.hardware.power.IPower/default  HintManagerService cai\n")
        self.assertEqual(check_vintf_hals.read_required(path),
                         [("android.hardware.power.IPower/default", "HintManagerService cai")])

    def test_required_list_of_the_tree_has_power_and_audio(self):
        names = [name for name, _ in check_vintf_hals.read_required(REQUIRED)]
        self.assertIn("android.hardware.power.IPower/default", names)
        self.assertIn("android.hardware.audio.core.IModule/default", names)

    def test_main_fails_with_missing_list(self):
        self.write("vendor/etc/vintf/manifest.xml", AIDL_INTERFACE)
        self.write("vendor/etc/init/h.rc", "service h /vendor/bin/h\n"
                   "    interface aidl android.hardware.health.IHealth/default\n"
                   "    interface android.hardware.media.c2@1.1::IComponentStore default\n"
                   "    interface android.hardware.media.c2@1.1::IComponentStore software\n")
        req = os.path.join(self.out, "req.txt")
        with open(req, "w") as f:
            f.write("android.hardware.power.IPower/default HintManagerService\n")
        self.assertEqual(check_vintf_hals.main([self.out, "--required", req]), 1)
        with open(req, "w") as f:
            f.write("android.hardware.health.IHealth/default BatteryService\n")
        self.assertEqual(check_vintf_hals.main([self.out, "--required", req]), 0)


class InitInterfaceTest(unittest.TestCase):
    """Todo HAL AIDL/HIDL declarado no VINTF precisa de um serviço do init com a "interface"
    correspondente: é o que o servicemanager usa para subir o serviço sob demanda. No boot 3 o
    audioserver pediu o IModule/default 91 vezes e o init respondeu "Could not find
    'aidl/android.hardware.audio.core.IModule/default' for ctl.interface_start"."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = self.tmp.name

    def write(self, rel, text):
        path = os.path.join(self.out, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)

    def test_reads_aidl_and_hidl_interface_lines_from_vendor_and_apex(self):
        self.write("vendor/etc/init/power.rc",
                   "service vendor.power /vendor/bin/hw/power\n"
                   "    interface aidl android.hardware.power.IPower/default\n")
        self.write("obj/PACKAGING/check_vintf_all_intermediates/apex/x/etc/c2.rc",
                   "service c2 /apex/x/bin/c2\n"
                   "    interface android.hardware.media.c2@1.1::IComponentStore default\n")
        found = check_vintf_hals.find_init_interfaces(self.out)
        self.assertIn("android.hardware.power.IPower/default", found)
        self.assertIn("android.hardware.media.c2.IComponentStore/default", found)

    def test_declared_hal_without_init_interface_is_reported(self):
        self.write("vendor/etc/vintf/manifest/a.xml", AIDL_FQNAME + "")
        self.write("vendor/etc/init/other.rc", "service x /vendor/bin/x\n    class hal\n")
        self.assertEqual(check_vintf_hals.find_without_init_service(self.out),
                         ["android.hardware.power.IPower/default"])

    def test_native_hals_do_not_need_init_services(self):
        self.write("vendor/etc/vintf/manifest/m.xml", """<manifest version="1.0" type="device">
    <hal format="native">
        <name>mapper</name>
        <version>5.0</version>
        <interface>
            <instance>minigbm</instance>
        </interface>
    </hal>
</manifest>
""")
        self.assertEqual(check_vintf_hals.find_without_init_service(self.out), [])

    def test_main_fails_when_a_declared_hal_has_no_service(self):
        self.write("vendor/etc/vintf/manifest/a.xml", AIDL_FQNAME)
        req = os.path.join(self.out, "req.txt")
        with open(req, "w") as f:
            f.write("android.hardware.power.IPower/default HintManagerService\n")
        self.assertEqual(check_vintf_hals.main([self.out, "--required", req]), 1)
        self.write("vendor/etc/init/power.rc",
                   "service p /vendor/bin/p\n    interface aidl android.hardware.power.IPower/default\n")
        self.assertEqual(check_vintf_hals.main([self.out, "--required", req]), 0)


if __name__ == "__main__":
    unittest.main()
