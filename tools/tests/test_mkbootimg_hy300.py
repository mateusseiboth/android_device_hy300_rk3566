"""Testes do tools/mkbootimg_hy300.py (ID do boot.img v2 no formato que o U-Boot Rockchip confere).

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
"""
import hashlib
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import mkbootimg_hy300  # noqa: E402

PAGE = 2048
FACTORY_BOOT = os.path.expanduser("~/hy300-backup/boot.img")


def pad(data):
    return data + b"\0" * (-len(data) % PAGE)


def build_v2_image(kernel, ramdisk, second, recovery_dtbo, dtb, header_version=2, image_id=b""):
    header = bytearray(1660)
    header[0:8] = b"ANDROID!"
    struct.pack_into("<I", header, 8, len(kernel))
    struct.pack_into("<I", header, 16, len(ramdisk))
    struct.pack_into("<I", header, 24, len(second))
    struct.pack_into("<I", header, 36, PAGE)
    struct.pack_into("<I", header, 40, header_version)
    header[576:576 + len(image_id)] = image_id
    struct.pack_into("<I", header, 1632, len(recovery_dtbo))
    struct.pack_into("<I", header, 1644, 1660)
    struct.pack_into("<I", header, 1648, len(dtb))
    sections = [kernel, ramdisk, second, recovery_dtbo, dtb]
    return pad(bytes(header)) + b"".join(pad(s) for s in sections)


def expected_id(sections):
    sha = hashlib.sha1()
    for section in sections:
        sha.update(section)
        sha.update(struct.pack("<I", len(section)))
    return sha.digest()


SECTIONS = [b"K" * 5000, b"R" * 300, b"S" * 4096, b"", b"D" * 77]


class ComputeIdTest(unittest.TestCase):
    def test_compute_image_id_hashes_each_section_and_its_size(self):
        image = build_v2_image(*SECTIONS)
        self.assertEqual(mkbootimg_hy300.compute_image_id(image), expected_id(SECTIONS))

    def test_compute_image_id_ignores_non_android_images(self):
        self.assertIsNone(mkbootimg_hy300.compute_image_id(b"VNDRBOOT" + b"\0" * 4096))

    def test_compute_image_id_ignores_header_v3(self):
        image = build_v2_image(*SECTIONS, header_version=3)
        self.assertIsNone(mkbootimg_hy300.compute_image_id(image))

    @unittest.skipUnless(os.path.exists(FACTORY_BOOT), "boot.img de fábrica fora deste host")
    def test_compute_image_id_matches_factory_boot(self):
        with open(FACTORY_BOOT, "rb") as handle:
            image = handle.read()
        self.assertEqual(mkbootimg_hy300.compute_image_id(image), image[576:596])


class FixIdTest(unittest.TestCase):
    def write_image(self, data):
        handle = tempfile.NamedTemporaryFile(suffix=".img", delete=False)
        handle.write(data)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def test_fix_image_id_rewrites_wrong_id_and_pads_field(self):
        path = self.write_image(build_v2_image(*SECTIONS, image_id=b"\x11" * 32))
        self.assertTrue(mkbootimg_hy300.fix_image_id(path))
        with open(path, "rb") as handle:
            data = handle.read()
        self.assertEqual(data[576:596], expected_id(SECTIONS))
        self.assertEqual(data[596:608], b"\0" * 12)

    def test_fix_image_id_keeps_correct_image_untouched(self):
        original = build_v2_image(*SECTIONS, image_id=expected_id(SECTIONS))
        path = self.write_image(original)
        self.assertFalse(mkbootimg_hy300.fix_image_id(path))
        with open(path, "rb") as handle:
            self.assertEqual(handle.read(), original)

    def test_find_output_reads_output_argument(self):
        argv = ["--kernel", "k", "--output", "out/boot.img", "--header_version", "2"]
        self.assertEqual(mkbootimg_hy300.find_output(argv), "out/boot.img")
        self.assertEqual(mkbootimg_hy300.find_output(["-o", "x.img"]), "x.img")
        self.assertEqual(mkbootimg_hy300.find_output(["--output=y.img"]), "y.img")
        self.assertIsNone(mkbootimg_hy300.find_output(["--vendor_boot", "v.img"]))


class MainTest(unittest.TestCase):
    def test_main_runs_real_tool_then_fixes_id(self):
        out = tempfile.NamedTemporaryFile(suffix=".img", delete=False)
        out.close()
        self.addCleanup(os.unlink, out.name)
        image = build_v2_image(*SECTIONS, image_id=b"\x22" * 32)
        calls = []

        def fake_run(command):
            calls.append(command)
            with open(out.name, "wb") as handle:
                handle.write(image)
            return 0

        code = mkbootimg_hy300.main(["--kernel", "k", "--output", out.name], run=fake_run, tool="mkbootimg")
        self.assertEqual(code, 0)
        self.assertEqual(calls, [["mkbootimg", "--kernel", "k", "--output", out.name]])
        with open(out.name, "rb") as handle:
            self.assertEqual(handle.read()[576:596], expected_id(SECTIONS))

    def test_main_propagates_tool_failure_without_touching_output(self):
        code = mkbootimg_hy300.main(["--output", "/nao/existe.img"], run=lambda command: 3, tool="mkbootimg")
        self.assertEqual(code, 3)


if __name__ == "__main__":
    unittest.main()
