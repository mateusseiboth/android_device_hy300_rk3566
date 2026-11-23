# device/txcz/hy300: LineageOS 24.0 (Android 17) para o projetor HY300

Árvore de dispositivo do HY300 (Rockchip RK3566, 1,5 GB de RAM, painel LVDS 1024x600, TXCZ
y356tx): LineageOS para TV, 64 bits, low-RAM, FCM 8, GPU aberta (Mesa Panfrost + drm_hwcomposer +
minigbm) e vídeo por hardware (Codec2 da Rockchip sobre o MPP). O plano, o inventário do aparelho,
como gravar e os riscos estão em `docs/lineageos.md` do repositório do projeto (`hy300-rk3566`).
Aqui fica só o porquê de cada arquivo.

Nenhum binário proprietário entra neste repositório. `prebuilt/` é ignorado pelo git.

## Como compilar

O caminho é `device/txcz/hy300` (o build procura o `BoardConfig.mk` em
`device/*/<PRODUCT_DEVICE>`; link simbólico não serve, o finder do Soong não segue). Os projetos
de fora vêm do local_manifest do projeto (`hy300.xml`: esta árvore, o repositório do projeto
`hy300-rk3566` em `vendor/hy300/hy300-rk3566` com o app de configurações e a animação de boot,
aospext, codec2, libmpp, librga, libhardware_rockchip). `hy300-prune.xml` tira do checkout o
que o HY300 não usa (CTS, Qualcomm, Cuttlefish, carro) para a análise do Soong caber em 31 GB.

```sh
cd ~/android/lineage
repo sync -c device/txcz/hy300 vendor/hy300/hy300-rk3566 vendor/glodroid/aospext hardware/rockchip/codec2 \
    hardware/rockchip/libmpp hardware/rockchip/librga hardware/rockchip/libhardware_rockchip
device/txcz/hy300/tools/apply_patches.py .            # patches/ nos projetos de fora
device/txcz/hy300/tools/build-mesa-host-tools.sh .    # mesa_clc e panfrost_compile (host)
export PATH="$HOME/hy300-work/mesa-host/install/bin:$PATH"
export ALLOW_MISSING_DEPENDENCIES=true GOMEMLIMIT=20GiB SOONG_INCREMENTAL_ANALYSIS=false
# prebuilt/: kernel/build-lineage-kernel.sh do repositório do projeto (ver abaixo)
source build/envsetup.sh
lunch lineage_hy300-cp2a-userdebug                    # = breakfast hy300
m -j12
python3 -I -m unittest discover -s device/txcz/hy300/tools/tests
```

## Arquivos

| Arquivo | O que é | Decisão |
|---|---|---|
| `AndroidProducts.mk` | lista de produtos | um produto só, `lineage_hy300`; a release `cp2a` vem de `vendor/lineage/vars/aosp_target_release` |
| `lineage_hy300.mk` | produto | Android TV do LineageOS: `atv_base.mk` + `common_full_tv.mk` (que traz `device/lineage/atv`, TvSettingsTwoPanel, LeanbackIME e o launcher Catapult), mais `atv_lowram_defaults.mk` para 1,5 GB. Mesmo esquema dos aparelhos ATV do Lineage |
| `device.mk` | pacotes, cópias, props | só 64 bits (`core_64_bit_only.mk`, um zygote); `PRODUCT_SHIPPING_API_LEVEL := 31` (Android 12 de fábrica); gráficos abertos, Codec2/MPP, KeyMint/Gatekeeper/health por software, lmkd |
| `BoardConfig.mk` | placa | ver "Boot" e "Partições" |
| `configs/init/fstab.rk3566` | fstab | derivado do `fstab.rk30board` de fábrica (diferenças no topo do arquivo) |
| `configs/init/init.rk3566.rc` | init da placa | `mount_all`, zram, permissões do motor de foco (`/sys/class/motor_cc`) e dos LEDs para o app de configurações (uid system) |
| `configs/init/ueventd.rk3566.rc` | nós de `/dev` | UART do Bluetooth, vendor storage, MPP, RGA, V4L2 da entrada HDMI |
| `configs/vintf/manifest.xml` | manifesto VINTF | `target-level="8"`: no Android 17 o kernel 6.1 só é aceito pela matriz de nível 8 |
| `keylayout/fdd70030_pwm.kl` | controle IR | escrito a partir das tabelas IR do DT do 6.1; F6 = entrada HDMI, F12 = configurações do projetor |
| `build/tasks/resource_img.mk` | resource.img | copia `prebuilt/resource.img` para a seção `second` |
| `tools/mkbootimg_hy300.py` | wrapper do mkbootimg | recalcula o ID SHA-1 que o U-Boot confere (testes em `tools/tests/`) |
| `tools/apply_patches.py` | patches nos projetos de fora | `patches/<caminho>/NNNN-*.patch` com `git apply`; idempotente; rodar depois de cada `repo sync` |
| `tools/build-mesa-host-tools.sh` | ferramentas de host do Mesa | `mesa_clc`, `vtn_bindgen2` e `panfrost_compile` da mesma fonte do `external/mesa3d`, com LLVM 22 |
| `configs/media/` | lista de codecs | `c2.rk.*` (H.264, HEVC, VP9, VP8, MPEG-2, MPEG-4, H.263) até 1920x1088 |
| `patches/hardware/rockchip/codec2` | Codec2 da Rockchip | sem blobs do vendor e sem NPU (0001); gralloc genérico: decodifica nos buffers do MPP e copia pela RGA para NV12 do minigbm (0002) |
| `patches/hardware/rockchip/librga` | librga | compilada do fonte, só a API por fd (no Lineage-Rockchip ela vem dos blobs) |

