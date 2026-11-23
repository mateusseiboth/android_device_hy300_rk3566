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
    $(DEVICE_PATH)/configs/init/hy300-alpine.sh:$(TARGET_COPY_OUT_VENDOR)/bin/hy300-alpine.sh \
    $(DEVICE_PATH)/configs/init/init.rk3566.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/hw/init.rk3566.rc \
    $(DEVICE_PATH)/configs/init/ueventd.rk3566.rc:$(TARGET_COPY_OUT_VENDOR)/etc/ueventd.rc

# Controle IR (remotectl no PWM3, dispositivo de entrada "fdd70030.pwm"). As teclas do
# painel (adc-keys) e o botão de energia (gpio-keys) usam o Generic.kl.
PRODUCT_COPY_FILES += \
    $(DEVICE_PATH)/keylayout/fdd70030_pwm.kl:$(TARGET_COPY_OUT_VENDOR)/usr/keylayout/fdd70030_pwm.kl

# zram pelo mmd do Android 17 (system/memory/mmd), não pelo fstab: só assim entra o writeback de
# páginas ociosas para o eMMC, com limite diário. Medido no boot 4 (mm_stat): 78,8 MB de páginas
# ocupando 30,5 MB com a sobra do zsmalloc, razão efetiva 2,58 com lz4. 125 % da RAM (1,81 GB)
# cheio ocuparia ~700 MB, menos da metade da RAM; acima disso o zram disputaria com o que precisa
# ficar descomprimido. lz4 e não zstd: o kernel não tem CONFIG_CRYPTO_ZSTD, e nos quatro A55 o
# zstd custa várias vezes mais CPU por página para ganhar ~25 % de razão.
# Writeback: arquivo de 512 MiB em /data/per_boot/zram, no máximo 256 MiB por dia no eMMC (~90 GB
# por ano), só páginas ociosas há 2 a 4 horas. A manutenção não espera o aparelho ficar ocioso:
# o projetor é desligado da tomada, não fica parado com a tela apagada.
PRODUCT_VENDOR_PROPERTIES += \
    mmd.zram.enabled=true \
    mmd.zram.size=125% \
    mmd.zram.comp_algorithm=lz4 \
    mmd.zram.writeback.enabled=true \
    mmd.zram.writeback.device_size=536870912 \
    mmd.zram.writeback.min_free_space_mib=1536 \
    mmd.zram.writeback.limit.enabled=true \
    mmd.zram.writeback.max_bytes_per_day=268435456 \
    mmd.zram.writeback.min_idle_seconds=7200 \
    mmd.zram.writeback.max_idle_seconds=14400
PRODUCT_PRODUCT_PROPERTIES += \
    mm.zram.maintenance.require_device_idle=false

# Memória (1,5 GB). lmkd por PSI, com limites
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
    $(DEVICE_PATH)/configs/media/media_codecs_c2_rk.xml:$(TARGET_COPY_OUT_VENDOR)/etc/media_codecs_c2_rk.xml \
    $(DEVICE_PATH)/configs/seccomp/android.hardware.media.c2@1.1-extended-seccomp-policy:$(TARGET_COPY_OUT_VENDOR)/etc/seccomp_policy/android.hardware.media.c2@1.1-extended-seccomp-policy

# Entrada por Surface nos encoders (gravação de tela, espelhamento, scrcpy). O HAL do Codec2 da
# Rockchip (HIDL 1.1) não cria InputSurface e o OMX está desligado (TARGET_SUPPORTS_OMX_SERVICE),
# então CCodec::CreateInputSurface devolvia nulo e createInputSurface() derreferia o ponteiro
# (SIGSEGV em libsfplugin_ccodec.so). Com -1 o CCodec cria o GraphicBufferSource (AIDL) no próprio
# processo do app, como no emulador (device/generic/goldfish).
PRODUCT_VENDOR_PROPERTIES += \
    debug.stagefright.c2inputsurface=-1

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

# Fuso padrão do produto (o usuário está em Mato Grosso do Sul).
PRODUCT_PRODUCT_PROPERTIES += \
    persist.sys.timezone=America/Campo_Grande

# Assistente de configuração: o do LineageOS não cabe em 1024x600 (botões fora da tela) e a TV não
# tem toque. O TvProvision do AOSP (device/google/atv) só marca device_provisioned e
# user_setup_complete e se desativa. O hy300-package-overrides (Android.bp) tira da imagem o
# LineageSetupWizard e o Updater (OTA oficial não existe para este aparelho; ele ficava residente
# com ~15 MB).
PRODUCT_PACKAGES += \
    TvProvision \
    hy300-package-overrides

# Google Apps para Android TV (MindTheGapps 17.0.0 arm64 ATV, variante minimal), SÓ NO BUILD
# LOCAL: são proprietários e nunca vão para repositório público. O checkout vem de um
# local_manifest (vendor/gapps_tv, docs/lineageos.md do hy300-rk3566); sem o diretório, ou com
# HY300_WITH_GAPPS=false no ambiente, a imagem sai sem GApps. A minimal não traz o TVLauncher:
# o launcher continua o do LineageOS.
# O SetupWraith (assistente do Google TV) também sai (hy300-gapps-overrides, Android.bp): o
# aparelho já é marcado como configurado pelo TvProvision e a conta Google entra por
# Configurações > Contas e login.
HY300_WITH_GAPPS ?= true
ifeq ($(HY300_WITH_GAPPS),true)
ifneq ($(wildcard vendor/gapps_tv/arm64/arm64-vendor.mk),)
GMS_VARIANT := minimal
$(call inherit-product, vendor/gapps_tv/arm64/arm64-vendor.mk)
PRODUCT_PACKAGES += hy300-gapps-overrides
endif
endif

# Aurora Store (GPLv3, loja do Google Play sem conta Google obrigatória), pré-instalada como app
# comum no /product. O APK da F-Droid fica fora do git: tools/fetch_aurora.py baixa, confere o
# sha256 e gera prebuilt/aurora/Android.bp.
ifneq ($(wildcard $(DEVICE_PATH)/prebuilt/aurora/AuroraStore.apk),)
PRODUCT_PACKAGES += AuroraStore
endif

# Keystone no SurfaceFlinger (patches/frameworks/native/0001): mesma API de props da fábrica
# (persist.sys.keystone.*), aplicada pelo RenderEngine na composição pelo cliente. O .rc dá o
# gatilho de releitura quando as props persist carregam.
PRODUCT_COPY_FILES += \
    $(DEVICE_PATH)/configs/init/hy300-keystone.rc:$(TARGET_COPY_OUT_SYSTEM_EXT)/etc/init/hy300-keystone.rc

# Sensores: HAL AIDL próprio (sensors/) com o acelerômetro do keystone automático do app. O
# backend e o dispositivo vêm das props abaixo; o padrão é o SC7A20 pelo framework "gsensor"
# do kernel Rockchip (GS_SC7A20). Para um driver IIO: backend=iio e device=<nome do IIO>.
PRODUCT_PACKAGES += android.hardware.sensors-service.hy300
PRODUCT_COPY_FILES += \
    frameworks/native/data/etc/android.hardware.sensor.accelerometer.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.sensor.accelerometer.xml
PRODUCT_VENDOR_PROPERTIES += \
    ro.vendor.hy300.accel.backend=rk-gsensor \
    ro.vendor.hy300.accel.device=gsensor \
    ro.vendor.hy300.accel.control=/dev/mma8452_daemon \
    ro.vendor.hy300.accel.axes=x,y,z
