"""Testes do keystone do SurfaceFlinger (patches/frameworks/native/0001): a matemática da
homografia (Keystone/KeystoneMath) é compilada e testada no host, tirada do próprio patch.

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import host_gtest  # noqa: E402

NATIVE = os.path.join(HERE, "..", "..", "patches", "frameworks", "native")
PATCH = os.path.join(NATIVE, "0001-surfaceflinger-keystone.patch")
# 0002: espelho com a homografia e composição pelo cliente (testes).
MIRROR_PATCH = os.path.join(NATIVE, "0002-keystone-espelho-e-composicao-pelo-cliente-testes.patch")
KEYSTONE = "services/surfaceflinger/Keystone"


def read_patch():
    with open(PATCH) as handle:
        return handle.read()


@unittest.skipUnless(host_gtest.find_compiler() and host_gtest.has_gtest(host_gtest.find_compiler()),
                     "sem compilador C++ ou gtest no host")
class KeystoneMathTest(unittest.TestCase):
    def test_gtest_of_the_keystone_math_passes(self):
        result = host_gtest.run([PATCH, MIRROR_PATCH], [f"{KEYSTONE}/*"],
                                [f"{KEYSTONE}/KeystoneMath.cpp",
                                 f"{KEYSTONE}/tests/KeystoneMathTest.cpp"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASSED", result.stdout)


class KeystonePatchContentTest(unittest.TestCase):
    def test_controller_and_math_are_built_into_surfaceflinger(self):
        patch = read_patch()
        self.assertIn('+        "Keystone/KeystoneController.cpp",', patch)
        self.assertIn('+        "Keystone/KeystoneMath.cpp",', patch)

    def test_render_engine_applies_the_transform_before_the_display_scale(self):
        patch = read_patch()
        self.assertIn("+        canvas->concat(getSkM44(display.keystoneTransform).asM33());", patch)

    def test_keystone_change_invalidates_the_client_composition_cache(self):
        self.assertIn("+            lhs.keystoneTransform == rhs.keystoneTransform &&", read_patch())

    def test_keystone_forces_every_layer_of_the_display_to_the_gpu(self):
        self.assertIn("+                refreshArgs.forcedClientCompositionLayerStacks.contains(outputLayerStack) ||",
                      read_patch())
        self.assertIn("+                keystoneForcesClientComposition;", read_patch())
        with open(MIRROR_PATCH) as handle:
            self.assertIn("keystoneForcesClientCompositionForAllLayers", handle.read())


if __name__ == "__main__":
    unittest.main()
