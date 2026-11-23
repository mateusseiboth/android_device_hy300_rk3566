"""Testes das escolhas do produto que não têm código próprio: propriedades, codecs e pacotes.

- Encoders por hardware: c2.rk.avc.encoder e c2.rk.hevc.encoder declarados no media_codecs e
  registrados pelo store do Codec2 da Rockchip (C2RKPlatformSupport.h).
- debug.stagefright.c2inputsurface=-1: sem InputSurface no HAL do Codec2 (HIDL 1.1 da Rockchip) e
  sem OMX, o CCodec::createInputSurface derrefere nulo; com -1 ele usa o GraphicBufferSource no
  próprio processo.
- Fuso padrão America/Campo_Grande.
- O assistente do LineageOS não cabe em 1024x600: sai do produto, o TvProvision marca o aparelho
  como configurado.

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
(HY300_OUT aponta para outro out/target/product/hy300)
"""
import os
import re
import unittest
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.normpath(os.path.join(HERE, "..", ".."))
TOP = os.path.normpath(os.path.join(TREE, "..", "..", ".."))
OUT = os.environ.get("HY300_OUT", os.path.join(TOP, "out", "target", "product", "hy300"))
CODECS = os.path.join(TREE, "configs", "media", "media_codecs_c2_rk.xml")
STORE = os.path.join(TOP, "hardware", "rockchip", "codec2", "store", "C2RKPlatformSupport.h")
HW_ENCODERS = {"c2.rk.avc.encoder": "video/avc", "c2.rk.hevc.encoder": "video/hevc"}


def read(path):
    with open(path) as f:
        return f.read()


def read_makefile_values(name):
    """Valores atribuídos com += a uma variável nos .mk da árvore (continuações com \\)."""
    values = []
    for mk in ("device.mk", "lineage_hy300.mk"):
        text = read(os.path.join(TREE, mk)).replace("\\\n", " ")
        for line in text.splitlines():
            if re.match(rf"\s*{name}\s*\+?=", line):
                values += line.split("=", 1)[1].split()
    return values


def read_vendor_props():
    props = {}
    for entry in read_makefile_values("PRODUCT_VENDOR_PROPERTIES") + \
            read_makefile_values("PRODUCT_PRODUCT_PROPERTIES") + \
            read_makefile_values("PRODUCT_SYSTEM_PROPERTIES"):
        key, _, value = entry.partition("=")
        props[key] = value
    return props


def find_codecs(path, kind):
    section = ET.parse(path).getroot().find(kind)
    return {} if section is None else {c.get("name"): c for c in section.iter("MediaCodec")}


class EncoderTest(unittest.TestCase):
    def test_hw_encoders_are_declared(self):
        encoders = find_codecs(CODECS, "Encoders")
        for name, mime in HW_ENCODERS.items():
            self.assertIn(name, encoders)
            self.assertEqual(encoders[name].get("type"), mime)

    def test_hw_encoders_stop_at_1080p(self):
        for name, codec in find_codecs(CODECS, "Encoders").items():
            size = next(l for l in codec.iter("Limit") if l.get("name") == "size")
            self.assertEqual(size.get("max"), "1920x1088", name)

    @unittest.skipUnless(os.path.exists(STORE), "hardware/rockchip/codec2 fora do checkout")
    def test_hw_encoders_are_registered_by_the_store(self):
        store = read(STORE)
        for name in HW_ENCODERS:
            self.assertIn(f'"{name}"', store)

    def test_hw_encoders_declare_performance_points(self):
        # Sem medição no aparelho não há media_codecs_performance.xml (measured-frame-rate seria
        # inventado); o ponto de desempenho declarado é o do datasheet: 1080p60.
        for name, codec in find_codecs(CODECS, "Encoders").items():
            limits = {l.get("name"): l.get("value") for l in codec.iter("Limit")}
            self.assertEqual(limits.get("performance-point-1920x1088"), "60", name)


class SeccompTest(unittest.TestCase):
    """O serviço do Codec2 roda com seccomp (minijail): chamada fora da lista mata o processo.
    O encoder importa o buffer de entrada no MPP (mpp_buffer_import -> mpp_dup -> fcntl), o que
    o decoder em buffer mode nunca faz."""

    POLICY = os.path.join(TREE, "configs", "seccomp",
                          "android.hardware.media.c2@1.1-extended-seccomp-policy")

    def test_extended_policy_allows_what_the_encoder_needs(self):
        allowed = {line.split(":")[0].strip() for line in read(self.POLICY).splitlines()
                   if line.strip() and not line.startswith("#")}
        self.assertTrue({"fcntl", "timerfd_create", "epoll_create1"} <= allowed)

    def test_extended_policy_is_installed_where_the_service_reads_it(self):
        self.assertIn("configs/seccomp/android.hardware.media.c2@1.1-extended-seccomp-policy:"
                      "$(TARGET_COPY_OUT_VENDOR)/etc/seccomp_policy/"
                      "android.hardware.media.c2@1.1-extended-seccomp-policy",
                      read(os.path.join(TREE, "device.mk")))


