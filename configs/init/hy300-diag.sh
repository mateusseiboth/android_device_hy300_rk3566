#!/system/bin/sh
#
# SPDX-FileCopyrightText: 2026 Mateus Seiboth
# SPDX-License-Identifier: Apache-2.0
#
# Diagnóstico do primeiro boot do LineageOS no HY300, sem rede e sem ninguém olhando (só
# userdebug, pelo ro.build.type). Liga com androidboot.hy300.diag=1 na cmdline ou com
# /metadata/hy300-diag/ativo.
#
# Grava em /metadata/hy300-diag/<n>/ (n = contador de boots; ficam as 3 últimas): dmesg, logcat,
# getprop e /proc/interrupts a cada 20 s; depois do boot_completed, o estado do sistema
# (SurfaceFlinger, codecs, memória, frequências, módulos, processos); em paralelo, o estado do
# Wi-Fi AIC8800.
#
# Com o boot_completed e o adb pela rede de pé (hy300-net.sh: adbd na porta 5555 e IPv4 no
# wlan0), as coletas param: quem conduz é o adb.
#
# Aos 8 min de uptime, com ou sem boot_completed:
#  - se o adb pela rede estiver de pé, não reinicia e o diag termina;
#  - senão grava a marca de "ficar" do Alpine na misc (0x10000, o mesmo formato do
#    scripts/reboot-to-alpine.sh do hy300-alpine: o Alpine fica no ar em vez de voltar sozinho ao
#    Lineage), faz sync e um reboot NORMAL (sys.powerctl=reboot, sem alvo: o init não grava BCB) e
#    o U-Boot sobe a partição boot, onde está o Alpine.
#
# Testes: tools/tests/test_diag.py (HY300_DIAG_LIB=1 só define as funções).

# logcat, ip, iw e dumpsys ficam em /system/bin. O sh do vendor força PATH=/vendor/bin:/vendor/xbin
# (MKSH_DEFPATH_OVERRIDE do sh_vendor), e no boot 2 eles saíram "inaccessible or not found". O .rc
# roda o diag com /system/bin/sh, e o PATH fica explícito aqui também.
export PATH="/system/bin:/system_ext/bin:/vendor/bin:/vendor/xbin:$PATH"

DIAG_ROOT="${HY300_DIAG_ROOT:-/metadata/hy300-diag}"
DIAG_UPTIME="${HY300_DIAG_UPTIME:-/proc/uptime}"
DIAG_SYS="${HY300_DIAG_SYS:-/sys}"
DIAG_PROC="${HY300_DIAG_PROC:-/proc}"
DIAG_INTERVAL="${HY300_DIAG_INTERVAL:-20}"
DIAG_REBOOT_AFTER="${HY300_DIAG_REBOOT_AFTER:-480}"
DIAG_WIFI="${HY300_DIAG_WIFI:-1}"
DIAG_WIFI_LIB="${HY300_DIAG_WIFI_LIB:-/vendor/etc/hy300/hy300-wifi.sh}"
DIAG_MODULE_DIR="${HY300_DIAG_MODULE_DIR:-/vendor/lib/modules}"
DIAG_FIRMWARE_DIR="${HY300_DIAG_FIRMWARE_DIR:-/vendor/etc/firmware/aic8800}"
DIAG_MISC="${HY300_DIAG_MISC:-/dev/block/by-name/misc}"
DIAG_MAX_LOOPS="${HY300_DIAG_MAX_LOOPS:-1000000}"
# Marca de ficar: "hy300-ficar\0" + versão 1, 16 bytes em 0x10000 (bloco 4096 de 16 bytes).
STAY_MARK_INDEX=4096
STAY_MARK_HEX="68 79 33 30 30 2d 66 69 63 61 72 00 01 00 00 00"
STAY_ZERO_HEX="00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00"
DIAG_WIFI_IFACE_WAIT=60

# userdebug pelo ro.build.type: o LineageOS liga PRODUCT_NOT_DEBUGGABLE_IN_USERDEBUG e o
# userdebug sai com ro.debuggable=0.
is_diag_enabled() {
	case "$(getprop ro.build.type)" in
	userdebug | eng) ;;
	*) return 1 ;;
	esac
	[ "$(getprop ro.boot.hy300.diag)" = 1 ] && return 0
	[ -e "$DIAG_ROOT/ativo" ]
}

next_boot_dir() {
	mkdir -p "$1" || return 1
	count=$(cat "$1/contador" 2>/dev/null)
	case "$count" in
	'' | *[!0-9]*) count=0 ;;
	esac
	count=$((count + 1))
	echo "$count" >"$1/contador"
	mkdir -p "$1/$count" || return 1
	echo "$1/$count"
}

