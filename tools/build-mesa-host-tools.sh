#!/usr/bin/env bash
#
# SPDX-FileCopyrightText: 2026 Mateus Seiboth
# SPDX-License-Identifier: Apache-2.0
#
# Ferramentas de HOST que o Mesa 26 precisa para compilar o Panfrost em cross (Android):
# mesa_clc, vtn_bindgen2 e panfrost_compile (kernels OpenCL pré-compilados da libpan). Têm de
# vir da MESMA fonte do external/mesa3d, por isso são compiladas aqui e não pegas do sistema.
#
# Uso: device/txcz/hy300/tools/build-mesa-host-tools.sh [raiz_do_lineage] [saída]
#   padrões: $ANDROID_BUILD_TOP (ou o diretório atual) e ~/hy300-work/mesa-host
# Depois: export PATH="<saída>/install/bin:$PATH" antes do `m` (o aospext roda o meson com o
# PATH de quem chamou o build).
#
# Dependências no Fedora 45: meson, ninja-build, python3-mako, python3-pyyaml, python3-ply,
# glslang, libdrm-devel, expat-devel, llvm22-devel, clang22-devel,
# spirv-llvm-translator22-devel, libclc22-devel, spirv-tools-devel. O LLVM 23 do sistema não
# serve: o clc_helpers.cpp do Mesa 26.1-devel não compila com ele (TargetRegistry::lookupTarget).
set -euo pipefail

TOP="$(cd "${1:-${ANDROID_BUILD_TOP:-$PWD}}" && pwd)"
OUT="${2:-$HOME/hy300-work/mesa-host}"
LLVM_CONFIG="${LLVM_CONFIG:-/usr/lib64/llvm22/bin/llvm-config}"
SRC="$TOP/external/mesa3d"

[[ -f "$SRC/meson.build" ]] || { echo "sem $SRC/meson.build" >&2; exit 1; }
[[ -x "$LLVM_CONFIG" ]] || { echo "sem $LLVM_CONFIG (llvm22-devel)" >&2; exit 1; }

mkdir -p "$OUT"
printf "[binaries]\nllvm-config = '%s'\n" "$LLVM_CONFIG" >"$OUT/native-llvm.ini"

[[ -f "$OUT/build/build.ninja" ]] || nice -n 10 meson setup "$OUT/build" "$SRC" \
	--native-file "$OUT/native-llvm.ini" --prefix="$OUT/install" -Dbuildtype=release \
	-Dplatforms= -Dgallium-drivers=panfrost -Dvulkan-drivers= -Dglx=disabled -Degl=disabled \
	-Dgbm=disabled -Dgles1=disabled -Dllvm=enabled -Dmesa-clc=enabled -Dinstall-mesa-clc=true \
	-Dprecomp-compiler=enabled -Dinstall-precomp-compiler=true -Dvalgrind=disabled \
	-Dlibunwind=disabled -Dlmsensors=disabled

nice -n 10 ninja -C "$OUT/build" -j"${JOBS:-12}" install >/dev/null
for tool in mesa_clc vtn_bindgen2 panfrost_compile; do
	[[ -x "$OUT/install/bin/$tool" ]] || { echo "FALHOU: $tool não foi instalado" >&2; exit 1; }
done
echo "ok: export PATH=\"$OUT/install/bin:\$PATH\""
