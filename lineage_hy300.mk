#
# SPDX-FileCopyrightText: 2026 Mateus Seiboth
# SPDX-License-Identifier: Apache-2.0
#

# Produto Android TV (Leanback), do mesmo jeito que os aparelhos ATV do LineageOS:
# atv_base.mk (AOSP) + common_full_tv.mk (LineageOS, que puxa device/lineage/atv e o
# TvSettingsTwoPanel). PRODUCT_IS_ATV é lido pelo vendor/lineage.
PRODUCT_IS_ATV := true

# Sem os HALs HIDL de CAS e OMX que o base_vendor.mk põe para shipping API <= 33: o FCM 8 do
# manifesto declara o CAS HIDL obsoleto (check_vintf recusa), e o vídeo é Codec2. Têm de vir antes
# dos inherit-product.
TARGET_REQUIRES_HIDL_CAS_HAL := false
TARGET_SUPPORTS_OMX_SERVICE := false

# Memória baixa (1,5 GB): perfis de boot e lowram do ATV. Tem que vir antes do device.mk
# para que os valores do aparelho possam sobrescrever.
$(call inherit-product, device/google/atv/products/atv_lowram_defaults.mk)

$(call inherit-product, device/google/atv/products/atv_base.mk)
$(call inherit-product, vendor/lineage/config/common_full_tv.mk)
$(call inherit-product, device/txcz/hy300/device.mk)

PRODUCT_NAME := lineage_hy300
PRODUCT_DEVICE := hy300
PRODUCT_BRAND := HY300
PRODUCT_MODEL := HY300 Projector
PRODUCT_MANUFACTURER := TXCZ

PRODUCT_SYSTEM_NAME := hy300
PRODUCT_SYSTEM_DEVICE := hy300
