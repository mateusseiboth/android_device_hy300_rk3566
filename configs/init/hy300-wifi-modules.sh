#!/vendor/bin/sh
#
# SPDX-FileCopyrightText: 2026 Mateus Seiboth
# SPDX-License-Identifier: Apache-2.0
#
# Carrega o Wi-Fi AIC8800 no boot (init.rk3566.rc, em segundo plano): aic8800_bsp com o firmware do
# /vendor (só no build local) e aic8800_fdrv, depois o aic8800_btlpm (rfkill do Bluetooth, depende
# do bsp; falhar nele não afeta o Wi-Fi), espera a interface e grava
# vendor.hy300.wifi.iface (nome da interface ou "falhou"). As funções vêm do hy300-wifi.sh do
# repositório do projeto (as mesmas do initramfs de teste). A carga leva ~40 s.
#
# Testes: tools/tests/test_wifi_modules.py

WIFI_LIB="${HY300_WIFI_LIB:-/vendor/etc/hy300/hy300-wifi.sh}"
MODULE_DIR="${HY300_WIFI_MODULE_DIR:-/vendor/lib/modules}"
FIRMWARE_DIR=/vendor/etc/firmware/aic8800
IFACE_WAIT=60

# shellcheck source=/dev/null
. "$WIFI_LIB" || exit 1
if load_wifi_modules "$MODULE_DIR" "$FIRMWARE_DIR" && [ -f "$MODULE_DIR/aic8800_btlpm.ko" ]; then
	insmod "$MODULE_DIR/aic8800_btlpm.ko" || echo "insmod aic8800_btlpm falhou"
fi
if iface=$(wait_for_wireless_iface "$IFACE_WAIT"); then
	setprop vendor.hy300.wifi.iface "$iface"
	exit 0
fi
setprop vendor.hy300.wifi.iface falhou
exit 1
