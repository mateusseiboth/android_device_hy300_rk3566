"""Testes do tools/fetch_aurora.py: Aurora Store (GPLv3) pré-instalada, APK fora do git.

O APK vem da F-Droid; a versão e o sha256 ficam fixos no script e são conferidos contra o
index-v2 e contra o arquivo baixado (ou a cópia local passada com --from).

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
"""
import hashlib
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

import fetch_aurora  # noqa: E402

APK_BYTES = b"PK\x03\x04 apk de teste"
APK_SHA = hashlib.sha256(APK_BYTES).hexdigest()


def make_index(sha=APK_SHA, version_code=76):
    return {"repo": {"address": "https://f-droid.org/repo"},
            "packages": {"com.aurora.store": {"versions": {
                sha: {"manifest": {"versionCode": version_code, "versionName": "4.8.4"},
                      "file": {"name": f"/com.aurora.store_{version_code}.apk", "sha256": sha,
                               "size": len(APK_BYTES)}}}}}}


class FindEntryTest(unittest.TestCase):
    def test_finds_the_pinned_version(self):
        entry = fetch_aurora.find_apk_entry(make_index(), "com.aurora.store", 76)
        self.assertEqual(entry["sha256"], APK_SHA)
        self.assertEqual(entry["name"], "/com.aurora.store_76.apk")

    def test_missing_version_is_an_error(self):
        with self.assertRaises(fetch_aurora.FetchError):
            fetch_aurora.find_apk_entry(make_index(version_code=75), "com.aurora.store", 76)

    def test_missing_package_is_an_error(self):
        with self.assertRaises(fetch_aurora.FetchError):
            fetch_aurora.find_apk_entry(make_index(), "com.example", 76)


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hy300-aurora-")
        self.addCleanup(shutil.rmtree, self.tmp)
        self.src = os.path.join(self.tmp, "baixado.apk")
        with open(self.src, "wb") as f:
            f.write(APK_BYTES)
        self.dest = os.path.join(self.tmp, "prebuilt", "aurora")

    def test_installs_apk_and_android_bp(self):
        fetch_aurora.install_apk(self.src, self.dest, APK_SHA)
        with open(os.path.join(self.dest, "AuroraStore.apk"), "rb") as f:
            self.assertEqual(f.read(), APK_BYTES)
        bp = open(os.path.join(self.dest, "Android.bp")).read()
        self.assertIn('name: "AuroraStore"', bp)
        self.assertIn('apk: "AuroraStore.apk"', bp)
        self.assertIn("presigned: true", bp)
        # targetSdk >= 30: assinatura v2, o build não pode realinhar o APK.
        self.assertIn("preprocessed: true", bp)

    def test_refuses_wrong_hash_and_writes_nothing(self):
        with self.assertRaises(fetch_aurora.FetchError):
            fetch_aurora.install_apk(self.src, self.dest, "0" * 64)
        self.assertFalse(os.path.exists(os.path.join(self.dest, "AuroraStore.apk")))
        self.assertFalse(os.path.exists(os.path.join(self.dest, "Android.bp")))

    def test_pinned_hash_is_the_one_in_the_index(self):
        index = make_index(sha=fetch_aurora.APK_SHA256, version_code=fetch_aurora.VERSION_CODE)
        entry = fetch_aurora.find_apk_entry(index, fetch_aurora.PACKAGE,
                                            fetch_aurora.VERSION_CODE)
        fetch_aurora.require_pinned_hash(entry)

    def test_index_with_other_hash_is_refused(self):
        entry = {"name": "/x.apk", "sha256": "f" * 64}
        with self.assertRaises(fetch_aurora.FetchError):
            fetch_aurora.require_pinned_hash(entry)


class MainTest(unittest.TestCase):
    def test_main_with_local_copy(self):
        tmp = tempfile.mkdtemp(prefix="hy300-aurora-")
        self.addCleanup(shutil.rmtree, tmp)
        src = os.path.join(tmp, "a.apk")
        with open(src, "wb") as f:
            f.write(APK_BYTES)
        dest = os.path.join(tmp, "out")
        rc = fetch_aurora.main(["--from", src, "--dest", dest, "--sha256", APK_SHA])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(os.path.join(dest, "AuroraStore.apk")))


if __name__ == "__main__":
    unittest.main()
