#
# SPDX-FileCopyrightText: 2026 Mateus Seiboth
# SPDX-License-Identifier: Apache-2.0
#

DEVICE_PATH := device/hy300/rk3566

# Só 64 bits: um zygote só (zygote64) cabe melhor em 1,5 GB que o par 64/32.
$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit_only.mk)

# A fábrica saiu com Android 12 (ro.product.first_api_level=31).
PRODUCT_SHIPPING_API_LEVEL := 31

# Kernel não-GKI (ACK android14-6.1 com o BSP Rockchip, prebuilt): o .config atende o
# kernel/configs/u/android-6.1, mas o build não tem o .config do prebuilt para conferir.
PRODUCT_OTA_ENFORCE_VINTF_KERNEL_REQUIREMENTS := false

PRODUCT_USE_DYNAMIC_PARTITIONS := true
PRODUCT_CHARACTERISTICS := tv
PRODUCT_AAPT_CONFIG := normal mdpi hdpi
PRODUCT_AAPT_PREF_CONFIG := mdpi

PRODUCT_SOONG_NAMESPACES += $(DEVICE_PATH)

# fstab: ramdisk do boot (primeiro estágio; header v2 não tem vendor_boot) e vendor.
PRODUCT_COPY_FILES += \
    $(DEVICE_PATH)/configs/init/fstab.rk3566:$(TARGET_COPY_OUT_RAMDISK)/fstab.rk3566 \
    $(DEVICE_PATH)/configs/init/fstab.rk3566:$(TARGET_COPY_OUT_VENDOR)/etc/fstab.rk3566

# init e ueventd
PRODUCT_COPY_FILES += \
    $(DEVICE_PATH)/configs/init/init.rk3566.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/hw/init.rk3566.rc \
    $(DEVICE_PATH)/configs/init/ueventd.rk3566.rc:$(TARGET_COPY_OUT_VENDOR)/etc/ueventd.rc

# Controle IR (remotectl no PWM3, dispositivo de entrada "fdd70030.pwm"). As teclas do
# painel (adc-keys) e o botão de energia (gpio-keys) usam o Generic.kl.
PRODUCT_COPY_FILES += \
    $(DEVICE_PATH)/keylayout/fdd70030_pwm.kl:$(TARGET_COPY_OUT_VENDOR)/usr/keylayout/fdd70030_pwm.kl

# Memória: zram vem do fstab (swapon_all no init.rk3566.rc). heapsize/growthlimit e lmkd
# vêm do atv_lowram_defaults.mk (go_defaults_common.prop), os mesmos valores da fábrica.
PRODUCT_VENDOR_PROPERTIES += \
    ro.lmk.use_psi=true \
    ro.lmk.swap_free_low_percentage=20

# Gráficos abertos (Mesa Panfrost + drm_hwcomposer + minigbm). Nomes conferidos nos
# Android.bp do android-17.0.0_r1. O Mesa com Panfrost não é compilado pelo
# external/mesa3d do AOSP 17 (só gfxstream): entra pelo aospext do GloDroid num marco
# próprio (local_manifest), e só então estes pacotes passam a ter sentido.
$(call soong_config_set,minigbm,platform,generic)
PRODUCT_PACKAGES += \
    android.hardware.composer.hwc3-service.drm \
    android.hardware.graphics.allocator-service.minigbm \
    mapper.minigbm
PRODUCT_VENDOR_PROPERTIES += \
    ro.hardware.hwcomposer=drm \
    ro.hardware.gralloc=minigbm \
    ro.opengles.version=196610
# TODO(marco gráficos): libs do Mesa via aospext e ro.hardware.egl=mesa,
# ro.hardware.vulkan=panfrost.

# TODO(marcos seguintes, ver docs/lineageos.md):
#  - áudio: HAL AIDL de referência com tinyalsa no card 0 (I2S1, codec mudo);
#  - Bluetooth: AIC8800 por UART (ttyS1, 1,5 Mbaud), HAL AIDL padrão em cima do hci_uart;
#  - KeyMint/Gatekeeper por software (a fábrica usa OP-TEE com TA fechada);
#  - sensores: acelerômetro SC7A20 (keystone automático do app);
#  - app io.github.hy300.settings como app de plataforma (android_app_import, certificate
#    "platform") e o patch de keystone no SurfaceFlinger.
