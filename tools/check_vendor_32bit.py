#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2026 Mateus Seiboth
# SPDX-License-Identifier: Apache-2.0
#
"""Confere, no vendor montado, que toda biblioteca same-process (carregada pelo app no próprio
processo: EGL/GLES e dri do Mesa, Vulkan, mapper) e as dependências dela no vendor existem em
lib64/ e em lib/. No modo misto (64 + 32 bits) um app armeabi-v7a sem a versão de 32 bits fica
sem GPU ou sem mapper. HALs em processo próprio (Codec2, áudio, Widevine) ficam só em 64 bits.

Uso: tools/check_vendor_32bit.py [out/target/product/hy300]
"""
import glob
import os
import re
import subprocess
import sys

ROOT_PATTERNS = ("egl/*.so", "dri/*.so", "hw/vulkan.*.so", "hw/mapper.*.so",
                 "hw/android.hardware.graphics.mapper@*.so")
NEEDED = re.compile(r"\(NEEDED\).*\[(.+)\]")


def find_same_process_roots(vendor):
    lib64 = os.path.join(vendor, "lib64")
    roots = set()
    for pattern in ROOT_PATTERNS:
        roots |= {os.path.relpath(p, lib64) for p in glob.glob(os.path.join(lib64, pattern))}
    return sorted(roots)


def read_needed_with_readelf(path):
    out = subprocess.run(["readelf", "-d", path], capture_output=True, text=True).stdout
    return NEEDED.findall(out)


def find_vendor_closure(vendor, roots, read_needed):
    lib64 = os.path.join(vendor, "lib64")
    seen, pending = set(), list(roots)
    while pending:
        rel = pending.pop()
        if rel in seen:
            continue
        seen.add(rel)
        for name in read_needed(os.path.join(lib64, rel)):
            # Só as do vendor: as do sistema (LLNDK/VNDK) vêm com a segunda arquitetura do system.
            if os.path.exists(os.path.join(lib64, name)):
                pending.append(name)
    return sorted(seen)


def find_missing_32bit(vendor, read_needed):
    closure = find_vendor_closure(vendor, find_same_process_roots(vendor), read_needed)
    return [rel for rel in closure if not os.path.exists(os.path.join(vendor, "lib", rel))]


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    tree = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    out = argv[0] if argv else os.path.join(tree, "..", "..", "..", "out", "target", "product",
                                            "hy300")
    vendor = os.path.join(out, "vendor")
    missing = find_missing_32bit(vendor, read_needed_with_readelf)
    for rel in missing:
        print(f"FALTA 32 bits: /vendor/lib/{rel}", file=sys.stderr)
    if not missing:
        count = len(find_vendor_closure(vendor, find_same_process_roots(vendor),
                                        read_needed_with_readelf))
        print(f"ok: {count} bibliotecas same-process do vendor em lib64/ e lib/")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
