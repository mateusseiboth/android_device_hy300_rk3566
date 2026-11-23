#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2026 Mateus Seiboth
# SPDX-License-Identifier: Apache-2.0
#
"""Aplica os patches da árvore (patches/<caminho do projeto>/NNNN-*.patch) nos projetos de
fora dela, no checkout do LineageOS. Rodar depois de cada `repo sync`.

Cada patch é aplicado com `git apply` (fica como mudança no working tree do projeto, sem
commit). Se o patch já está aplicado, passa adiante; se não encaixa, para com erro.

Uso: device/txcz/hy300/tools/apply_patches.py [raiz_do_lineage]
     (padrão: $ANDROID_BUILD_TOP ou o diretório atual)
"""
import os
import subprocess
import sys

PATCHES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "patches")


def find_patches(patches_dir):
    found = {}
    for root, _dirs, files in sorted(os.walk(patches_dir)):
        patches = sorted(name for name in files if name.endswith(".patch"))
        if patches:
            project = os.path.relpath(root, patches_dir).replace(os.sep, "/")
            found[project] = [os.path.join(root, name) for name in patches]
    return found


def git_apply(project_dir, patch, *flags):
    return subprocess.run(["git", "apply", *flags, patch], cwd=project_dir,
                          capture_output=True, text=True).returncode == 0


def apply_one(project_dir, patch):
    if git_apply(project_dir, patch, "--reverse", "--check"):
        return "já aplicado"
    if git_apply(project_dir, patch):
        return "aplicado"
    raise RuntimeError(f"{os.path.basename(patch)} não encaixa em {project_dir}")


def apply_all(top, patches_dir=PATCHES_DIR):
    results = []
    for project, patches in find_patches(patches_dir).items():
        project_dir = os.path.join(top, project)
        if not os.path.isdir(project_dir):
            raise RuntimeError(f"projeto {project} não existe em {top}")
        results += [(project, os.path.basename(p), apply_one(project_dir, p)) for p in patches]
    return results


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    top = argv[0] if argv else os.environ.get("ANDROID_BUILD_TOP", os.getcwd())
    try:
        results = apply_all(os.path.abspath(top))
    except RuntimeError as error:
        print(f"FALHOU: {error}", file=sys.stderr)
        return 1
    for project, patch, state in results:
        print(f"{project}: {patch} {state}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
