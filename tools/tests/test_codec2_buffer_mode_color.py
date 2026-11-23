"""Testes da cor no buffer mode do decoder do Codec2 da Rockchip com o minigbm (patches/hardware/
rockchip/codec2/0007).

Rodada 14: VP9 1920x1080 (hor 2496, ver 1080) e 854x480 saíam roxos com faixas verdes. No ramo
mBufferMode a cópia (RGA ou CPU) usava dstVStride = C2_ALIGN(height, 2), mas o minigbm aloca o NV12
com a altura alinhada e o plano UV começa em stride * 1088, não em stride * 1080: o UV era escrito
8 linhas antes. A vstride do destino passa a vir do layout real do bloco (deslocamento do plano U
sobre o Y, dividido pelo rowInc). As regras ficam no C2RKGenericGralloc.h, testadas no host com
gtest tirado dos patches 0005 e 0007.

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import host_gtest  # noqa: E402

PATCHES = os.path.join(HERE, "..", "..", "patches", "hardware", "rockchip", "codec2")
P0005 = os.path.join(PATCHES, "0005-decoder-10-bits-com-gralloc-generico.patch")
P0007 = os.path.join(PATCHES, "0007-buffer-mode-vstride-do-layout-real.patch")
OSAL = "component/osal"


@unittest.skipUnless(host_gtest.find_compiler() and host_gtest.has_gtest(host_gtest.find_compiler()),
                     "sem compilador C++ ou gtest no host")
class BufferModeColorGtest(unittest.TestCase):
    def test_gtest_of_the_vstride_rule_passes(self):
        with host_gtest.extracted([P0005, P0007], [f"{OSAL}/include/*", f"{OSAL}/tests/*"]) as work:
            result = host_gtest.run_sources(
                [os.path.join(work, OSAL, "tests", "C2RKGenericGrallocTest.cpp")],
                [f"-I{os.path.join(work, OSAL, 'include')}"], std="gnu++17")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("BufferModeVStrideTest", result.stdout)


class BufferModeColorPatchTest(unittest.TestCase):
    def test_decoder_takes_the_vstride_from_the_block_layout(self):
        with open(P0007) as patch:
            text = patch.read()
        self.assertIn("c2_rk_generic::vstrideFromUvOffset(", text)
        self.assertIn("dstView.data()[C2PlanarLayout::PLANE_U]", text)


if __name__ == "__main__":
    unittest.main()
