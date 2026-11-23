"""Testes do preparo da UART do Bluetooth (bluetooth/): configuração, rfkill numa árvore sysfs
falsa e termios num pty, compilados no host. E o patch hardware/interfaces/0002, que dá ao HAL
AIDL padrão a "interface" no init.

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import host_gtest  # noqa: E402

TREE = os.path.join(HERE, "..", "..")
BT = os.path.join(TREE, "bluetooth")


@unittest.skipUnless(host_gtest.find_compiler() and host_gtest.has_gtest(host_gtest.find_compiler()),
                     "sem compilador C++ ou gtest no host")
class BtUartGtest(unittest.TestCase):
    def test_gtest_of_the_uart_setup_passes(self):
        result = host_gtest.run_sources(
            [os.path.join(BT, "BtUart.cpp"), os.path.join(BT, "tests", "BtUartTest.cpp")],
            [f"-I{BT}", "-lutil"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASSED", result.stdout)


class BluetoothFilesTest(unittest.TestCase):
    def test_hal_rc_patch_adds_the_aidl_interface(self):
        with open(os.path.join(TREE, "patches", "hardware", "interfaces",
                               "0002-bluetooth-interface-no-init.patch")) as patch:
            self.assertIn("+    interface aidl android.hardware.bluetooth.IBluetoothHci/default",
                          patch.read())

    def test_bluetooth_stays_off_until_the_kernel_is_ready(self):
        with open(os.path.join(TREE, "device.mk")) as mk:
            text = mk.read()
        block = text[text.index("ifeq ($(HY300_WITH_BLUETOOTH),true)"):]
        self.assertIn("android.hardware.bluetooth-service.default", block[:block.index("endif")])


if __name__ == "__main__":
    unittest.main()