# O metadata tem 16 MiB: apaga as coletas mais antigas e deixa as últimas $2.
prune_old_boots() {
	# sh não tem variável local: nomes próprios para não sobrescrever o "dir" do main.
	prune_last=$(cat "$1/contador" 2>/dev/null)
	case "$prune_last" in
	'' | *[!0-9]*) return 0 ;;
	esac
	for prune_entry in "$1"/*; do
		prune_name=${prune_entry##*/}
		case "$prune_name" in
		'' | *[!0-9]*) continue ;;
		esac
		[ "$prune_name" -le $((prune_last - $2)) ] && rm -rf "$prune_entry"
	done
	return 0
}

uptime_seconds() {
	read -r up _ <"$DIAG_UPTIME"
	echo "${up%%.*}"
}

log_line() {
	echo "[$(uptime_seconds) s] $2" >>"$1/diag.txt"
}

# Grava num .tmp e renomeia: o arquivo anterior fica inteiro se o reboot cortar no meio.
save_output() {
	"$@" >"$OUT_FILE.tmp" 2>&1
	mv -f "$OUT_FILE.tmp" "$OUT_FILE"
}

snapshot() {
	OUT_FILE="$1/dmesg.txt" save_output dmesg
	OUT_FILE="$1/logcat.txt" save_output logcat -b all -d -v threadtime
	OUT_FILE="$1/getprop.txt" save_output getprop
	OUT_FILE="$1/interrupts.txt" save_output cat "$DIAG_PROC/interrupts"
	sync
}

dump_frequencies() {
	for file in "$DIAG_SYS"/devices/system/cpu/cpufreq/policy*/scaling_cur_freq \
		"$DIAG_SYS"/devices/system/cpu/cpufreq/policy*/scaling_governor \
		"$DIAG_SYS"/devices/system/cpu/cpufreq/policy*/scaling_max_freq \
		"$DIAG_SYS"/class/devfreq/*/cur_freq "$DIAG_SYS"/class/devfreq/*/governor \
		"$DIAG_SYS"/class/devfreq/*/max_freq "$DIAG_SYS"/class/thermal/thermal_zone*/temp; do
		[ -e "$file" ] && echo "$file: $(cat "$file" 2>/dev/null)"
	done
	return 0
}

collect_after_boot() {
	OUT_FILE="$1/surfaceflinger.txt" save_output dumpsys SurfaceFlinger
	OUT_FILE="$1/media.txt" save_output dumpsys media.player
	OUT_FILE="$1/hal.txt" save_output lshal
	OUT_FILE="$1/meminfo.txt" save_output cat "$DIAG_PROC/meminfo"
	OUT_FILE="$1/freq.txt" save_output dump_frequencies
	OUT_FILE="$1/lsmod.txt" save_output lsmod
	OUT_FILE="$1/ps.txt" save_output ps -A
	sync
}

# Wi-Fi AIC8800: os módulos sobem pelo init (hy300-wifi-modules) e a interface é do Android
# (wpa_supplicant). O diag só registra o estado (sem scan próprio, que brigaria com o
# supplicant). Se a interface não aparecer, carrega os módulos ele mesmo e tenta religar o chip.
# Nomes de rede e endereços não são gravados.
run_wifi_test() {
	report="$1/wifi.txt"
	# shellcheck source=/dev/null
	. "$DIAG_WIFI_LIB" || { echo "sem $DIAG_WIFI_LIB" >>"$report"; return 1; }
	{
		echo "[$(uptime_seconds) s] início"
		has_wifi_card && echo "chip no barramento SDIO" || echo "chip fora do barramento SDIO"
		if ! iface=$(wait_for_wireless_iface "$DIAG_WIFI_IFACE_WAIT"); then
			echo "[$(uptime_seconds) s] sem interface sem fio em $DIAG_WIFI_IFACE_WAIT s; carregando os módulos"
			dump_sdio_state
			load_wifi_modules "$DIAG_MODULE_DIR" "$DIAG_FIRMWARE_DIR"
			echo "[$(uptime_seconds) s] módulos carregados (rc=$?)"
			if ! iface=$(wait_for_wireless_iface "$DIAG_WIFI_IFACE_WAIT"); then
				echo "religando o chip (WL_REG_ON) e tentando de novo"
				recover_wifi_chip
				load_wifi_modules "$DIAG_MODULE_DIR" "$DIAG_FIRMWARE_DIR"
				iface=$(wait_for_wireless_iface "$DIAG_WIFI_IFACE_WAIT") ||
					{ echo "[$(uptime_seconds) s] sem interface sem fio de novo"; dump_sdio_state; return 1; }
			fi
		fi
		echo "[$(uptime_seconds) s] interface $iface"
		iw dev "$iface" link 2>&1 | grep -v -i -e 'SSID' -e 'Connected to'
		dmesg | grep -i -e aic -e rwnx -e sdio -e mmc1 | tail -n 200
	} >>"$report" 2>&1
	sync
}

