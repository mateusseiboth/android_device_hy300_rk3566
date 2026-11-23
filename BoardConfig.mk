#
# SPDX-FileCopyrightText: 2026 Mateus Seiboth
# SPDX-License-Identifier: Apache-2.0
#
# HY300 (RK3566, TXCZ y356tx). Tamanhos e offsets tirados do aparelho: GPT em
# ~/hy300-backup/gpt_head.bin, metadado da super em super.img.gz (lpdump), header do
# boot.img de fábrica. Ver docs/lineageos.md no repositório do projeto.
#

DEVICE_PATH := device/txcz/hy300

# Arquitetura: só 64 bits (core_64_bit_only.mk no device.mk). A55 x4.
TARGET_ARCH := arm64
TARGET_ARCH_VARIANT := armv8-2a
TARGET_CPU_ABI := arm64-v8a
TARGET_CPU_VARIANT := cortex-a55

TARGET_BOARD_PLATFORM := rk356x
TARGET_BOOTLOADER_BOARD_NAME := rk30board
TARGET_NO_BOOTLOADER := false

# Kernel: prebuilt do nosso build, copiado para prebuilt/ por fora; o arquivo não vai para o
# git. Fonte: branch hy300-ack-6.1 do kernel-hy300-rk3566 (kernel Android da Rockchip: ACK
# android14-6.1 + BSP develop-6.1, 6.1.172), rockchip_defconfig + android-14.config +
# rk3566_hy300.config, clang-r547379 (KBASE=ack no kernel/build-marco1.sh do projeto).
# Comprimido porque a partição boot tem 40 MiB e a Image crua tem 34,9 MiB (gzip -9:
# 15,2 MB); somada ao ramdisk e ao resource ela não cabe. O U-Boot de fábrica tem código de
# gzip e lz4 no bootm (strings do uboot.img), mas isso só vale depois de testado no slot
# recovery.
TARGET_NO_KERNEL := false
TARGET_PREBUILT_KERNEL := $(DEVICE_PATH)/prebuilt/Image.gz
BOARD_KERNEL_IMAGE_NAME := Image.gz

# boot.img header v2, igual à fábrica: sem vendor_boot (só existe com header >= 3).
# Endereços iguais aos do boot.img de fábrica (base 0x10000000).
BOARD_BOOT_HEADER_VERSION := 2
BOARD_KERNEL_BASE := 0x10000000
BOARD_KERNEL_PAGESIZE := 2048
BOARD_KERNEL_OFFSET := 0x00008000
BOARD_RAMDISK_OFFSET := 0x01000000
BOARD_KERNEL_SECOND_OFFSET := 0x00f00000
BOARD_KERNEL_TAGS_OFFSET := 0x00000100
BOARD_DTB_OFFSET := 0x01f00000
BOARD_MKBOOTIMG_ARGS += --header_version $(BOARD_BOOT_HEADER_VERSION)
BOARD_MKBOOTIMG_ARGS += --kernel_offset $(BOARD_KERNEL_OFFSET)
BOARD_MKBOOTIMG_ARGS += --ramdisk_offset $(BOARD_RAMDISK_OFFSET)
BOARD_MKBOOTIMG_ARGS += --second_offset $(BOARD_KERNEL_SECOND_OFFSET)
BOARD_MKBOOTIMG_ARGS += --tags_offset $(BOARD_KERNEL_TAGS_OFFSET)
BOARD_MKBOOTIMG_ARGS += --dtb_offset $(BOARD_DTB_OFFSET)
BOARD_MKBOOTIMG_ARGS += --pagesize $(BOARD_KERNEL_PAGESIZE)

# O U-Boot confere o SHA-1 do header; o mkbootimg do Lineage calcula diferente.
BOARD_CUSTOM_MKBOOTIMG := $(DEVICE_PATH)/tools/mkbootimg_hy300.py

# Seção "second" = resource.img (logo + rk-kernel.dtb de FÁBRICA, que é o que o U-Boot
# usa como DT próprio). O kernel ignora esse DT e usa o embutido (CONFIG_HY300_BUILTIN_DTB).
# build/tasks/resource_img.mk copia prebuilt/resource.img para o 2ndbootloader.
TARGET_BOOTLOADER_IS_2ND := true

# Seção dtb do header v2: o U-Boot não usa, mas o mkbootimg exige com header v2.
BOARD_INCLUDE_DTB_IN_BOOTIMG := true
BOARD_PREBUILT_DTBIMAGE_DIR := $(DEVICE_PATH)/prebuilt/dtb