## Gráficos

- **Mesa 26.1 do próprio `external/mesa3d`** compilado com meson pelo aospext do GloDroid
  (`BOARD_BUILD_AOSPEXT_MESA3D`), só o driver `panfrost`. O `Android.bp` do Mesa no AOSP 17 só
  monta o gfxstream. `drm.gpu.vendor_name=panfrost` faz o EGL abrir o nó do Panfrost.
- **Panfrost é módulo** no kernel (`prebuilt/modules`): o `init.rk3566.rc` carrega no
  `early-init`, antes do allocator e do composer.
- **minigbm "generic"** sem patch: o rockchip é driver dumb no minigbm, e o kernel Android
  permite `CREATE_DUMB` no render node. O Panfrost importa os buffers por dma-buf.
- **drm_hwcomposer** (HWC3) do AOSP, no `card0` (VOP2, LVDS).

## Vídeo por hardware

Codec2 da Rockchip (`android.hardware.media.c2@1.1-service`, componentes `c2.rk.*`) sobre o MPP
do fonte (`/dev/mpp_service`). O gralloc é o minigbm, que não aceita o stride, os formatos e os
bits de uso privados da Rockchip; por isso (patch 0002) o decoder trabalha sempre em "buffer
mode": o MPP decodifica nos buffers dele e cada quadro é copiado pela RGA para um bloco NV12 comum.
Custa uma cópia por quadro na RGA, irrelevante em 1080p. Sem 10 bits por enquanto (HEVC Main10,
VP9 perfil 2 vão para software) e sem encoders.

## App de configurações e animação de boot

Os dois vêm do repositório do projeto (`vendor/hy300/hy300-rk3566`), compilados do fonte pelos
`Android.bp` de lá: `HY300Settings` (priv-app no `/product`, chave de plataforma; o TvSettings
mostra o item "Projetor" porque o app trata `com.android.tv.settings.SOUND`) e `hy300-bootlog`
(o serviço `bootanim` vira o terminal com o logcat ao vivo; `ro.product.bootanim.file` escolhe o
zip de 1 quadro com o logo). O `init.rk3566.rc` dá ao app o motor de foco e os LEDs (0666, como a
fábrica).

## Wi-Fi, áudio e adb pela rede

- **Wi-Fi**: módulos do AIC8800 carregados no `boot` (`configs/init/hy300-wifi-modules.sh`),
  firmware só no build local, `wpa_supplicant` AIDL do AOSP e `wificond`, sem HAL Wi-Fi do
  fabricante (o framework usa `wifi.interface`).
- **Áudio**: APEX de exemplo do AOSP com `configs/audio/audio_policy_configuration.xml` (o HAL
  registra um `IModule` por módulo desse arquivo).
- **Userdebug**: `configs/init/hy300-net.sh` instala a chave do adb e conecta o Wi-Fi a partir de
  `/metadata/hy300-diag/{adb_keys,wifi.conf}` (gravados pelo Alpine; formato em
  `docs/lineageos.md` do projeto) e liga o adb pela rede na porta 5555, com autenticação.
- `tools/check_vintf_hals.py`: HALs obrigatórios e uma `interface` no init para cada HAL
  declarado.

## Desempenho e memória

- `init.rk3566.rc`: CPU no governador `performance` (vale quando o kernel tiver cpufreq), GPU
  (devfreq do Panfrost) e DDR (`dmc`) em `performance`; o térmico do kernel limita por cima.
- lmkd por PSI com limites que poupam o app em primeiro plano (`device.mk`); zram 75 % lz4.



## Boot

