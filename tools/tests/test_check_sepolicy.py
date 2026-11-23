"""Testes do tools/check_sepolicy.py: a troca dos arquivos de política da árvore principal pelos
desta no comando m4 do build e, com um checkout compilado ao lado, a conferência de verdade
(neverallows do build e contextos).

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
(LINEAGE_TOP aponta para outro checkout; sem build anterior, a conferência real é pulada)
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import check_sepolicy  # noqa: E402

TOP = os.environ.get("LINEAGE_TOP", os.path.expanduser("~/android/lineage"))

SCRIPT = ("echo > x/newline && prebuilts/build-tools/linux-x86/bin/m4 --fatal-warnings "
          "-D target_build_variant=user -s system/sepolicy/public/te_macros x/newline "
          "system/sepolicy/public/file.te device/txcz/hy300/sepolicy/vendor/file.te "
          "system/sepolicy/vendor/hal.te system/sepolicy/private/genfs_contexts "
          "device/txcz/hy300/sepolicy/vendor/genfs_contexts system/sepolicy/private/port_contexts"
          " >  out.conf && rm -f x/newline")


class MergeTest(unittest.TestCase):
    def test_extracts_the_m4_arguments_without_the_redirection(self):
        args = check_sepolicy.extract_m4_args(SCRIPT)
        self.assertEqual(args[:2], ["--fatal-warnings", "-D"])
        self.assertEqual(args[-1], "system/sepolicy/private/port_contexts")

    def test_replaces_the_main_tree_files_by_category(self):
        args = check_sepolicy.extract_m4_args(SCRIPT)
        merged = check_sepolicy.merge_files(args, ["/t/a.te", "/t/genfs_contexts"])
        self.assertNotIn("device/txcz/hy300/sepolicy/vendor/file.te", merged)
        self.assertEqual(merged[merged.index("system/sepolicy/vendor/hal.te") + 1], "/t/a.te")
        self.assertEqual(merged[merged.index("system/sepolicy/private/genfs_contexts") + 1],
                         "/t/genfs_contexts")

    def test_policy_files_cover_both_partitions(self):
        names = [os.path.relpath(p, check_sepolicy.TREE) for p in check_sepolicy.policy_files()]
        self.assertIn("sepolicy/vendor/genfs_contexts", names)
        self.assertIn("sepolicy/system_ext/private/hy300_settings_app.te", names)
        self.assertIn("sepolicy/system_ext/public/hy300_settings_app.te", names)


@unittest.skipUnless(os.path.isfile(os.path.join(TOP, "out/host/linux-x86/bin/checkpolicy")),
                     "sem build anterior do LineageOS ao lado")
class RealPolicyTest(unittest.TestCase):
    def test_policy_passes_the_neverallows_and_contexts(self):
        self.assertEqual(check_sepolicy.check(os.path.abspath(TOP)), [])


if __name__ == "__main__":
    unittest.main()
