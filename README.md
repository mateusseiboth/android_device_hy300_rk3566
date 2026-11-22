# device/hy300/rk3566: LineageOS 24.0 (Android 17) para o projetor HY300

Esqueleto da árvore de dispositivo do HY300 (Rockchip RK3566, 1,5 GB de RAM, painel LVDS
1024x600, TXCZ y356tx). Ainda **não compila**: faltam o Mesa com Panfrost, os HALs de
áudio, Bluetooth, KeyMint e sensores, a política SELinux e o patch de keystone. O plano, o
inventário do aparelho e os riscos estão em `docs/lineageos.md` do repositório do projeto
(`hy300-rk3566`). Aqui fica só o porquê de cada arquivo.

Nenhum binário proprietário entra neste repositório. `prebuilt/` é ignorado pelo git.

## Como usar (quando o checkout terminar)

```sh
# a árvore vai para device/hy300/rk3566 do checkout do lineage-24.0
ln -s ~/android/device-hy300 ~/android/lineage/device/hy300/rk3566   # ou clonar ali
# prebuilt/ (ver abaixo), depois:
source build/envsetup.sh
breakfast hy300            # = lunch lineage_hy300-cp2a-userdebug
python3 -I -m unittest discover -s device/hy300/rk3566/tools/tests
```

## Arquivos

| Arquivo | O que é | Decisão |
|---|---|---|
| `AndroidProducts.mk` | lista de produtos | um produto só, `lineage_hy300`; a release `cp2a` vem de `vendor/lineage/vars/aosp_target_release` |
| `lineage_hy300.mk` | produto | Android TV do LineageOS: `atv_base.mk` + `common_full_tv.mk` (que traz `device/lineage/atv`, TvSettingsTwoPanel, LeanbackIME e o launcher Catapult), mais `atv_lowram_defaults.mk` para 1,5 GB. Mesmo esquema dos aparelhos ATV do Lineage |
| `device.mk` | pacotes, cópias, props | só 64 bits (`core_64_bit_only.mk`, um zygote); `PRODUCT_SHIPPING_API_LEVEL := 31` (Android 12 de fábrica); gráficos abertos (drm_hwcomposer hwc3 + minigbm; Mesa ainda por vir) |
| `BoardConfig.mk` | placa | ver "Boot" e "Partições" |
| `configs/init/fstab.rk3566` | fstab | derivado do `fstab.rk30board` de fábrica (diferenças no topo do arquivo) |
| `configs/init/init.rk3566.rc` | init da placa | `mount_all`, zram, permissões do motor de foco (`/sys/class/motor_cc`) e dos LEDs para o app de configurações (uid system) |
| `configs/init/ueventd.rk3566.rc` | nós de `/dev` | UART do Bluetooth, vendor storage, MPP, RGA, V4L2 da entrada HDMI |
| `configs/vintf/manifest.xml` | manifesto VINTF | `target-level="8"`: no Android 17 o kernel 6.1 só é aceito pela matriz de nível 8 |
| `keylayout/fdd70030_pwm.kl` | controle IR | escrito a partir das tabelas IR do DT do 6.1; F6 = entrada HDMI, F12 = configurações do projetor |
| `build/tasks/resource_img.mk` | resource.img | copia `prebuilt/resource.img` para a seção `second` |
| `tools/mkbootimg_hy300.py` | wrapper do mkbootimg | recalcula o ID SHA-1 que o U-Boot confere (testes em `tools/tests/`) |

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
  38,8 MiB. O U-Boot tem gzip/lz4 no `bootm`; falta confirmar no slot `recovery`.
- **cmdline**: vem toda do boot.img. `androidboot.hardware=rk3566` (dá nome ao `fstab` e ao
  `init.rk3566.rc`); `androidboot.boot_devices=fe310000.mmc`, que é o nome do eMMC no 6.1
  (no 4.19 era `fe310000.sdhci`).
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

| Arquivo | De onde vem |
|---|---|
| `Image.gz` | build do kernel `hy300` (`gzip -9 -n arch/arm64/boot/Image`) |
| `dtb/*.dtb` | qualquer DTB: a seção dtb do header v2 é exigida pelo mkbootimg, mas o U-Boot não a usa. Usar o `rk3566-hy300.dtb` do build |
| `resource.img` | a seção `second` do `boot.img` do próprio aparelho, já com o logo da capivara: `tools/mkboot.py unpack ~/hy300-backup/boot.img /tmp/boot` (repositório do projeto) e copiar o arquivo da seção second |

## O que falta (ordem em `docs/lineageos.md`)

1. Kernel com as configs do Android (binder, ashmem, SELinux, BPF, netfilter etc.).
2. Mesa com Panfrost (aospext do GloDroid) e o primeiro boot até a tela.
3. sepolicy própria; áudio; Bluetooth; KeyMint/Gatekeeper por software; sensores.
4. Keystone no SurfaceFlinger (mesmas props `persist.sys.keystone.*`), app de configurações
   como app de plataforma, entrada HDMI (RK628).
