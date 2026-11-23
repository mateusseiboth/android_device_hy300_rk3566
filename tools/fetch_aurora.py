#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2026 Mateus Seiboth
# SPDX-License-Identifier: Apache-2.0
#
"""Busca a Aurora Store (GPLv3, https://gitlab.com/AuroraOSS/AuroraStore) para pré-instalar.

O APK é o da F-Droid, versão e sha256 fixos aqui e conferidos contra o index-v2 do repositório e
contra o arquivo. Ele fica em prebuilt-apps/aurora/ (fora do git), com um Android.bp gerado; o
device.mk só inclui o AuroraStore se o APK existir. Fora do prebuilt/ de propósito: o kernel é
copiado para lá com rsync --delete.

Uso: tools/fetch_aurora.py                 baixa da F-Droid
     tools/fetch_aurora.py --from APK      usa uma cópia local (o hash é conferido igual)
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import urllib.request

PACKAGE = "com.aurora.store"
VERSION_CODE = 76  # 4.8.4
APK_SHA256 = "fd9c75d90d0f4a7c132b9b4a5a2cf1992a45e03b8d8ff988b7dcfbc0db2c4d11"
REPO = "https://f-droid.org/repo"
INDEX_URL = REPO + "/index-v2.json"
DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prebuilt-apps", "aurora")
APK_NAME = "AuroraStore.apk"
ANDROID_BP = """// Gerado por tools/fetch_aurora.py. Não editar; prebuilt-apps/ fica fora do git.
// Aurora Store {version} (GPLv3, fonte em https://gitlab.com/AuroraOSS/AuroraStore),
// APK da F-Droid, sha256 {sha256}.
android_app_import {{
    name: "AuroraStore",
    apk: "{apk}",
    presigned: true,
    // targetSdk >= 30: assinado com v2; o build não pode realinhar o APK.
    preprocessed: true,
    product_specific: true,
    dex_preopt: {{
        enabled: false,
    }},
}}
"""


class FetchError(Exception):
    pass


def find_apk_entry(index, package, version_code):
    versions = index.get("packages", {}).get(package, {}).get("versions")
    if not versions:
        raise FetchError(f"{package} não está no índice")
    for version in versions.values():
        if version["manifest"]["versionCode"] == version_code:
            return version["file"]
    raise FetchError(f"{package} versionCode {version_code} não está no índice")


def require_pinned_hash(entry, expected=APK_SHA256):
    if entry["sha256"] != expected:
        raise FetchError(f"o índice traz {entry['sha256']} para {entry['name']}, "
                         f"o fixado é {expected}")


def hash_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install_apk(src, dest, expected):
    actual = hash_file(src)
    if actual != expected:
        raise FetchError(f"sha256 de {src} é {actual}, esperado {expected}")
    os.makedirs(dest, exist_ok=True)
    shutil.copyfile(src, os.path.join(dest, APK_NAME))
    with open(os.path.join(dest, "Android.bp"), "w") as f:
        f.write(ANDROID_BP.format(version=VERSION_CODE, sha256=expected, apk=APK_NAME))


def download(url, path):
    with urllib.request.urlopen(url, timeout=120) as response, open(path, "wb") as out:
        shutil.copyfileobj(response, out)


def fetch_from_fdroid(workdir):
    index_path = os.path.join(workdir, "index-v2.json")
    download(INDEX_URL, index_path)
    with open(index_path) as f:
        entry = find_apk_entry(json.load(f), PACKAGE, VERSION_CODE)
    require_pinned_hash(entry)
    apk_path = os.path.join(workdir, os.path.basename(entry["name"]))
    download(REPO + entry["name"], apk_path)
    return apk_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from", dest="local", help="cópia local do APK")
    parser.add_argument("--dest", default=DEST)
    parser.add_argument("--sha256", default=APK_SHA256, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        with tempfile.TemporaryDirectory(prefix="hy300-aurora-") as workdir:
            src = args.local or fetch_from_fdroid(workdir)
            install_apk(src, args.dest, args.sha256)
    except (FetchError, OSError) as error:
        print(f"erro: {error}", file=sys.stderr)
        return 1
    print(f"ok: {os.path.join(args.dest, APK_NAME)} ({args.sha256})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
