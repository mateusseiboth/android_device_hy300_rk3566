#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2026 Mateus Seiboth
# SPDX-License-Identifier: Apache-2.0
#
"""Confere no host os módulos do audio_policy_configuration.xml do vendor com as regras que o HAL
de áudio AIDL de exemplo do AOSP aplica ao subir (hardware/interfaces/audio/aidl/default/
XsdcConversion.cpp). Uma regra quebrada aborta o HAL em laço e o system_server fica preso no
AudioService (boot 6, rodada 9: "HDMI In" em <attachedDevices>).

Regras (função do XsdcConversion.cpp entre parênteses):
- no máximo um <devicePorts> e um <mixPorts> por módulo (convertDevicePortsInModuleToAidl,
  convertMixPortsInModuleToAidl);
- o tipo de cada devicePort existe na tabela legado -> AIDL (convertDeviceTypeToAidl);
- um devicePort está em <attachedDevices> se e só se a conexão do tipo dele for vazia
  (convertDevicePortsInModuleToAidl): HDMI, USB, Bluetooth, analógico com fio etc. são externos;
- toda rota liga nomes de devicePort ou mixPort (getSinkPortId, getSourcePortIds).

A conexão de cada tipo vem da própria tabela do AOSP (frameworks/av/media/audioaidlconversion/
AidlConversionCppNdk.cpp, getAudioDevicePairs), lida do checkout.

Uso: tools/check_audio_policy.py [raiz do lineage]
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

CONVERSION = os.path.join("frameworks", "av", "media", "audioaidlconversion",
                          "AidlConversionCppNdk.cpp")
AOSP_CONFIGS = os.path.join("frameworks", "av", "services", "audiopolicy", "config")
XI_INCLUDE = "{http://www.w3.org/2001/XInclude}include"

SINGLE = re.compile(r"\{\s*(AUDIO_DEVICE_\w+),\s*make_AudioDeviceDescription\(\s*"
                    r"AudioDeviceType::\w+\s*(?:,\s*GET_DEVICE_DESC_CONNECTION\((\w+)\))?\s*\)")
PAIRED = re.compile(r"append_AudioDeviceDescription\(\s*pairs,\s*(AUDIO_DEVICE_\w+),\s*"
                    r"(AUDIO_DEVICE_\w+),\s*AudioDeviceType::\w+,\s*AudioDeviceType::\w+\s*"
                    r"(?:,\s*GET_DEVICE_DESC_CONNECTION\((\w+)\))?\s*\)")


def parse_connection_table(text):
    table = {}
    for legacy, connection in SINGLE.findall(text):
        table[legacy] = connection
    for legacy_in, legacy_out, connection in PAIRED.findall(text):
        table[legacy_in] = connection
        table[legacy_out] = connection
    return table


def find_port_problems(module, table, attached):
    problems = []
    for port in module.iter("devicePort"):
        name, device_type = port.get("tagName"), port.get("type")
        if device_type not in table:
            problems.append(f'devicePort "{name}": tipo {device_type} desconhecido '
                            "(convertDeviceTypeToAidl)")
            continue
        if (name in attached) != (table[device_type] == ""):
            where = "conexão " + table[device_type] if table[device_type] else "embutido"
            problems.append(f'devicePort "{name}" ({device_type}, {where}): está em '
                            "<attachedDevices> só se a conexão for vazia "
                            "(convertDevicePortsInModuleToAidl)")
    return problems


def find_route_problems(module):
    names = {p.get("tagName") for p in module.iter("devicePort")}
    names |= {p.get("name") for p in module.iter("mixPort")}
    problems = []
    for route in module.iter("route"):
        endpoints = [route.get("sink")] + [s.strip() for s in route.get("sources", "").split(",")]
        problems += [f'rota para "{route.get("sink")}": "{endpoint}" não é devicePort nem mixPort '
                     "(getSinkPortId/getSourcePortIds)" for endpoint in endpoints
                     if endpoint not in names]
    return problems


def find_problems_in_module(module, table):
    problems = [f"mais de um <{tag}> (convertDevicePortsInModuleToAidl)"
                for tag in ("devicePorts", "mixPorts") if len(module.findall(tag)) > 1]
    attached = {item.text.strip() for item in module.iter("item") if item.text}
    return problems + find_port_problems(module, table, attached) + find_route_problems(module)


def find_problems_in_text(xml_text, table):
    root = ET.fromstring(xml_text)
    modules = [root] if root.tag == "module" else list(root.iter("module"))
    # AudioPolicyConfigXmlConverter::init(): o "r_submix" não é convertido (configuração fixa).
    return [f'módulo "{m.get("name")}": {problem}'
            for m in modules if m.get("name") != "r_submix"
            for problem in find_problems_in_module(m, table)]


def find_module_problems(path, table):
    with open(path) as f:
        return find_problems_in_text(f.read(), table)


def resolve_include(href, tree, top):
    for base in (os.path.join(tree, "configs", "audio"), os.path.join(top, AOSP_CONFIGS)):
        path = os.path.join(base, href)
        if os.path.exists(path):
            return path
    return None


def check_tree(tree, top):
    with open(os.path.join(top, CONVERSION)) as f:
        table = parse_connection_table(f.read())
    main = ET.parse(os.path.join(tree, "configs", "audio", "audio_policy_configuration.xml"))
    problems = []
    modules = main.getroot().find("modules")
    for include in modules.iter(XI_INCLUDE):
        path = resolve_include(include.get("href"), tree, top)
        if path is None:
            problems.append(f'{include.get("href")}: arquivo incluído não encontrado')
            continue
        problems += [f"{os.path.basename(path)}: {p}" for p in find_module_problems(path, table)]
    for module in modules.iter("module"):
        if module.get("name") != "r_submix":
            problems += find_problems_in_module(module, table)
    return problems


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    tree = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    top = os.path.abspath(argv[0]) if argv else os.path.normpath(os.path.join(tree, "..", "..", ".."))
    problems = check_tree(tree, top)
    for problem in problems:
        print(f"FALHOU: {problem}", file=sys.stderr)
    if not problems:
        print("ok: os módulos do audio policy passam nas regras do HAL de áudio AIDL de exemplo")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
