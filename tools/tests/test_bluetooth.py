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

    def test_bluetooth_is_behind_the_build_flag(self):
        with open(os.path.join(TREE, "device.mk")) as mk:
            text = mk.read()
        block = text[text.index("ifeq ($(HY300_WITH_BLUETOOTH),true)"):]
        self.assertIn("android.hardware.bluetooth-service.default", block[:block.index("endif")])

    def test_bluetooth_is_on_in_the_test_image(self):
        # Rodada 8: o kernel cae418b6c490 já tem o aic8800_btlpm e a UART; a imagem de teste sai
        # com Bluetooth. HY300_WITH_BLUETOOTH=false no ambiente desliga, se a pilha ficar
        # reiniciando no aparelho.
        with open(os.path.join(TREE, "device.mk")) as mk:
            text = mk.read()
        self.assertLess(text.index("HY300_WITH_BLUETOOTH ?= true"),
                        text.index("ifeq ($(HY300_WITH_BLUETOOTH),true)"))


class BluetoothBoot7Test(unittest.TestCase):
    """Boot 7 (rodada 10): Bluetooth parado em BLE_TURNING_ON, sem hci0 no kernel."""

    def test_hal_goes_straight_to_the_uart(self):
        # O initialize() do HAL padrão tenta primeiro o hci do kernel (NetBluetoothMgmt::openHci),
        # e o waitHciDev() repete o "Read Index List" para sempre enquanto não houver hci0. No modo
        # "uart" não há hci0: com vendor.ser.bt-uart definido, o HAL abre o tty direto.
        with open(os.path.join(TREE, "patches", "hardware", "interfaces",
                               "0003-bluetooth-uart-sem-esperar-o-hci.patch")) as patch:
            text = patch.read()
        self.assertIn('+    if (GetSystemProperty("vendor.ser.bt-uart").has_value()) {', text)
        self.assertIn("+        mFd = getFdFromDevPath();", text)

    def test_uart_setup_runs_again_after_the_aic8800_modules(self):
        # O aic8800_btlpm (rfkill "bluetooth") carrega com o Wi-Fi, depois da primeira passada do
        # hy300-bt-uart; sem a segunda, esse rfkill ficava bloqueado.
        with open(os.path.join(BT, "hy300-bt-uart.rc")) as rc:
            text = rc.read()
        self.assertIn("on property:vendor.hy300.wifi.iface=*\n    start vendor.hy300-bt-uart", text)


if __name__ == "__main__":
    unittest.main()
