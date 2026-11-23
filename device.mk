#
# SPDX-FileCopyrightText: 2026 Mateus Seiboth
# SPDX-License-Identifier: Apache-2.0
#

DEVICE_PATH := device/txcz/hy300

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
    $(DEVICE_PATH)/configs/init/hy300-clear-bcb.sh:$(TARGET_COPY_OUT_VENDOR)/bin/hy300-clear-bcb.sh \
    $(DEVICE_PATH)/configs/init/hy300-diag.sh:$(TARGET_COPY_OUT_VENDOR)/bin/hy300-diag.sh \
    $(DEVICE_PATH)/configs/init/init.rk3566.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/hw/init.rk3566.rc \
    $(DEVICE_PATH)/configs/init/ueventd.rk3566.rc:$(TARGET_COPY_OUT_VENDOR)/etc/ueventd.rc

# Controle IR (remotectl no PWM3, dispositivo de entrada "fdd70030.pwm"). As teclas do
# painel (adc-keys) e o botão de energia (gpio-keys) usam o Generic.kl.
PRODUCT_COPY_FILES += \
    $(DEVICE_PATH)/keylayout/fdd70030_pwm.kl:$(TARGET_COPY_OUT_VENDOR)/usr/keylayout/fdd70030_pwm.kl

# Memória (1,5 GB): zram de 75 % com lz4 (fstab + init.rk3566.rc). lmkd por PSI, com limites
# que poupam o app em primeiro plano (vídeo): mata cedo os de segundo plano (kill_heaviest_task,
# thrashing_limit baixo) e só fica crítico com stall completo longo. heapsize/growthlimit vêm do
# atv_lowram_defaults.mk.
PRODUCT_VENDOR_PROPERTIES += \
    ro.lmk.use_psi=true \
    ro.lmk.use_minfree_levels=false \
    ro.lmk.kill_heaviest_task=true \
    ro.lmk.psi_partial_stall_ms=200 \
    ro.lmk.psi_complete_stall_ms=700 \
    ro.lmk.thrashing_limit=30 \
    ro.lmk.thrashing_limit_decay=50 \
    ro.lmk.swap_util_max=90 \
    ro.lmk.swap_free_low_percentage=10

# Gráficos abertos: Mesa Panfrost (aospext, ver BoardConfig.mk) + drm_hwcomposer (HWC3) +
# minigbm. O minigbm "generic" usa o driver dumb no nó do rockchip (o ACK libera
# CREATE_DUMB no render node) e o Panfrost importa por dma-buf. Qual GLES usar (Mesa/Panfrost ou
# ANGLE + SwiftShader por software) é decidido no init.rk3566.rc pela androidboot.hy300.gpu:
# ro.hardware.egl, ro.hardware.vulkan e drm.gpu.vendor_name não vão nos build.prop.
$(call soong_config_set,minigbm,platform,generic)
PRODUCT_PACKAGES += \
    android.hardware.composer.hwc3-service.drm \
    android.hardware.graphics.allocator-service.minigbm \
    mapper.minigbm \
    libEGL_mesa \
    libGLESv1_CM_mesa \
    libGLESv2_mesa \
    libgallium_dri
PRODUCT_PACKAGES += vulkan.pastel
PRODUCT_VENDOR_PROPERTIES += \
    ro.opengles.version=196609 \
    debug.renderengine.backend=skiaglthreaded \
    ro.surface_flinger.max_frame_buffer_acquired_buffers=3

# Vídeo por hardware: Codec2 da Rockchip (hardware/rockchip/codec2) sobre o MPP
# (hardware/rockchip/libmpp, kernel mpp_service), com cópia pela RGA (librga) para os buffers do
# minigbm. Tudo compilado do fonte; os patches que a árvore aplica estão em patches/. Os codecs
# de software do AOSP continuam disponíveis (APEX swcodec) para o que o hardware não cobre.
# O Codec2 e a librga ficam em namespaces do Soong: sem eles aqui, os módulos não chegam ao Make
# (e, com ALLOW_MISSING_DEPENDENCIES, sumiriam da imagem sem erro).
PRODUCT_SOONG_NAMESPACES += \
    hardware/rockchip/codec2 \
    hardware/rockchip/librga
PRODUCT_PACKAGES += \
    android.hardware.media.c2@1.1-service \
    libcodec2_rk_component \
    libmpp \
    librga
PRODUCT_COPY_FILES += \
    $(DEVICE_PATH)/configs/media/media_codecs.xml:$(TARGET_COPY_OUT_VENDOR)/etc/media_codecs.xml \
    $(DEVICE_PATH)/configs/media/media_codecs_c2_rk.xml:$(TARGET_COPY_OUT_VENDOR)/etc/media_codecs_c2_rk.xml

# App de configurações do projetor (vendor/hy300/hy300-rk3566/android/hy300-settings, do fonte):
# priv-app com a chave de plataforma; o TvSettings mostra o item "Projetor" para ele.
PRODUCT_PACKAGES += HY300Settings

# Animação de boot com log ao vivo (vendor/hy300/hy300-rk3566/android/bootlog): o serviço bootanim
# vira o bootlog.sh (rc com override no /product), que tenta a versão nativa em C++
# (/system_ext/bin/hy300-bootlog-native, sem ART) e, se ela não desenhar, a Java com o
# bootanimation mostrando o hy300-bootlog.zip (1 quadro, o logo) até o ART subir.
PRODUCT_PACKAGES += \
    hy300-bootlog-native \
    hy300-bootlog \
    hy300-bootlog.rc \
    hy300-bootlog.sh \
    hy300-bootlog-logo.png \
    hy300-bootlog.zip
PRODUCT_PRODUCT_PROPERTIES += \
    ro.product.bootanim.file=hy300-bootlog.zip

