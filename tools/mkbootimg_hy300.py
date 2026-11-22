#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2026 Mateus Seiboth
# SPDX-License-Identifier: Apache-2.0
#
"""mkbootimg com o ID que o U-Boot de fábrica do HY300 confere.

O U-Boot Rockchip (2017.09 #txcz) recusa um boot.img v1/v2 cujo campo `id` (offset 576)
não seja o SHA-1 de cada seção seguida do seu tamanho em 32 bits little-endian:
kernel, ramdisk, second, recovery_dtbo e (v2) dtb. O mkbootimg do LineageOS soma 4 bytes
a mais no hash (patch do `--dt`), então o ID sai errado e o U-Boot não boota.

Este wrapper roda o mkbootimg verdadeiro sem mudar nada e depois regrava o ID da imagem
gerada. Vale para boot.img e recovery.img (BOARD_CUSTOM_MKBOOTIMG). Imagens v0, v3, v4 e
vendor_boot passam sem mudança.
"""
import hashlib
import os
import struct
import subprocess
import sys

BOOT_MAGIC = b"ANDROID!"
OFF_KERNEL_SIZE = 8
OFF_RAMDISK_SIZE = 16
OFF_SECOND_SIZE = 24
OFF_PAGE_SIZE = 36
OFF_HEADER_VERSION = 40
OFF_ID = 576
ID_FIELD_SIZE = 32
OFF_RECOVERY_DTBO_SIZE = 1632
OFF_HEADER_SIZE = 1644
OFF_DTB_SIZE = 1648
HEADER_V2_SIZE = 1660
SIZE_FIELDS_BY_VERSION = {
    1: (OFF_KERNEL_SIZE, OFF_RAMDISK_SIZE, OFF_SECOND_SIZE, OFF_RECOVERY_DTBO_SIZE),
    2: (OFF_KERNEL_SIZE, OFF_RAMDISK_SIZE, OFF_SECOND_SIZE, OFF_RECOVERY_DTBO_SIZE, OFF_DTB_SIZE),
}
OUTPUT_FLAGS = ("--output", "-o")
REAL_MKBOOTIMG = os.path.join("system", "tools", "mkbootimg", "mkbootimg.py")


def read_u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def align(size, page):
    return (size + page - 1) // page * page


def is_hashed_image(image):
    return (
        len(image) >= HEADER_V2_SIZE
        and image.startswith(BOOT_MAGIC)
        and read_u32(image, OFF_HEADER_VERSION) in SIZE_FIELDS_BY_VERSION
    )


def compute_image_id(image):
    if not is_hashed_image(image):
        return None
    page = read_u32(image, OFF_PAGE_SIZE)
    sizes = [read_u32(image, off) for off in SIZE_FIELDS_BY_VERSION[read_u32(image, OFF_HEADER_VERSION)]]
    sha = hashlib.sha1()
    offset = align(read_u32(image, OFF_HEADER_SIZE), page)
    for size in sizes:
        sha.update(image[offset:offset + size])
        sha.update(struct.pack("<I", size))
        offset += align(size, page)
    return sha.digest()


def fix_image_id(path):
    with open(path, "rb") as handle:
        image = handle.read()
    image_id = compute_image_id(image)
    if image_id is None or image[OFF_ID:OFF_ID + len(image_id)] == image_id:
        return False
    with open(path, "r+b") as handle:
        handle.seek(OFF_ID)
        handle.write(image_id.ljust(ID_FIELD_SIZE, b"\0"))
    return True


def find_output(argv):
    for index, arg in enumerate(argv):
        if arg in OUTPUT_FLAGS and index + 1 < len(argv):
            return argv[index + 1]
        if arg.startswith("--output="):
            return arg.split("=", 1)[1]
    return None


def find_real_mkbootimg():
    roots = [os.environ.get("ANDROID_BUILD_TOP"), os.getcwd()]
    candidates = [os.path.join(root, REAL_MKBOOTIMG) for root in roots if root]
    found = next((path for path in candidates if os.path.isfile(path)), None)
    if not found:
        sys.exit(f"mkbootimg_hy300: {REAL_MKBOOTIMG} não encontrado")
    return found


def build_command(tool, argv):
    return [tool, *argv] if not tool.endswith(".py") else [sys.executable, tool, *argv]


def run_command(command):
    return subprocess.call(command)


def main(argv=None, run=run_command, tool=None):
    argv = sys.argv[1:] if argv is None else argv
    code = run(build_command(tool or find_real_mkbootimg(), argv))
    output = find_output(argv)
    if code != 0 or not output:
        return code
    if fix_image_id(output):
        print(f"mkbootimg_hy300: ID de {os.path.basename(output)} recalculado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
