"""O grupo do motor de foco e dos LEDs tem de bater em três lugares: o AID do config.fs, o
mapeamento permissão -> gid no /product e o chown do init.rk3566.rc. Um nome errado faz o init
ou o system_server ignorarem o grupo sem erro visível.

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
"""
import os
import re
import unittest
import xml.etree.ElementTree as ET

TREE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")


def read(*parts):
    with open(os.path.join(TREE, *parts)) as handle:
        return handle.read()


class HwGroupTest(unittest.TestCase):
    def test_aid_is_in_the_vendor_range(self):
        match = re.search(r"\[AID_VENDOR_HY300_HW\]\s*value:\s*(\d+)", read("config.fs"))
        self.assertIsNotNone(match)
        self.assertTrue(2900 <= int(match.group(1)) <= 2999)

    def test_permission_maps_to_the_aid_group(self):
        root = ET.fromstring(read("configs", "permissions", "hy300-hw-permissions.xml"))
        permission = root.find("permission")
        self.assertEqual(permission.get("name"), "io.github.hy300.permission.PROJECTOR_HARDWARE")
        self.assertEqual(permission.find("group").get("gid"), "vendor_hy300_hw")

    def test_init_gives_the_motor_and_leds_to_the_group_only(self):
        rc = read("configs", "init", "init.rk3566.rc")
        for node in ("/sys/class/motor_cc/motor_cc/motor", "/sys/class/leds/green/brightness",
                     "/sys/class/leds/red/brightness"):
            self.assertIn(f"chown root vendor_hy300_hw {node}", rc)
            self.assertIn(f"chmod 0660 {node}", rc)
        self.assertNotIn("chmod 0666", rc)


if __name__ == "__main__":
    unittest.main()