- **boot.img header v2**, como a fábrica. Com header v2 o build não gera `vendor_boot`
  (`core/board_config.mk`: só com header >= 3). O ramdisk do boot é o do primeiro estágio, e
  o `fstab.rk3566` vai nele.
- **ID do header**: o U-Boot de fábrica recusa a imagem se o campo `id` não for o SHA-1 de
  cada seção mais o tamanho dela. O mkbootimg do Lineage soma 4 bytes a mais (patch do
  `--dt`). `tools/mkbootimg_hy300.py` (`BOARD_CUSTOM_MKBOOTIMG`) roda o mkbootimg real e
  regrava o ID. O teste confere o algoritmo contra o `boot.img` de fábrica.
- **resource.img** na seção `second`, com o DT **de fábrica**: o U-Boot usa esse DT para ele
  mesmo e trava com o do 6.1. O kernel ignora esse DT e usa o embutido
  (`CONFIG_HY300_BUILTIN_DTB`). Por isso o resource é fixo e não é reempacotado no build.
- **Kernel comprimido** (`Image.gz`): a partição `boot` tem 40 MiB e a `Image` do 6.1 tem
  34,9 MiB (base Android `hy300-ack-6.1`; `gzip -9`: 15,2 MB). O U-Boot tem gzip/lz4 no `bootm`; falta confirmar no slot `recovery`.
- **cmdline**: vem toda do boot.img. `androidboot.hardware=rk3566` (dá nome ao `fstab` e ao
  `init.rk3566.rc`); `androidboot.boot_devices=fe310000.sdhci`, que é o nome do eMMC na base
  Android do kernel (`hy300-ack-6.1`), igual ao 4.19 de fábrica (no BSP Linux era
  `fe310000.mmc`).
- Sem AVB e sem dtbo própria: a `vbmeta` e a `dtbo` de fábrica ficam intocadas.

## Partições

Todas tiradas do aparelho (GPT e metadado da `super`). Nada é reparticionado.

| Partição | Tamanho | Uso no Lineage |
|---|---|---|
| boot | 40 MiB | boot.img v2 |
| recovery | 108 MiB | recovery do Lineage; antes disso, o slot de teste |
| cache | 384 MiB | /cache (OTA sem A/B) |
| metadata | 16 MiB | /metadata |
| super | 3.263.168.512 bytes | grupo `rockchip_dynamic_partitions` com 4 MiB a menos, igual à fábrica: system, system_ext, product, vendor, odm |
| userdata | 3334 MiB | /data, FBE v2 |
| uboot, trust, misc, dtbo, vbmeta, security, baseparameter, backup, cust | | intocadas |

Sem A/B (a fábrica não é A/B). Sem `vendor_dlkm`/`odm_dlkm`: os módulos vão no vendor.

## prebuilt/ (fora do git)

Gerado por `kernel/build-lineage-kernel.sh` do repositório do projeto (`hy300-rk3566`): compila
um commit fixo do `hy300-ack-6.1` a partir de um `git archive`, confere os requisitos do FCM 8 e
instala aqui. `prebuilt/VERSION` guarda o commit e os sha256.

| Arquivo | O que é |
|---|---|
| `Image.gz` | kernel com o DT do HY300 embutido, `gzip -9` reproduzível |
| `dtb/rk3566-hy300.dtb` | seção dtb do header v2 (o mkbootimg exige; o U-Boot não usa) |
| `resource.img` | seção `second` do `boot.img` de fábrica (logo + `rk-kernel.dtb` de fábrica) |
| `modules/*.ko` | `drm_shmem_helper`, `gpu-sched`, `panfrost` |

## Estado

Só conta como visto no aparelho o que está nos logs dos boots 1 a 3 (detalhes em
`docs/lineageos.md` do projeto).

**Feito e visto no aparelho**

- Primeiro boot pelo Alpine, com o ciclo do diag e a volta automática ao Alpine.
- Kernel ACK com o DT corrigido, sem tempestade de IRQ.
- Display e bootlog nativo.
- GPU Panfrost sem erro.
- Driver Wi-Fi AIC8800, com scan.
- Shutdown e reboot.

**Feito, sem verificação no aparelho**

- App de configurações como priv-app com a chave de plataforma.
- Vídeo por hardware (Codec2 + MPP).

**Falta**

- Boot completo: o HAL core de áudio trava o system_server (corrigido na rodada 5, a conferir).
- Pilha Wi-Fi completa e adb pela rede (rodada 5, a conferir).
- Bluetooth e sensores.
- Widevine.
- Vídeo 10 bits e encoders.
- sepolicy própria (hoje permissive).
- Keystone no SurfaceFlinger (mesmas props `persist.sys.keystone.*`).
- Entrada HDMI (RK628, vídeo e áudio).
