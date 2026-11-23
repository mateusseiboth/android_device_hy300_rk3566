#
# SPDX-FileCopyrightText: 2026 Mateus Seiboth
# SPDX-License-Identifier: Apache-2.0
#
# resource.img (formato RSCE da Rockchip) na seção "second" do boot.img e do recovery.img:
# o mkbootimg recebe --second de $(INSTALLED_2NDBOOTLOADER_TARGET) quando
# TARGET_BOOTLOADER_IS_2ND=true.
#
# O conteúdo é fixo: logo do U-Boot e o rk-kernel.dtb DE FÁBRICA, que o U-Boot usa como DT
# próprio (com o DT do 6.1 ele trava antes do logo). O kernel usa o DT embutido. Por isso
# não se reempacota o resource em volta do DTB do build, ao contrário de outras árvores
# Rockchip. O arquivo vem do boot.img do próprio aparelho (prebuilt/README.md) e não vai
# para o git.
#
# Fica em build/tasks porque INSTALLED_2NDBOOTLOADER_TARGET ainda não existe quando os
# Android.mk são lidos.
ifeq ($(TARGET_DEVICE),hy300)
HY300_RESOURCE_IMG := device/txcz/hy300/prebuilt/resource.img

$(INSTALLED_2NDBOOTLOADER_TARGET): $(HY300_RESOURCE_IMG)
	$(hide) mkdir -p $(dir $@)
	$(hide) cp $< $@
endif
