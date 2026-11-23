"""Testes do BCSH no drm_hwcomposer (patches/external/drm_hwcomposer/0001): a leitura das props
persist.vendor.{brightness,contrast,saturation,hue}.main é compilada e testada no host, tirada
do próprio patch, com o mesmo padrão de C++ do projeto (gnu++17).

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import host_gtest  # noqa: E402

PATCH = os.path.join(HERE, "..", "..", "patches", "external", "drm_hwcomposer",
                     "0001-bcsh-do-vop2-pelas-props-da-rockchip.patch")


def read_patch():
    with open(PATCH) as handle:
        return handle.read()


@unittest.skipUnless(host_gtest.find_compiler() and host_gtest.has_gtest(host_gtest.find_compiler()),
                     "sem compilador C++ ou gtest no host")
class BcshGtest(unittest.TestCase):
    def test_gtest_of_the_bcsh_props_passes(self):
        result = host_gtest.run(PATCH, ["utils/Bcsh*"], ["utils/Bcsh.cpp", "utils/BcshTest.cpp"],
                                std="gnu++17")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASSED", result.stdout)


class BcshPatchContentTest(unittest.TestCase):
    def test_connector_reads_the_four_bsp_properties(self):
        patch = read_patch()
        for name in ("brightness", "contrast", "saturation", "hue"):
            self.assertIn(f'+  GetOptionalConnectorProperty("{name}", &{name}_property_);', patch)

    def test_every_commit_carries_the_bcsh(self):
        patch = read_patch()
        self.assertIn("+  a_args.bcsh = GetBcsh();", patch)
        self.assertIn("+  args.bcsh = GetBcsh();", patch)
        self.assertIn("+  if (!SetBcshIfNeeded(args, *atomic_request)) {", patch)

    def test_bcsh_test_is_in_the_unittests_of_the_project(self):
        self.assertIn('+        "utils/BcshTest.cpp",', read_patch())


if __name__ == "__main__":
    unittest.main()