# HALs que o system_server do LineageOS 24 não tolera sem (tabela e trechos do framework em
# docs/lineageos.md, conferida no host por tools/check_vintf_hals.py):
#  - Power AIDL: o HintManagerService lê getSupportInfo() sem conferir nulo e derruba o
#    system_server (foi o que aconteceu no primeiro boot). O exemplo do AOSP responde tudo.
#  - Áudio AIDL (core + effect, APEX de exemplo do AOSP): sem ele o audioserver fica sem módulo
#    primário; o exemplo usa o ALSA do card 0 (I2S1).
#  - O serviço de efeitos do APEX procura audio_effects_config.xml no APEX (não está lá) e depois
#    no /vendor/etc; sem o arquivo ele sai, o "onrestart" reinicia o audioserver em laço, e o
#    AudioService trava o system_server (o Watchdog o mata). O exemplo do AOSP instala o arquivo
#    no vendor com esta variável.
#  - Sem audio_policy_configuration.xml o HAL de exemplo não registra nenhum IModule (cria um por
#    módulo do arquivo) e o audioserver espera o IModule/default para sempre; o Watchdog mata o
#    system_server em AudioService.<init> (boot 3). configs/audio tem o módulo primário (só o
#    alto-falante) e inclui do AOSP o r_submix, os volumes e o surround.
$(call soong_config_set_bool,hardware_interfaces_audio,use_default_audio_effects_config,true)
$(call soong_config_set_bool,frameworks_av,use_aosp_audio_policy_volumes,true)
$(call soong_config_set_bool,frameworks_av,use_aosp_default_volume_tables,true)
$(call soong_config_set_bool,frameworks_av,use_aosp_r_submix_audio_policy_configuration,true)
$(call soong_config_set_bool,frameworks_av,use_aosp_surround_sound_configuration_5_0,true)
PRODUCT_PACKAGES += \
    android.hardware.power-service.example \
    com.android.hardware.audio \
    audio_effects_config.xml \
    aosp_audio_policy_volumes.xml \
    aosp_default_volume_tables.xml \
    aosp_r_submix_audio_policy_configuration.xml \
    aosp_surround_sound_configuration_5_0.xml
PRODUCT_COPY_FILES += \
    $(DEVICE_PATH)/configs/audio/audio_policy_configuration.xml:$(TARGET_COPY_OUT_VENDOR)/etc/audio_policy_configuration.xml \
    $(DEVICE_PATH)/configs/audio/hy300_primary_audio_policy_configuration.xml:$(TARGET_COPY_OUT_VENDOR)/etc/hy300_primary_audio_policy_configuration.xml

# Segurança e sistema por software (a fábrica usa OP-TEE com TA fechada). KeyMint é preciso
# para o FBE do /data.
PRODUCT_PACKAGES += \
    android.hardware.security.keymint-service \
    com.android.hardware.gatekeeper.nonsecure \
    android.hardware.health-service.example \
    android.hardware.health-service.example_recovery

# Wi-Fi AIC8800: módulos em prebuilt/modules (BOARD_VENDOR_KERNEL_MODULES), carregados no boot
# pelo hy300-wifi-modules.sh com as funções do initramfs de teste (hy300-wifi.sh, do repositório do
# projeto). O firmware da AICSemi é binário de fábrica: entra só no build local, de
# prebuilt/firmware/aic8800 (fora do git, extraído do vendor.img de fábrica pelo
# kernel/build-lineage-kernel.sh).
# Pilha do Android sem HAL Wi-Fi do fabricante: o framework funciona sem ela (WifiNative usa o
# wificond e pega a interface de wifi.interface quando isVendorHalSupported() é falso), e o HAL
# AIDL padrão do AOSP só sobe com uma libwifi-hal do fabricante (a libwifi-hal-fallback devolve
# WIFI_ERROR_NOT_SUPPORTED no init_wifi_vendor_hal_func_table). wpa_supplicant AIDL do AOSP com
# nl80211 (BoardConfig.mk).
PRODUCT_PACKAGES += \
    hy300-wifi.sh \
    wpa_supplicant
PRODUCT_PACKAGES_DEBUG += iw
PRODUCT_COPY_FILES += \
    $(foreach f,$(wildcard $(DEVICE_PATH)/prebuilt/firmware/aic8800/*),$(f):$(TARGET_COPY_OUT_VENDOR)/etc/firmware/aic8800/$(notdir $(f))) \
    $(DEVICE_PATH)/configs/init/hy300-wifi-modules.sh:$(TARGET_COPY_OUT_VENDOR)/bin/hy300-wifi-modules.sh \
    $(DEVICE_PATH)/configs/init/hy300-net.sh:$(TARGET_COPY_OUT_VENDOR)/bin/hy300-net.sh \
    $(DEVICE_PATH)/configs/wifi/wpa_supplicant.conf:$(TARGET_COPY_OUT_VENDOR)/etc/wifi/wpa_supplicant.conf \
    frameworks/native/data/etc/android.hardware.wifi.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.wifi.xml
PRODUCT_VENDOR_PROPERTIES += wifi.interface=wlan0

# Rede cabeada por adaptador USB, além do Wi-Fi.
PRODUCT_COPY_FILES += \
    frameworks/native/data/etc/android.hardware.ethernet.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.ethernet.xml

# TODO(marcos seguintes, ver docs/lineageos.md):
#  - áudio: HAL AIDL de referência com tinyalsa no card 0 (I2S1, codec mudo);
#  - Bluetooth (UART ttyS1, HAL AIDL padrão);
#  - sensores: acelerômetro SC7A20 (keystone automático do app);
#  - patch de keystone no SurfaceFlinger (o app já grava as props persist.sys.keystone.*).
