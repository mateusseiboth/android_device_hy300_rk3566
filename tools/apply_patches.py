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
import shutil
import subprocess
import sys
import tempfile

PATCHES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "patches")


def find_patches(patches_dir):
    found = {}
    for root, _dirs, files in sorted(os.walk(patches_dir)):
        patches = sorted(name for name in files if name.endswith(".patch"))
        if patches:
            project = os.path.relpath(root, patches_dir).replace(os.sep, "/")
            found[project] = [os.path.join(root, name) for name in patches]
    return found


def git_apply(project_dir, *args):
    return subprocess.run(["git", "apply", *args], cwd=project_dir,
                          capture_output=True, text=True).returncode == 0


def find_touched_files(patch):
    touched = set()
    with open(patch, errors="replace") as handle:
        for line in handle:
            if line.startswith("diff --git "):
                _, _, a_path, b_path = line.split()[:4]
                touched.update({a_path[2:], b_path[2:]})
    return touched


def copy_touched_files(project_dir, patches, scratch):
    for rel in set().union(*(find_touched_files(p) for p in patches)):
        src = os.path.join(project_dir, rel)
        if os.path.isfile(src):
            os.makedirs(os.path.dirname(os.path.join(scratch, rel)), exist_ok=True)
            shutil.copy2(src, os.path.join(scratch, rel))


def is_series_applied(project_dir, patches):
    """Desfaz a série de trás para a frente numa cópia dos arquivos tocados: um patch que mexe
    nas linhas de outro (codec2/0005 sobre o 0002) não se desfaz sozinho enquanto o de cima
    estiver aplicado, e o git apply com vários patches confere cada um contra o original."""
    with tempfile.TemporaryDirectory(prefix="hy300-patches-") as scratch:
        copy_touched_files(project_dir, patches, scratch)
        return all(subprocess.run(["git", "apply", "--reverse", patch], cwd=scratch,
                                  capture_output=True).returncode == 0
                   for patch in reversed(patches))


def count_applied(project_dir, patches):
    """Quantos patches do começo da série já estão aplicados."""
    for count in range(len(patches), 0, -1):
        if is_series_applied(project_dir, patches[:count]):
            return count
    return 0


def apply_series(project_dir, patches):
    applied = count_applied(project_dir, patches)
    results = [(patch, "já aplicado") for patch in patches[:applied]]
    for patch in patches[applied:]:
        if not git_apply(project_dir, patch):
            raise RuntimeError(f"{os.path.basename(patch)} não encaixa em {project_dir}")
        results.append((patch, "aplicado"))
    return results


def apply_all(top, patches_dir=PATCHES_DIR):
    results = []
    for project, patches in find_patches(patches_dir).items():
        project_dir = os.path.join(top, project)
        if not os.path.isdir(project_dir):
            raise RuntimeError(f"projeto {project} não existe em {top}")
        results += [(project, os.path.basename(patch), state)
                    for patch, state in apply_series(project_dir, patches)]
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
