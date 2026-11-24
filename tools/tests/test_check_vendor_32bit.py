"""Testes do tools/check_vendor_32bit.py: no modo misto (64 + 32 bits), toda biblioteca do vendor
que um app carrega no próprio processo (same-process HAL: EGL/GLES do Mesa, dri, Vulkan, mapper)
e as dependências dela no vendor precisam existir em /vendor/lib64 e em /vendor/lib. Sem a de 32
bits um app armeabi-v7a (a Netflix de TV) fica sem GPU ou sem mapper.

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
"""
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import check_vendor_32bit  # noqa: E402

TREE = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT = os.environ.get("HY300_OUT", os.path.normpath(
    os.path.join(TREE, "..", "..", "..", "out", "target", "product", "hy300")))


class FakeVendor:
    def __init__(self, root):
        self.root = root
        self.needed = {}

    def add(self, rel, needed=()):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()
        self.needed[path] = list(needed)

    def read_needed(self, path):
        return self.needed.get(path, [])


class Vendor32Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hy300-v32-")
        self.addCleanup(shutil.rmtree, self.tmp)
        self.vendor = os.path.join(self.tmp, "vendor")
        self.fake = FakeVendor(self.vendor)

    def problems(self):
        return check_vendor_32bit.find_missing_32bit(self.vendor, self.fake.read_needed)

    def test_roots_are_egl_dri_vulkan_and_mapper(self):
        self.fake.add("lib64/egl/libEGL_mesa.so")
        self.fake.add("lib64/dri/panfrost_dri.so")
        self.fake.add("lib64/hw/vulkan.pastel.so")
        self.fake.add("lib64/hw/mapper.minigbm.so")
        self.fake.add("lib64/hw/android.hardware.audio.service.so")  # não é same-process
        roots = check_vendor_32bit.find_same_process_roots(self.vendor)
        self.assertEqual(sorted(roots), ["dri/panfrost_dri.so", "egl/libEGL_mesa.so",
                                         "hw/mapper.minigbm.so", "hw/vulkan.pastel.so"])

    def test_missing_32bit_root_is_reported(self):
        self.fake.add("lib64/egl/libEGL_mesa.so")
        self.assertEqual(self.problems(), ["egl/libEGL_mesa.so"])

    def test_vendor_dependency_needs_32bit_too(self):
        self.fake.add("lib64/hw/mapper.minigbm.so", ["libminigbm_gralloc.so", "liblog.so"])
        self.fake.add("lib64/libminigbm_gralloc.so")
        self.fake.add("lib/hw/mapper.minigbm.so")
        # liblog é do sistema (não está no vendor): não conta.
        self.assertEqual(self.problems(), ["libminigbm_gralloc.so"])

    def test_complete_vendor_passes(self):
        self.fake.add("lib64/egl/libGLESv2_mesa.so", ["libgallium_dri.so"])
        self.fake.add("lib64/libgallium_dri.so")
        self.fake.add("lib/egl/libGLESv2_mesa.so", ["libgallium_dri.so"])
        self.fake.add("lib/libgallium_dri.so")
        self.assertEqual(self.problems(), [])


@unittest.skipUnless(os.path.exists(os.path.join(OUT, "vendor", "lib")), "sem vendor 32 bits montado")
class BuiltVendorTest(unittest.TestCase):
    def test_every_same_process_library_has_32bit(self):
        vendor = os.path.join(OUT, "vendor")
        self.assertEqual(check_vendor_32bit.find_missing_32bit(
            vendor, check_vendor_32bit.read_needed_with_readelf), [])
        self.assertTrue(check_vendor_32bit.find_same_process_roots(vendor))


if __name__ == "__main__":
    unittest.main()
