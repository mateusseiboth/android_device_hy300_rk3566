#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2026 Mateus Seiboth
# SPDX-License-Identifier: Apache-2.0
#
"""Confere, no host, se o VINTF montado declara os HALs sem os quais o system_server (ou outro
serviço essencial) do LineageOS 24 cai. O check_vintf do build só confere compatibilidade: um HAL
que falta inteiro passa, e no primeiro boot faltou o IPower (o system_server morreu no
HintManagerService).

Lê os manifestos de out/target/product/hy300: vendor/etc/vintf e odm/etc/vintf (manifest.xml e
manifest/*.xml) e os fragmentos dos APEX de vendor que o check_vintf do build extrai em
obj/PACKAGING/check_vintf_all_intermediates/apex/*/etc/vintf. A lista do que é obrigatório e por
quê fica em configs/vintf/required_hals.txt (uma instância por linha: pacote.Interface/instância
e o motivo).

Também confere que todo HAL AIDL/HIDL declarado tem um serviço do init com a "interface"
correspondente (vendor/etc/init, odm/etc/init e os .rc dos APEX de vendor): é o que o
servicemanager usa para subir o serviço sob demanda. No boot 3 o audioserver pediu o
IModule/default 91 vezes e o init não tinha a quem pedir. HALs "native" (mapper) não passam pelo
servicemanager e ficam de fora.

Uso: tools/check_vintf_hals.py <out/target/product/hy300> [--required arquivo]
"""
import argparse
import glob
import os
import sys
import xml.etree.ElementTree as ET

REQUIRED_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "configs", "vintf",
                                "required_hals.txt")
MANIFEST_GLOBS = (
    "vendor/etc/vintf/manifest.xml",
    "vendor/etc/vintf/manifest/*.xml",
    "odm/etc/vintf/manifest.xml",
    "odm/etc/vintf/manifest/*.xml",
    "obj/PACKAGING/check_vintf_all_intermediates/apex/*/etc/vintf/*.xml",
)


RC_GLOBS = (
    "vendor/etc/init/*.rc",
    "vendor/etc/init/hw/*.rc",
    "odm/etc/init/*.rc",
    "obj/PACKAGING/check_vintf_all_intermediates/apex/*/etc/*.rc",
)
SERVICE_FORMATS = ("aidl", "hidl")


def read_hal_instances(hal):
    name = hal.findtext("name", "").strip()
    found = set()
    for fqname in hal.findall("fqname"):
        # AIDL: "IPower/default"; HIDL: "@1.1::IComponentStore/default".
        text = fqname.text.strip().rpartition("::")[2]
        found.add(f"{name}.{text}")
    for interface in hal.findall("interface"):
        iface = interface.findtext("name", "").strip()
        found |= {f"{name}.{iface}/{inst.text.strip()}" for inst in interface.findall("instance")}
    return found


def read_manifest(path, formats=None):
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return set()
    found = set()
    for hal in root.iter("hal"):
        if formats is None or hal.get("format", "hidl") in formats:
            found |= read_hal_instances(hal)
    return found


def find_declared(out, formats=None):
    found = set()
    for pattern in MANIFEST_GLOBS:
        for path in sorted(glob.glob(os.path.join(out, pattern))):
            found |= read_manifest(path, formats)
    return found


def parse_interface_line(words):
    # "interface aidl pacote.IFoo/instância" ou "interface pacote@1.1::IFoo instância"
    if len(words) == 3 and words[1] == "aidl":
        return words[2]
    if len(words) == 3 and "::" in words[1]:
        package, _, iface = words[1].partition("::")
        return f"{package.partition('@')[0]}.{iface}/{words[2]}"
    return None


def find_init_interfaces(out):
    found = set()
    for pattern in RC_GLOBS:
        for path in sorted(glob.glob(os.path.join(out, pattern))):
            with open(path, errors="replace") as f:
                for line in f:
                    words = line.split()
                    if words and words[0] == "interface":
                        name = parse_interface_line(words)
                        if name:
                            found.add(name)
    return found


def find_without_init_service(out):
    declared = find_declared(out, SERVICE_FORMATS)
    return sorted(declared - find_init_interfaces(out))


def read_required(path):
    required = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, _, reason = line.partition(" ")
            required.append((name, reason.strip()))
    return required


def find_missing(out, required):
    declared = find_declared(out)
    return [(name, reason) for name, reason in required if name not in declared]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out")
    parser.add_argument("--required", default=REQUIRED_DEFAULT)
    args = parser.parse_args(argv)
    required = read_required(args.required)
    missing = find_missing(args.out, required)
    for name, reason in missing:
        print(f"FALTA {name}: {reason}")
    orphans = find_without_init_service(args.out)
    for name in orphans:
        print(f"SEM SERVIÇO {name}: declarado no VINTF, nenhum .rc tem \"interface\" para ele")
    if missing or orphans:
        return 1
    print(f"ok: {len(required)} HALs obrigatórios declarados; todo HAL declarado tem serviço no init")
    return 0


if __name__ == "__main__":
    sys.exit(main())
