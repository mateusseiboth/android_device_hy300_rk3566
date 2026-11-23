"""Testes do tools/apply_patches.py (patches da árvore aplicados nos projetos de fora).

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import apply_patches  # noqa: E402

PATCH = """\
diff --git a/hello.txt b/hello.txt
--- a/hello.txt
+++ b/hello.txt
@@ -1 +1 @@
-ola
+ola hy300
"""


def run_git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class ApplyPatchesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.top = os.path.join(self.tmp.name, "top")
        self.project = os.path.join(self.top, "hardware", "rockchip", "codec2")
        os.makedirs(self.project)
        with open(os.path.join(self.project, "hello.txt"), "w") as handle:
            handle.write("ola\n")
        run_git(self.project, "init", "-q")
        run_git(self.project, "add", ".")
        run_git(self.project, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
        self.patches = os.path.join(self.tmp.name, "patches")
        patch_dir = os.path.join(self.patches, "hardware", "rockchip", "codec2")
        os.makedirs(patch_dir)
        with open(os.path.join(patch_dir, "0001-hello.patch"), "w") as handle:
            handle.write(PATCH)

    def read_hello(self):
        with open(os.path.join(self.project, "hello.txt")) as handle:
            return handle.read()

    def test_find_patches_maps_project_path_to_sorted_patches(self):
        found = apply_patches.find_patches(self.patches)
        self.assertEqual(list(found), ["hardware/rockchip/codec2"])
        self.assertEqual([os.path.basename(p) for p in found["hardware/rockchip/codec2"]],
                         ["0001-hello.patch"])

    def test_apply_all_applies_patch(self):
        results = apply_patches.apply_all(self.top, self.patches)
        self.assertEqual(self.read_hello(), "ola hy300\n")
        self.assertEqual(results, [("hardware/rockchip/codec2", "0001-hello.patch", "aplicado")])

    def test_apply_all_is_idempotent(self):
        apply_patches.apply_all(self.top, self.patches)
        results = apply_patches.apply_all(self.top, self.patches)
        self.assertEqual(self.read_hello(), "ola hy300\n")
        self.assertEqual(results[0][2], "já aplicado")

    def test_apply_all_fails_when_patch_does_not_fit(self):
        with open(os.path.join(self.project, "hello.txt"), "w") as handle:
            handle.write("outra coisa\n")
        with self.assertRaisesRegex(RuntimeError, "0001-hello.patch"):
            apply_patches.apply_all(self.top, self.patches)

    def test_apply_all_fails_when_project_is_missing(self):
        os.rename(self.project, self.project + ".x")
        with self.assertRaisesRegex(RuntimeError, "hardware/rockchip/codec2"):
            apply_patches.apply_all(self.top, self.patches)


class TreePatchesTest(unittest.TestCase):
    """Os patches da árvore têm de ser diffs de verdade: um deles chegou a ser gravado com o resumo
    que um wrapper do git imprime no lugar do diff, e o apply_patches.py só acusou no checkout."""

    def test_every_patch_of_the_tree_is_a_git_diff(self):
        found = apply_patches.find_patches(apply_patches.PATCHES_DIR)
        self.assertTrue(found)
        for project, patches in found.items():
            for patch in patches:
                with open(patch) as f:
                    text = f.read()
                self.assertIn("\ndiff --git a/", text, patch)
                self.assertNotIn("--- Changes ---", text, patch)


if __name__ == "__main__":
    unittest.main()
