"""Testes da captura da entrada HDMI (hdmiin/): a lógica (V4L2 multiplanar, só o quadro mais
novo, RGA para a janela, recomeço quando a fonte muda) roda no host com um V4L2 falso; e a
interface AIDL congelada tem de bater com o hash, senão o build recusa.

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
"""
import glob
import hashlib
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import host_gtest  # noqa: E402

HDMIIN = os.path.join(HERE, "..", "..", "hdmiin")
# O Soong procura o aidl_api ao lado do Android.bp do aidl_interface (não dentro de aidl/).
FROZEN = os.path.join(HDMIIN, "aidl_api", "vendor.hy300.hdmiin", "1")


@unittest.skipUnless(host_gtest.find_compiler() and host_gtest.has_gtest(host_gtest.find_compiler()),
                     "sem compilador C++ ou gtest no host")
class HdmiCaptureGtest(unittest.TestCase):
    def test_gtest_of_the_capture_passes(self):
        sources = sorted(glob.glob(os.path.join(HDMIIN, "core", "*.cpp")))
        sources.append(os.path.join(HDMIIN, "tests", "HdmiCaptureTest.cpp"))
        result = host_gtest.run_sources(sources, [f"-I{os.path.join(HDMIIN, 'core')}",
                                                  f"-I{os.path.join(HDMIIN, 'tests')}"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASSED", result.stdout)


class FrozenAidlTest(unittest.TestCase):
    def test_hash_matches_the_frozen_files(self):
        """Mesma conta do aidl_interface: sha1 de cada .aidl em ordem e 'latest-version'."""
        lines = []
        files = sorted(os.path.relpath(p, FROZEN)
                       for p in glob.glob(os.path.join(FROZEN, "**", "*.aidl"), recursive=True))
        for relative in files:
            with open(os.path.join(FROZEN, relative), "rb") as handle:
                lines.append(f"{hashlib.sha1(handle.read()).hexdigest()}  ./{relative}\n")
        lines.append("latest-version\n")
        expected = hashlib.sha1("".join(lines).encode()).hexdigest()
        with open(os.path.join(FROZEN, ".hash")) as handle:
            self.assertEqual(handle.read().strip(), expected)

    def test_rc_declares_the_interface(self):
        with open(os.path.join(HDMIIN, "hal", "vendor.hy300.hdmiin-service.rc")) as rc:
            self.assertIn("interface aidl vendor.hy300.hdmiin.IHdmiCapture/default", rc.read())


class ServiceBuildTest(unittest.TestCase):
    """O que o Soong pegou no build da rodada 9."""

    def test_service_has_the_nativebase_headers(self):
        # vndk/window.h inclui nativebase/nativebase.h, que não vem com a libnativewindow.
        with open(os.path.join(HDMIIN, "Android.bp")) as bp:
            text = bp.read()
        service = text[text.index('name: "vendor.hy300.hdmiin-service"'):]
        block = service[:service.index("\n}")]
        # nativebase.h inclui system/graphics-base.h e cutils/native_handle.h.
        for header_lib in ("libnativebase_headers", "libsystem_headers", "libcutils_headers"):
            self.assertIn(f'"{header_lib}"', block)

    def test_service_links_the_tvinput_core(self):
        # static_libs de uma biblioteca estática não entram no link de quem a usa: o
        # libhy300tvinput_probe chama buildHdmiInConfig e findV4l2Node do núcleo.
        with open(os.path.join(HDMIIN, "Android.bp")) as bp:
            text = bp.read()
        service = text[text.index('name: "vendor.hy300.hdmiin-service"'):]
        block = service[:service.index("\n}")]
        self.assertLess(block.index('"libhy300tvinput_probe"'), block.index('"libhy300tvinput_core"'))

    def test_ioctl_request_matches_bionic(self):
        # No bionic o ioctl recebe int; unsigned long direto quebra no -Wshorten-64-to-32.
        with open(os.path.join(HDMIIN, "hal", "V4l2FdDevice.cpp")) as source:
            self.assertIn("ioctl(fd_.get(), static_cast<int>(request), arg)", source.read())


if __name__ == "__main__":
    unittest.main()
