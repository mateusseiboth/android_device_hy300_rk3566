#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2026 Mateus Seiboth
# SPDX-License-Identifier: Apache-2.0
#
"""Confere a sepolicy da árvore (sepolicy/vendor e sepolicy/system_ext) contra a política do
LineageOS sem rodar o Soong: refaz o policy.conf das neverallows com o mesmo m4 e as mesmas
flags do último build (o script de regra do sepolicy_neverallows.checkpolicy.conf em out/soong),
troca os arquivos da árvore principal pelos desta árvore e compila com o checkpolicy do build
(que falha em qualquer neverallow). Depois confere file_contexts, property_contexts e
service_contexts com o checkfc contra a política compilada.

Uso: tools/check_sepolicy.py [raiz_do_lineage]   (padrão: $ANDROID_BUILD_TOP ou ~/android/lineage)
Precisa de um build anterior (out/host/linux-x86/bin e out/soong/rule_builder_scripts).
"""
import glob
import os
import shlex
import subprocess
import sys
import tempfile

TREE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DEVICE_PREFIX = "device/txcz/hy300/sepolicy/"
RULE_MARKER = "sepolicy_neverallows.checkpolicy.conf/android_common/sepolicy_neverallows.checkpolicy.conf"
POLICY_DIRS = ("sepolicy/system_ext/public", "sepolicy/system_ext/private", "sepolicy/vendor")


def find_rule_script(top):
    for script in glob.glob(os.path.join(top, "out/soong/rule_builder_scripts/*.sh")):
        with open(script) as handle:
            text = handle.read()
        if RULE_MARKER in text and "bin/m4" in text:
            return text
    raise RuntimeError("script do sepolicy_neverallows.checkpolicy.conf não achado em out/soong")


def extract_m4_args(script):
    """Argumentos do m4 (flags e arquivos), sem o redirecionamento final."""
    command = script[script.index("prebuilts/build-tools/linux-x86/bin/m4"):]
    command = command[:command.index(" > ")] if " > " in command else command[:command.index(">")]
    return shlex.split(command)[1:]


def policy_files(tree=TREE):
    """Arquivos .te e genfs_contexts desta árvore, relativos a ela, em ordem estável."""
    found = []
    for directory in POLICY_DIRS:
        base = os.path.join(tree, directory)
        found += sorted(os.path.join(base, name) for name in os.listdir(base)
                        if name.endswith(".te") or name == "genfs_contexts")
    return found


def merge_files(args, files):
    """Tira os arquivos da árvore principal e põe os desta: .te depois do último .te e
    genfs_contexts depois do último genfs_contexts, como o build faz por categoria."""
    kept = [arg for arg in args if not arg.startswith(DEVICE_PREFIX)]
    for path in files:
        is_te = path.endswith(".te")
        last = max(i for i, arg in enumerate(kept)
                   if (arg.endswith(".te") if is_te else arg.endswith("genfs_contexts")))
        kept.insert(last + 1, path)
    return kept


def run(args, cwd, **kwargs):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, **kwargs)


def check(top):
    host = os.path.join(top, "out/host/linux-x86/bin")
    args = merge_files(extract_m4_args(find_rule_script(top)), policy_files())
    errors = []
    with tempfile.TemporaryDirectory() as work:
        # O build separa os arquivos com um arquivo de uma linha em branco, criado na hora.
        newline = os.path.join(work, "newline")
        with open(newline, "w") as handle:
            handle.write("\n")
        args = [newline if arg.endswith("/newline") else arg for arg in args]
        conf = os.path.join(work, "policy.conf")
        with open(conf, "w") as out:
            result = subprocess.run([os.path.join(top, "prebuilts/build-tools/linux-x86/bin/m4"),
                                     *args], cwd=top, stdout=out, stderr=subprocess.PIPE,
                                    text=True)
        if result.returncode != 0:
            return [f"m4: {result.stderr.strip()[:3000]}"]
        policy = os.path.join(work, "sepolicy")
        result = run([os.path.join(host, "checkpolicy"), "-M", "-c", "30", "-o", policy, conf],
                     top)
        if result.returncode != 0:
            return [f"checkpolicy: {(result.stdout + result.stderr).strip()[-6000:]}"]
        contexts = [("", "sepolicy/vendor/file_contexts"),
                    ("", "sepolicy/system_ext/private/file_contexts"),
                    ("-p", "sepolicy/vendor/property_contexts"),
                    ("-p", "sepolicy/system_ext/private/property_contexts"),
                    ("-s", "sepolicy/vendor/service_contexts")]
        for flag, path in contexts:
            result = run([os.path.join(host, "checkfc"), *([flag] if flag else []), policy,
                          os.path.join(TREE, path)], top)
            if result.returncode != 0:
                errors.append(f"checkfc {path}: {(result.stdout + result.stderr).strip()}")
    return errors


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    top = argv[0] if argv else os.environ.get("ANDROID_BUILD_TOP",
                                              os.path.expanduser("~/android/lineage"))
    try:
        errors = check(os.path.abspath(top))
    except RuntimeError as error:
        print(f"FALHOU: {error}", file=sys.stderr)
        return 2
    for error in errors:
        print(f"FALHOU: {error}", file=sys.stderr)
    if not errors:
        print("ok: sepolicy compila com as neverallows do build e os contextos conferem")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