class PropsTest(unittest.TestCase):
    def test_input_surface_uses_the_graphic_buffer_source(self):
        self.assertEqual(read_vendor_props().get("debug.stagefright.c2inputsurface"), "-1")

    def test_default_timezone_is_campo_grande(self):
        self.assertEqual(read_vendor_props().get("persist.sys.timezone"), "America/Campo_Grande")


class PackagesTest(unittest.TestCase):
    def test_tv_provision_replaces_the_setup_wizard(self):
        self.assertIn("TvProvision", read_makefile_values("PRODUCT_PACKAGES"))
        bp = read(os.path.join(TREE, "Android.bp"))
        self.assertRegex(bp, r'overrides:\s*\[[^\]]*"LineageSetupWizard"')
        self.assertRegex(bp, r'overrides:\s*\[[^\]]*"Updater"')
        self.assertIn("hy300-package-overrides", read_makefile_values("PRODUCT_PACKAGES"))

    @unittest.skipUnless(os.path.exists(os.path.join(OUT, "system", "build.prop")),
                         "sem imagem montada")
    def test_built_image_has_no_setup_wizard(self):
        self.assertFalse(os.path.exists(os.path.join(OUT, "system_ext", "priv-app",
                                                     "LineageSetupWizard")))


class ProprietaryTest(unittest.TestCase):
    """GApps e APKs de terceiros só no build local: a árvore pública só tem a configuração."""

    def test_gapps_are_optional_and_only_with_the_local_checkout(self):
        text = read(os.path.join(TREE, "device.mk"))
        self.assertIn("HY300_WITH_GAPPS ?= true", text)
        self.assertRegex(text, r"ifneq \(\$\(wildcard vendor/gapps_tv/arm64/arm64-vendor.mk\),\)\n"
                               r"GMS_VARIANT := minimal\n"
                               r"\$\(call inherit-product, vendor/gapps_tv/arm64/arm64-vendor.mk\)")

    def test_aurora_only_when_the_apk_was_fetched(self):
        self.assertRegex(read(os.path.join(TREE, "device.mk")),
                         r"ifneq \(\$\(wildcard \$\(DEVICE_PATH\)/prebuilt/aurora/AuroraStore.apk\),\)\n"
                         r"PRODUCT_PACKAGES \+= AuroraStore")

    def test_no_apk_or_zip_is_tracked(self):
        import subprocess
        tracked = subprocess.run(["git", "ls-files", "*.apk", "*.zip", "*.so"], cwd=TREE,
                                 capture_output=True, text=True).stdout.split()
        self.assertEqual(tracked, [])


class ZramTest(unittest.TestCase):
    """zram gerenciado pelo mmd (Android 17): tamanho, lz4 e writeback de páginas ociosas para o
    eMMC com limite diário. Números em docs/lineageos.md do hy300-rk3566 (rodada 6)."""

    def setUp(self):
        self.props = read_vendor_props()

    def test_fstab_leaves_zram_to_mmd(self):
        # Com a linha no fstab o swapon_all ativa o zram antes do mmd_setup, que então pula a
        # configuração inteira (e o writeback junto).
        fstab = read(os.path.join(TREE, "configs", "init", "fstab.rk3566"))
        self.assertNotRegex(fstab, r"(?m)^/dev/block/zram")
        rc = read(os.path.join(TREE, "configs", "init", "init.rk3566.rc"))
        self.assertNotIn("swapon_all", rc)
        self.assertNotIn("/sys/block/zram0", rc)

    def test_mmd_sets_up_zram_with_lz4_at_125_percent(self):
        self.assertEqual(self.props.get("mmd.zram.enabled"), "true")
        self.assertEqual(self.props.get("mmd.zram.size"), "125%")
        self.assertEqual(self.props.get("mmd.zram.comp_algorithm"), "lz4")

    def test_writeback_is_on_and_bounded(self):
        self.assertEqual(self.props.get("mmd.zram.writeback.enabled"), "true")
        self.assertLessEqual(int(self.props["mmd.zram.writeback.device_size"]), 1 << 30)
        self.assertLessEqual(int(self.props["mmd.zram.writeback.max_bytes_per_day"]), 256 << 20)
        self.assertEqual(self.props.get("mmd.zram.writeback.limit.enabled"), "true")

    def test_maintenance_does_not_wait_for_device_idle(self):
        # Projetor: o aparelho é desligado da tomada em vez de ficar ocioso com a tela apagada.
        self.assertEqual(self.props.get("mm.zram.maintenance.require_device_idle"), "false")


if __name__ == "__main__":
    unittest.main()
