"""Testes do vídeo 10 bits no Codec2 da Rockchip com o minigbm (patches/hardware/rockchip/codec2/
0005): as regras (stride da RGA em pixels, P010 nunca anunciado com o gralloc genérico) são
compiladas e testadas no host, tiradas do próprio patch, no padrão C++17 do projeto.

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import host_gtest  # noqa: E402

PATCH = os.path.join(HERE, "..", "..", "patches", "hardware", "rockchip", "codec2",
                     "0005-decoder-10-bits-com-gralloc-generico.patch")
OSAL = "component/osal"


def read_patch():
    with open(PATCH) as handle:
        return handle.read()


@unittest.skipUnless(host_gtest.find_compiler() and host_gtest.has_gtest(host_gtest.find_compiler()),
                     "sem compilador C++ ou gtest no host")
class GenericGralloc10BitGtest(unittest.TestCase):
    def test_gtest_of_the_10bit_rules_passes(self):
        with host_gtest.extracted(PATCH, [f"{OSAL}/include/*", f"{OSAL}/tests/*"]) as work:
            result = host_gtest.run_sources(
                [os.path.join(work, OSAL, "tests", "C2RKGenericGrallocTest.cpp")],
                [f"-I{os.path.join(work, OSAL, 'include')}"], std="gnu++17")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASSED", result.stdout)


class Decoder10BitPatchTest(unittest.TestCase):
    def test_decoder_uses_the_rules(self):
        patch = read_patch()
        self.assertIn("+        if (c2_rk_generic::isP010Usable(kGenericGralloc, "
                      "C2RKMediaUtils::isP010Allowed())) {", patch)
        self.assertIn("+            const int32_t srcWStride = c2_rk_generic::toRgaWidthStride(",
                      patch)


if __name__ == "__main__":
    unittest.main()