# A dtbo de fábrica fica como está (o U-Boot aplica no DT de fábrica).
BOARD_KERNEL_SEPARATED_DTBO := false

# boot_devices: na base Android (hy300-ack-6.1) o nó do eMMC é sdhci@fe310000, o mesmo nome
# do 4.19 de fábrica (no BSP Linux hy300-6.1 era mmc@fe310000).
# A cmdline vem inteira do boot.img (o U-Boot só acrescenta mode, serialno,
# verifiedbootstate, dtb_idx e earlycon). SELinux permissive até a política existir.
BOARD_KERNEL_CMDLINE := console=ttyFIQ0 firmware_class.path=/vendor/etc/firmware init=/init
BOARD_KERNEL_CMDLINE += rootwait ro loop.max_part=7 printk.devkmsg=on
BOARD_KERNEL_CMDLINE += androidboot.console=ttyFIQ0 androidboot.hardware=rk3566
BOARD_KERNEL_CMDLINE += androidboot.boot_devices=fe310000.sdhci
BOARD_KERNEL_CMDLINE += androidboot.selinux=permissive
# Nunca parar: panic reinicia em 5 s (também é o CONFIG_PANIC_TIMEOUT do kernel) e erro fatal do
# init vira panic do kernel. O init_fatal_reboot_target não é usado (o init lê o valor com bug de
# sizeof); com panic o reboot é normal e o U-Boot sobe a boot (o Alpine).
BOARD_KERNEL_CMDLINE += panic=5 androidboot.init_fatal_panic=true
# Imagem de teste do primeiro boot: liga o hy300-diag (logs no /metadata e reinício normal aos
# 8 min, de volta ao Alpine, se o adb pela rede não subir). O perfil "uso" desliga.
BOARD_KERNEL_CMDLINE += androidboot.hy300.diag=1
# GPU: "panfrost" (Mesa). As travadas dos primeiros boots vinham de uma tempestade de IRQ do
# GPIO da tecla Home no DT (corrigido no kernel 1ee24ab83ac1). O boot-sw.img troca para "sw"
# (ANGLE + SwiftShader, sem panfrost.ko) como reserva (tools/lineage_prebuilt.py variant).
BOARD_KERNEL_CMDLINE += androidboot.hy300.gpu=panfrost
# Perfil: "teste" (diag ligado e adb pela rede ligado sozinho, como nas rodadas 1 a 6) ou "uso"
# (sem diag; o adb pela rede fica desligado até o usuário ligar nas Opções do desenvolvedor). A
# imagem de uso é o mesmo build com o boot.img trocado por tools/lineage_prebuilt.py variant
# --set androidboot.hy300.perfil=uso (configs/init/hy300-diag.sh e hy300-net.sh leem a prop).
BOARD_KERNEL_CMDLINE += androidboot.hy300.perfil=teste

# Partições físicas (GPT de fábrica; o eMMC não é reparticionado).
BOARD_FLASH_BLOCK_SIZE := 131072
BOARD_BOOTIMAGE_PARTITION_SIZE := 41943040            # boot      40 MiB
BOARD_RECOVERYIMAGE_PARTITION_SIZE := 113246208       # recovery 108 MiB
BOARD_CACHEIMAGE_PARTITION_SIZE := 402653184          # cache    384 MiB
BOARD_CACHEIMAGE_FILE_SYSTEM_TYPE := ext4
BOARD_USERDATAIMAGE_PARTITION_SIZE := 3495919616      # userdata 3334 MiB
BOARD_USERDATAIMAGE_FILE_SYSTEM_TYPE := ext4
BOARD_USES_METADATA_PARTITION := true                 # metadata  16 MiB

# Partições dinâmicas: super de 3.263.168.512 bytes, grupo com 4 MiB a menos (igual à
# fábrica). Sem A/B, sem vendor_dlkm/odm_dlkm: os módulos vão no vendor.
BOARD_SUPER_PARTITION_SIZE := 3263168512
BOARD_SUPER_PARTITION_GROUPS := rockchip_dynamic_partitions
BOARD_ROCKCHIP_DYNAMIC_PARTITIONS_SIZE := 3258974208
BOARD_ROCKCHIP_DYNAMIC_PARTITIONS_PARTITION_LIST := system system_ext product vendor odm
AB_OTA_UPDATER := false
# super.img (sparse) no próprio `m`, para gravar pelo Alpine (simg2img antes do dd).
BOARD_BUILD_SUPER_IMAGE_BY_DEFAULT := true

