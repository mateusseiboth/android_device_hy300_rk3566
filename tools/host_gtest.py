#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2026 Mateus Seiboth
# SPDX-License-Identifier: Apache-2.0
#
"""Compila e roda no host os testes gtest que vivem dentro dos patches da árvore (código novo
dos projetos do AOSP que não depende do Android), sem o build do Soong.

Os arquivos são tirados do próprio patch com `git apply --include`, então o que é testado é
exatamente o que vai para o checkout.
"""
import os
import shutil
import subprocess
import tempfile

TREE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
WARNINGS = ["-Wall", "-Wextra", "-Werror", "-Wconversion", "-Wunused", "-Wunreachable-code"]


def find_compiler():
    return shutil.which("clang++") or shutil.which("g++")


def has_gtest(compiler):
    probe = subprocess.run([compiler, "-x", "c++", "-std=c++20", "-", "-o", os.devnull,
                            "-lgtest", "-lgtest_main"],
                           input="#include <gtest/gtest.h>\n", capture_output=True, text=True)
    return probe.returncode == 0


def extract(patch, includes, destination):
    """Aplica só os caminhos `includes` (globs) do patch num diretório vazio."""
    args = ["git", "apply", *[f"--include={pattern}" for pattern in includes]]
    subprocess.run([*args, os.path.abspath(patch)], cwd=destination, check=True,
                   capture_output=True, text=True)


def run(patch, includes, sources, extra_flags=()):
    """Extrai, compila `sources` (relativos à raiz do projeto do patch) e roda. Devolve o
    CompletedProcess da execução; levanta CalledProcessError se a compilação falhar."""
    compiler = find_compiler()
    with tempfile.TemporaryDirectory() as work:
        extract(patch, includes, work)
        binary = os.path.join(work, "test")
        compile_args = [compiler, "-std=c++20", *WARNINGS, *extra_flags,
                        *[os.path.join(work, source) for source in sources],
                        "-lgtest", "-lgtest_main", "-pthread", "-o", binary]
        subprocess.run(compile_args, check=True, capture_output=True, text=True)
        return subprocess.run([binary], capture_output=True, text=True)
