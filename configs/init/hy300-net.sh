#!/system/bin/sh
#
# SPDX-FileCopyrightText: 2026 Mateus Seiboth
# SPDX-License-Identifier: Apache-2.0
#
# Rede e adb pela rede no userdebug do HY300, sem credencial na imagem nem no git. Roda depois do
# boot_completed (init.rk3566.rc) e lê o que o Alpine deixou em /metadata/hy300-diag/:
#
#   wifi.conf (modo 600, uma chave por linha; o arquivo não é executado):
#       WIFI_SSID=Nome da rede
#       WIFI_PSK=senha
#       WIFI_SECURITY=wpa2          (opcional: wpa2, o padrão; wpa3; open)
#   adb_keys: chave pública do PC (conteúdo de ~/.android/adbkey.pub)
#
# 1) adb pela rede: adb_enabled=1, service.adb.tcp.port=5555 e reinicia o adbd. A autenticação
#    continua ligada; a chave do PC vai para /data/misc/adb/adb_keys (sem duplicar). Na imagem de
#    uso (androidboot.hy300.perfil=uso) só a chave é instalada; o adb fica desligado.
# 2) Wi-Fi: `cmd wifi set-wifi-enabled enabled` e `cmd wifi connect-network`, que também salva a
#    rede. IP por DHCP (o cmd wifi não tem opção de IP fixo). Depois apaga o wifi.conf.
# Log em /metadata/hy300-diag/net.txt, nunca com a senha.
#
# Testes: tools/tests/test_net.py (HY300_NET_LIB=1 só define as funções).

export PATH="/system/bin:/system_ext/bin:/vendor/bin:$PATH"

NET_ROOT="${HY300_NET_ROOT:-/metadata/hy300-diag}"
NET_ADB_DIR="${HY300_NET_ADB_DIR:-/data/misc/adb}"
NET_WAIT="${HY300_NET_WAIT:-10}"
NET_ADB_PORT=5555

log_net() {
	echo "[$(cut -d' ' -f1 /proc/uptime 2>/dev/null) s] $*" >>"$NET_ROOT/net.txt"
}

is_userdebug() {
	case "$(getprop ro.build.type)" in
	userdebug | eng) return 0 ;;
	esac
	return 1
}

# Lê só as chaves conhecidas, sem `.`/eval: o valor é tudo depois do primeiro "=".
read_wifi_conf() {
	[ -f "$1" ] || return 1
	case "$(stat -c %a "$1" 2>/dev/null)" in
	600 | 400) ;;
	*) return 1 ;;
	esac
	WIFI_SSID=
	WIFI_PSK=
	WIFI_SECURITY=wpa2
	while IFS= read -r line || [ -n "$line" ]; do
		case "$line" in
		WIFI_SSID=*) WIFI_SSID=${line#WIFI_SSID=} ;;
		WIFI_PSK=*) WIFI_PSK=${line#WIFI_PSK=} ;;
		WIFI_SECURITY=*) WIFI_SECURITY=${line#WIFI_SECURITY=} ;;
		esac
	done <"$1"
	[ -n "$WIFI_SSID" ]
}

install_adb_key() {
	[ -s "$1" ] || return 0
	mkdir -p "$NET_ADB_DIR"
	key=$(cat "$1")
	if ! grep -qxF "$key" "$NET_ADB_DIR/adb_keys" 2>/dev/null; then
		echo "$key" >>"$NET_ADB_DIR/adb_keys"
		log_net "chave do adb instalada"
	fi
	chown system:shell "$NET_ADB_DIR/adb_keys"
	chmod 0640 "$NET_ADB_DIR/adb_keys"
}

enable_network_adb() {
	settings put global development_settings_enabled 1
	settings put global adb_enabled 1
	setprop service.adb.tcp.port "$NET_ADB_PORT"
	setprop ctl.restart adbd
	log_net "adb pela rede na porta $NET_ADB_PORT (com autenticação)"
}

connect_wifi() {
	cmd wifi set-wifi-enabled enabled >/dev/null
	sleep "$NET_WAIT"
	log_net "conectando ao Wi-Fi ($WIFI_SECURITY)"
	if [ "$WIFI_SECURITY" = open ]; then
		result=$(cmd wifi connect-network "$WIFI_SSID" open 2>&1)
	else
		result=$(cmd wifi connect-network "$WIFI_SSID" "$WIFI_SECURITY" "$WIFI_PSK" 2>&1)
	fi
	log_net "cmd wifi: $(echo "$result" | head -n 1)"
}

# Imagem de uso (androidboot.hy300.perfil=uso): o adb não liga sozinho. O usuário liga em Opções
# do desenvolvedor (depuração USB e ADB pela rede, do TvSettings).
is_profile_uso() {
	[ "$(getprop ro.boot.hy300.perfil)" = uso ]
}

main() {
	is_userdebug || exit 0
	mkdir -p "$NET_ROOT"
	install_adb_key "$NET_ROOT/adb_keys"
	if is_profile_uso; then
		log_net "imagem de uso: adb pela rede fica desligado"
	else
		enable_network_adb
	fi
	if read_wifi_conf "$NET_ROOT/wifi.conf"; then
		connect_wifi
		rm -f "$NET_ROOT/wifi.conf"
		sync
		log_net "wifi.conf apagado do metadata"
	elif [ -e "$NET_ROOT/wifi.conf" ]; then
		log_net "wifi.conf ignorado (precisa de modo 600 e WIFI_SSID)"
	fi
}

[ "${HY300_NET_LIB:-0}" = 1 ] || main
