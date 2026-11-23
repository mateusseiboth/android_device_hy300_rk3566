#!/system/bin/sh
#
# SPDX-FileCopyrightText: 2026 Mateus Seiboth
# SPDX-License-Identifier: Apache-2.0
#
# Ir do LineageOS ao Alpine e ficar nele, pelo adb sem root:
#
#   adb shell setprop debug.hy300.alpine 1
#
# O init (init.rk3566.rc) inicia este script como root quando a prop vira 1, só no userdebug e com
# o adbd no ar. Ele grava a marca de "ficar" do Alpine na misc (0x10000, a mesma do diag e do
# scripts/reboot-to-alpine.sh do hy300-alpine) e faz um reboot normal (sys.powerctl=reboot, sem
# alvo: o init não grava BCB). O U-Boot sobe a partição boot, o Alpine vê a marca e não volta
# sozinho ao Lineage. Se a área da marca tiver outra coisa, não reinicia.
#
# Testes: tools/tests/test_alpine.py.

export PATH="/system/bin:/system_ext/bin:/vendor/bin:$PATH"

ALPINE_DIAG_LIB="${HY300_ALPINE_DIAG_LIB:-/vendor/bin/hy300-diag.sh}"
ALPINE_LOG_DIR="${HY300_ALPINE_LOG_DIR:-/metadata/hy300-diag}"

# write_stay_mark e DIAG_MISC vêm do diag (HY300_DIAG_LIB=1 só define as funções).
HY300_DIAG_LIB=1 . "$ALPINE_DIAG_LIB"

log_alpine() {
	mkdir -p "$ALPINE_LOG_DIR"
	echo "[$(cut -d' ' -f1 /proc/uptime 2>/dev/null) s] $*" >>"$ALPINE_LOG_DIR/alpine.txt"
}

is_userdebug() {
	case "$(getprop ro.build.type)" in
	userdebug | eng) return 0 ;;
	esac
	return 1
}

main() {
	is_userdebug || exit 0
	# Volta a 0 para um próximo "setprop debug.hy300.alpine 1" disparar de novo.
	setprop debug.hy300.alpine 0
	if ! write_stay_mark "$DIAG_MISC"; then
		log_alpine "pedido de ir ao Alpine: marca de ficar NÃO gravada (área da misc ocupada ou sem acesso); sem reinício"
		exit 1
	fi
	log_alpine "pedido de ir ao Alpine: marca de ficar gravada; reinício normal"
	sync
	setprop sys.powerctl reboot
}

main
