"""Testes do núcleo do HAL de sensores (sensors/core): configuração, IIO e input com dispositivos
falsos (árvore sysfs temporária e pipe). Compila com o compilador do host, sem o Soong.

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
"""
import glob
import os
import sys
import unittest
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import host_gtest  # noqa: E402

SENSORS = os.path.join(HERE, "..", "..", "sensors")


@unittest.skipUnless(host_gtest.find_compiler() and host_gtest.has_gtest(host_gtest.find_compiler()),
                     "sem compilador C++ ou gtest no host")
class SensorsCoreGtest(unittest.TestCase):
    def test_gtest_of_the_core_passes(self):
        sources = sorted(glob.glob(os.path.join(SENSORS, "core", "*.cpp")))
        sources.append(os.path.join(SENSORS, "tests", "AccelCoreTest.cpp"))
        result = host_gtest.run_sources(sources, [f"-I{os.path.join(SENSORS, 'core')}"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASSED", result.stdout)


class SensorsHalFilesTest(unittest.TestCase):
    def test_rc_declares_the_aidl_interface(self):
        with open(os.path.join(SENSORS, "hal", "android.hardware.sensors-service.hy300.rc")) as rc:
            self.assertIn("interface aidl android.hardware.sensors.ISensors/default", rc.read())

    def test_vintf_fragment_declares_isensors_default(self):
        root = ET.parse(os.path.join(SENSORS, "hal",
                                     "android.hardware.sensors-service.hy300.xml")).getroot()
        hal = root.find("hal")
        self.assertEqual(hal.findtext("name"), "android.hardware.sensors")
        self.assertEqual(hal.findtext("fqname"), "ISensors/default")


if __name__ == "__main__":
    unittest.main()
