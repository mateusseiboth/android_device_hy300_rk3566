"""Testes da entrada do encoder do Codec2 da Rockchip com o minigbm (patches/hardware/rockchip/
codec2/0006).

Boot 8 (rodada 11): scrcpy com c2.rk.avc.encoder saía preto. O buffer RGBA da Surface de entrada
(display virtual) vem do minigbm sem uso de CPU, e o C2RKMpiEnc fazia lock pela CPU só para saber
o layout: "Gralloc5: lock(...) failed: 3", "C2AllocatorGralloc: failed transaction:
lock(RGBA_8888)", "C2RKMpiEnc: failed to mapInputBuffer with err 14". Com o gralloc genérico o
encoder não faz lock: o layout vem do formato HAL do handle e o MPP/RGA leem o dma-buf pelo fd.

As regras ficam num cabeçalho sem dependência do Android, testado no host com gtest tirado do
próprio patch.

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import host_gtest  # noqa: E402

PATCH = os.path.join(HERE, "..", "..", "patches", "hardware", "rockchip", "codec2",
                     "0006-encoder-sem-lock-da-cpu-na-entrada.patch")
OSAL = "component/osal"


def read_patch():
    with open(PATCH) as handle:
        return handle.read()


@unittest.skipUnless(host_gtest.find_compiler() and host_gtest.has_gtest(host_gtest.find_compiler()),
                     "sem compilador C++ ou gtest no host")
class EncoderInputGtest(unittest.TestCase):
    def test_gtest_of_the_input_rules_passes(self):
        with host_gtest.extracted(PATCH, [f"{OSAL}/include/*", f"{OSAL}/tests/*"]) as work:
            result = host_gtest.run_sources(
                [os.path.join(work, OSAL, "tests", "C2RKGenericInputTest.cpp")],
                [f"-I{os.path.join(work, OSAL, 'include')}"], std="gnu++17")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASSED", result.stdout)


class EncoderInputPatchTest(unittest.TestCase):
    def test_process_does_not_lock_the_input_with_generic_gralloc(self):
        patch = read_patch()
        self.assertIn("+    if (!work->input.buffers.empty() &&\n"
                      "+            c2_rk_generic::needsCpuMapping(kGenericGralloc)) {", patch)

    def test_layout_comes_from_the_hal_format(self):
        patch = read_patch()
        self.assertIn("c2_rk_generic::inputLayoutFromHalFormat(format)", patch)


if __name__ == "__main__":
    unittest.main()