# adb pela rede de pé: adbd rodando na porta 5555 e IPv4 no wlan0 (hy300-net.sh liga os dois).
is_network_adb_up() {
	[ "$(getprop init.svc.adbd)" = running ] || return 1
	[ "$(getprop service.adb.tcp.port)" = 5555 ] || return 1
	ip -4 addr show wlan0 2>/dev/null | grep -q 'inet '
}

read_mark_area() {
	dd if="$1" bs=16 skip="$STAY_MARK_INDEX" count=1 2>/dev/null | od -An -tx1 | tr -s ' \n' '  ' |
		sed 's/^ *//; s/ *$//'
}

# Só grava se a área estiver zerada ou já com a marca (o contador do Alpine fica em 0x10010).
write_stay_mark() {
	area=$(read_mark_area "$1")
	[ "$area" = "$STAY_MARK_HEX" ] && return 0
	[ "$area" = "$STAY_ZERO_HEX" ] || return 1
	printf 'hy300-ficar\000\001\000\000\000' |
		dd of="$1" bs=16 seek="$STAY_MARK_INDEX" count=1 conv=notrunc,fsync 2>/dev/null || return 1
	[ "$(read_mark_area "$1")" = "$STAY_MARK_HEX" ]
}

wait_interval() {
	remaining=$(($2 - $1))
	[ "$remaining" -gt "$DIAG_INTERVAL" ] && remaining=$DIAG_INTERVAL
	[ "$remaining" -gt 0 ] && sleep "$remaining"
	return 0
}

# Com o boot completo e o adb pela rede no ar, quem conduz é o adb: as coletas param (o dmesg
# como root a cada 20 s deixava o processo em estado D e custava CPU) e o diag só confere, até o
# prazo, se o adb continua de pé. Se cair antes do prazo, as coletas voltam e o retorno ao Alpine
# segue valendo.
is_quiet_mode() {
	[ "$1" = 1 ] && is_network_adb_up
}

main() {
	is_diag_enabled || exit 0
	dir=$(next_boot_dir "$DIAG_ROOT") || exit 1
	prune_old_boots "$DIAG_ROOT" 3
	log_line "$dir" "diag ligado; reinício normal aos $DIAG_REBOOT_AFTER s de uptime"
	if [ "$DIAG_WIFI" = 1 ]; then
		run_wifi_test "$dir" &
	fi
	collected=0
	loops=0
	quiet_logged=0
	while :; do
		loops=$((loops + 1))
		now=$(uptime_seconds)
		if is_quiet_mode "$collected"; then
			[ "$quiet_logged" = 1 ] || log_line "$dir" "adb pela rede no ar: coletas suspensas"
			quiet_logged=1
			if [ "$now" -ge "$DIAG_REBOOT_AFTER" ]; then
				log_line "$dir" "adb pela rede no ar aos $now s: sem reinício automático, diag encerrado"
				exit 0
			fi
			[ "$loops" -ge "$DIAG_MAX_LOOPS" ] && exit 0
			wait_interval "$now" "$DIAG_REBOOT_AFTER"
			continue
		fi
		snapshot "$dir"
		if [ "$collected" = 0 ] && [ "$(getprop sys.boot_completed)" = 1 ]; then
			log_line "$dir" "boot_completed"
			collect_after_boot "$dir"
			collected=1
		fi
		if [ "$now" -ge "$DIAG_REBOOT_AFTER" ] && is_network_adb_up; then
			log_line "$dir" "adb pela rede no ar aos $now s (boot_completed=$collected): sem reinício automático, diag encerrado"
			exit 0
		fi
		if [ "$now" -ge "$DIAG_REBOOT_AFTER" ]; then
			if write_stay_mark "$DIAG_MISC"; then
				log_line "$dir" "marca de ficar gravada na misc"
			else
				log_line "$dir" "marca de ficar NÃO gravada (área da misc ocupada ou sem acesso)"
			fi
			log_line "$dir" "reinício normal (boot_completed=$collected)"
			sync
			setprop sys.powerctl reboot
			exit 0
		fi
		[ "$loops" -ge "$DIAG_MAX_LOOPS" ] && exit 0
		wait_interval "$now" "$DIAG_REBOOT_AFTER"
	done
}

[ "${HY300_DIAG_LIB:-0}" = 1 ] || main