BOARD_SYSTEMIMAGE_FILE_SYSTEM_TYPE := ext4
BOARD_SYSTEM_EXTIMAGE_FILE_SYSTEM_TYPE := ext4
BOARD_PRODUCTIMAGE_FILE_SYSTEM_TYPE := ext4
BOARD_VENDORIMAGE_FILE_SYSTEM_TYPE := ext4
BOARD_ODMIMAGE_FILE_SYSTEM_TYPE := ext4
TARGET_COPY_OUT_SYSTEM_EXT := system_ext
TARGET_COPY_OUT_PRODUCT := product
TARGET_COPY_OUT_VENDOR := vendor
TARGET_COPY_OUT_ODM := odm
TARGET_USERIMAGES_USE_EXT4 := true
TARGET_USES_MKE2FS := true

# Sem AVB: o U-Boot de fábrica não confere (verifiedbootstate=orange, vbmeta intocada).
BOARD_AVB_ENABLE := false

# Recovery do Lineage, com o mesmo fstab.
TARGET_RECOVERY_FSTAB := $(DEVICE_PATH)/configs/init/fstab.rk3566
TARGET_RECOVERY_PIXEL_FORMAT := RGBX_8888

# Tela: painel LVDS 1024x600 renderizado nativo. 170 dpi dá ~963x564 dp, o mínimo de
# 960x540 dp que as telas Leanback esperam. Confirmar visualmente.
TARGET_SCREEN_DENSITY := 170

# VINTF: o kernel 6.1 só é aceito pela matriz de FCM nível 8 (Android 14) no Android 17.
DEVICE_MANIFEST_FILE := $(DEVICE_PATH)/configs/vintf/manifest.xml

# Wi-Fi AIC8800 por nl80211, wpa_supplicant do AOSP. O BOARD_WLAN_DEVICE (que escolhe a
# libwifi-hal) fica para quando o driver portado estiver no aparelho: a libwifi-hal-aic
# de fábrica é fechada e 32 bits.
WPA_SUPPLICANT_VERSION := VER_0_8_X
BOARD_WPA_SUPPLICANT_DRIVER := NL80211
BOARD_HOSTAPD_DRIVER := NL80211
WIFI_DRIVER_SOCKET_IFACE := wlan0
# O .rc do wpa_supplicant AIDL (com a "interface" do ISupplicant) só é instalado com isto.
WIFI_HIDL_UNIFIED_SUPPLICANT_SERVICE_RC_ENTRY := true

# Módulos do kernel no /vendor/lib/modules (prebuilt/modules, gerados junto com a Image pelo
# kernel/build-lineage-kernel.sh do projeto). Hoje: Panfrost e dependências (a GPU é módulo no
# hy300-ack-6.1). O init.rk3566.rc carrega antes do composer.
BOARD_VENDOR_KERNEL_MODULES := $(sort $(wildcard $(DEVICE_PATH)/prebuilt/modules/*.ko))

# Gráficos: Mesa com Panfrost (Mali-G52), compilado com meson pelo aospext do GloDroid
# (vendor/glodroid/aospext, local_manifest) a partir do external/mesa3d do próprio AOSP 17
# (Mesa 26.1). O Android.bp do external/mesa3d só monta o gfxstream, por isso o aospext.
# O Panfrost do Mesa 26 tem kernels OpenCL pré-compilados (libpan): mesa_clc, vtn_bindgen2 e
# panfrost_compile vêm do host, compilados da MESMA fonte pelo tools/build-mesa-host-tools.sh
# (o PATH do build precisa deles; ver README.md).
BOARD_BUILD_AOSPEXT_MESA3D := true
BOARD_MESA3D_SRC_DIR := external/mesa3d
BOARD_MESA3D_GALLIUM_DRIVERS := panfrost
BOARD_MESA3D_VULKAN_DRIVERS :=
BOARD_MESA3D_EXTRA_MESON_ARGS := -Dmesa-clc=system -Dprecomp-compiler=system \
    -Doptimization=2 -Db_ndebug=true

# SELinux: começa permissive (cmdline). A política própria (sysfs do motor e dos LEDs,
# props persist.sys.keystone.* e persist.txcz.*) entra num marco próprio.
