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
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.normpath(os.path.join(HERE, "..", ".."))
TOP = os.path.normpath(os.path.join(TREE, "..", "..", ".."))
sys.path.insert(0, os.path.join(TREE, "tools"))
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
                         r"ifneq \(\$\(wildcard \$\(DEVICE_PATH\)/prebuilt-apps/aurora/AuroraStore.apk\),\)\n"
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


class FocusMotorAccessTest(unittest.TestCase):
    """Motor de foco (hy300_focus_motor): só o app de configurações escreve, por um gid de vendor
    que ele ganha pela permissão de assinatura FOCUS_MOTOR, e um tipo sysfs próprio na sepolicy."""

    def test_vendor_aid(self):
        text = read(os.path.join(TREE, "config.fs"))
        self.assertRegex(text, r"\[AID_VENDOR_HY300_MOTOR\]\nvalue: *29\d\d")
        board = read(os.path.join(TREE, "BoardConfig.mk"))
        self.assertIn("TARGET_FS_CONFIG_GEN += $(DEVICE_PATH)/config.fs", board)

    def test_permission_maps_to_the_gid(self):
        path = os.path.join(TREE, "configs", "permissions", "hy300-focus-motor.xml")
        root = ET.parse(path).getroot()
        perm = root.find("permission")
        self.assertEqual(perm.get("name"), "io.github.hy300.settings.permission.FOCUS_MOTOR")
        self.assertEqual(perm.find("group").get("gid"), "vendor_hy300_motor")
        # Só /system e /product podem mapear permissão para gid (SystemConfig, ALLOW_PERMISSIONS).
        self.assertIn("configs/permissions/hy300-focus-motor.xml:$(TARGET_COPY_OUT_PRODUCT)/etc/"
                      "permissions/hy300-focus-motor.xml", read(os.path.join(TREE, "device.mk")))

    def test_sepolicy_labels_the_node(self):
        sep = os.path.join(TREE, "sepolicy", "vendor")
        self.assertRegex(read(os.path.join(sep, "file.te")),
                         r"type sysfs_hy300_motor, sysfs_type, fs_type;")
        genfs = read(os.path.join(sep, "genfs_contexts"))
        for attr in ("motor", "hd_camera_on"):
            self.assertIn(f"genfscon sysfs /devices/platform/focus-motor/motor_cc/motor_cc/{attr} "
                          "u:object_r:sysfs_hy300_motor:s0", genfs)
        # O app tem domínio próprio desde a sepolicy da rodada 8 (hy300_settings_app).
        self.assertRegex(read(os.path.join(sep, "hy300_settings_app.te")),
                         r"allow hy300_settings_app sysfs_hy300_motor:file rw_file_perms;")
        self.assertIn("BOARD_VENDOR_SEPOLICY_DIRS += $(DEVICE_PATH)/sepolicy/vendor",
                      read(os.path.join(TREE, "BoardConfig.mk")))


class KernelModulesTest(unittest.TestCase):
    def test_modules_load_order(self):
        board = read(os.path.join(TREE, "BoardConfig.mk")).replace("\\\n", " ")
        line = next(l for l in board.splitlines() if l.startswith("BOARD_VENDOR_KERNEL_MODULES_LOAD"))
        names = line.split("=", 1)[1].split()
        self.assertEqual(names, ["drm_shmem_helper.ko", "gpu-sched.ko", "panfrost.ko",
                                 "aic8800_bsp.ko", "aic8800_btlpm.ko", "aic8800_fdrv.ko"])

    @unittest.skipUnless(os.path.exists(os.path.join(OUT, "vendor", "lib", "modules")),
                         "sem imagem montada")
    def test_built_modules_load_names_the_files(self):
        with open(os.path.join(OUT, "vendor", "lib", "modules", "modules.load")) as f:
            names = f.read().split()
        self.assertEqual(names.index("aic8800_btlpm.ko"), names.index("aic8800_bsp.ko") + 1)


class NamespaceTest(unittest.TestCase):
    def test_device_namespace_sees_librga(self):
        # O vendor.hy300.hdmiin-service copia pela RGA; a librga fica no namespace
        # hardware/rockchip/librga, que o namespace da árvore precisa importar (build da rodada 9:
        # "missing dependencies: librga").
        bp = read(os.path.join(TREE, "Android.bp"))
        namespace = bp[bp.index("soong_namespace {"):]
        namespace = namespace[:namespace.index("}")]
        self.assertIn('"hardware/rockchip/librga"', namespace)


class Boot7Test(unittest.TestCase):
    def test_vendor_modules_have_the_kernel_modules_label(self):
        # Boot 7: insmod do aic8800_bsp/btlpm negado (module_load) porque /vendor/lib/modules
        # ficava como vendor_file; o AOSP não rotula esse diretório.
        contexts = read(os.path.join(TREE, "sepolicy", "vendor", "file_contexts"))
        self.assertIn("/vendor/lib/modules(/.*)?  u:object_r:vendor_kernel_modules:s0", contexts)

    def test_test_builds_keep_more_log(self):
        # Low RAM deixa o logd com buffers mínimos: no boot 7 o log do HAL de Bluetooth sumiu antes
        # de alguém ler. Só fora do build "user".
        mk = read(os.path.join(TREE, "device.mk"))
        block = mk[mk.index("ifneq ($(TARGET_BUILD_VARIANT),user)"):]
        self.assertIn("ro.logd.size=1M", block[:block.index("endif")])


class AuroraLocationTest(unittest.TestCase):
    def test_aurora_lives_outside_the_kernel_prebuilt(self):
        # O worker do kernel copia o prebuilt com rsync --delete: o prebuilt/aurora sumiu na troca
        # para o cae418b6c490 e a Aurora saiu da imagem sem ninguém notar (rodadas 7 a 10).
        import fetch_aurora
        self.assertEqual(os.path.basename(os.path.dirname(fetch_aurora.DEST)), "prebuilt-apps")
        tracked = read(os.path.join(TREE, ".gitignore"))
        self.assertIn("/prebuilt-apps/", tracked)


class DrmTest(unittest.TestCase):
    """Rodada 12: YouTube para TV fechava em MediaDrm.isCryptoSchemeSupportedNative ("Failed to
    query crypto scheme support"). Sem nenhum HAL de DRM, DrmHal::initCheck() é ERROR_UNSUPPORTED,
    DrmUtils::MakeObject() devolve nulo e o JNI lança IllegalArgumentException. Com um IDrmFactory
    (ClearKey), a consulta por um UUID desconhecido (Widevine) devolve false."""

    def test_clearkey_hal_is_in_the_product(self):
        self.assertIn("android.hardware.drm-service-lazy.clearkey",
                      read_makefile_values("PRODUCT_PACKAGES"))

    def test_drm_is_a_required_hal(self):
        required = read(os.path.join(TREE, "configs", "vintf", "required_hals.txt"))
        self.assertRegex(required, r"(?m)^android\.hardware\.drm\.IDrmFactory/clearkey ")


class WidevineTest(unittest.TestCase):
    """Widevine L3 é binário do Google: fica num diretório local (vendor/hy300-widevine, fora dos
    repositórios) e a árvore pública só tem a ligação condicional e a sepolicy."""

    def test_widevine_only_with_the_local_directory(self):
        self.assertRegex(read(os.path.join(TREE, "device.mk")),
                         r"ifneq \(\$\(wildcard vendor/hy300-widevine/widevine.mk\),\)\n"
                         r"\$\(call inherit-product, vendor/hy300-widevine/widevine.mk\)\n"
                         r"endif")

    def test_sepolicy_has_the_widevine_domain(self):
        te = read(os.path.join(TREE, "sepolicy", "vendor", "hal_drm_widevine.te"))
        self.assertIn("hal_server_domain(hal_drm_widevine, hal_drm)", te)
        self.assertIn("init_daemon_domain(hal_drm_widevine)", te)
        self.assertRegex(te, r"allow hal_drm_widevine mediadrm_vendor_data_file:dir "
                             r"create_dir_perms;")
        self.assertRegex(read(os.path.join(TREE, "sepolicy", "vendor", "file.te")),
                         r"type mediadrm_vendor_data_file, file_type, data_file_type;")

    def test_sepolicy_labels_the_binary_and_the_data(self):
        contexts = read(os.path.join(TREE, "sepolicy", "vendor", "file_contexts"))
        self.assertRegex(contexts, r"(?m)^/vendor/bin/hw/android\\.hardware\\.drm-service"
                                   r"\(-lazy\)\?\\.widevine\s+u:object_r:hal_drm_widevine_exec:s0$")
        self.assertRegex(contexts, r"(?m)^/data/vendor/mediadrm\(/\.\*\)\?\s+"
                                   r"u:object_r:mediadrm_vendor_data_file:s0$")

    def test_service_name_has_the_drm_context(self):
        self.assertRegex(read(os.path.join(TREE, "sepolicy", "vendor", "service_contexts")),
                         r"(?m)^android\.hardware\.drm\.IDrmFactory/widevine\s+"
                         r"u:object_r:hal_drm_service:s0$")

    def test_no_apex_is_tracked(self):
        import subprocess
        tracked = subprocess.run(["git", "ls-files", "*.apex"], cwd=TREE,
                                 capture_output=True, text=True).stdout.split()
        self.assertEqual(tracked, [])


class DebuggableTest(unittest.TestCase):
    """Rodada 12: adb root e adb remount no userdebug (o LineageOS liga
    PRODUCT_NOT_DEBUGGABLE_IN_USERDEBUG em vendor/lineage/config/common.mk e o userdebug saía com
    ro.debuggable=0). O produto de topo vence as variáveis de valor único herdadas."""

    def test_product_turns_debuggable_back_on(self):
        # Valor único herdado não se desfaz no produto de topo (vazio herda; "false" vira true no
        # add_json_bool). O patch vendor/lineage/0001 deixa o common.mk respeitar a flag.
        text = read(os.path.join(TREE, "lineage_hy300.mk"))
        flag = text.index("TARGET_USERDEBUG_DEBUGGABLE := true")
        self.assertLess(flag, text.index("$(call inherit-product, vendor/lineage/config/common_full_tv.mk)"))
        self.assertNotIn("PRODUCT_NOT_DEBUGGABLE_IN_USERDEBUG :=", text)
        patch = read(os.path.join(TREE, "patches", "vendor", "lineage",
                                  "0001-userdebug-depuravel-por-flag.patch"))
        self.assertIn("+ifneq ($(TARGET_USERDEBUG_DEBUGGABLE),true)", patch)

    @unittest.skipUnless(os.path.exists(os.path.join(OUT, "system", "build.prop")),
                         "sem imagem montada")
    def test_built_userdebug_is_debuggable(self):
        props = read(os.path.join(OUT, "system", "build.prop"))
        if "ro.build.type=userdebug" in props:
            self.assertIn("ro.debuggable=1", props)


class MixedAbiTest(unittest.TestCase):
    """Rodada 14: 64 + 32 bits para apps de TV que só publicam armeabi-v7a."""

    def test_second_arch_is_arm_on_the_a55(self):
        board = read(os.path.join(TREE, "BoardConfig.mk"))
        for line in ("TARGET_2ND_ARCH := arm", "TARGET_2ND_ARCH_VARIANT := armv8-2a",
                     "TARGET_2ND_CPU_ABI := armeabi-v7a", "TARGET_2ND_CPU_ABI2 := armeabi",
                     "TARGET_2ND_CPU_VARIANT := cortex-a55"):
            self.assertIn(line, board)

    def test_cts_root_bionic_test_is_first_arch_only(self):
        # Com a segunda arquitetura o kati parava em "cannot copy target from multiple modules"
        # (testcases/CtsBionicRootTestCases do cts_root, uma cópia por variante).
        patch = read(os.path.join(TREE, "patches", "test", "cts-root",
                                  "0001-bionic-root-so-na-primeira-arquitetura.patch"))
        self.assertIn('+    compile_multilib: "first",', patch)

    def test_zygote64_32(self):
        mk = read(os.path.join(TREE, "device.mk"))
        self.assertIn("$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit.mk)", mk)
        self.assertNotIn("core_64_bit_only.mk", mk)

    @unittest.skipUnless(os.path.exists(os.path.join(OUT, "system", "build.prop")),
                         "sem imagem montada")
    def test_built_image_lists_32bit_abis(self):
        system = read(os.path.join(OUT, "system", "build.prop"))
        vendor = read(os.path.join(OUT, "vendor", "build.prop"))
        self.assertRegex(system + vendor, r"ro\.(system|vendor)\.product\.cpu\.abilist32=armeabi-v7a,armeabi")
        self.assertIn("ro.zygote=zygote64_32", vendor)


class LocaleTest(unittest.TestCase):
    def test_pt_br_is_the_default_locale(self):
        # O primeiro de PRODUCT_LOCALES vira ro.product.locale; o produto de topo vem antes dos
        # herdados (o full_base.mk põe en_US).
        text = read(os.path.join(TREE, "lineage_hy300.mk"))
        self.assertRegex(text, r"(?m)^PRODUCT_LOCALES := pt_BR\b")

    @unittest.skipUnless(os.path.exists(os.path.join(OUT, "system", "build.prop")),
                         "sem imagem montada")
    def test_built_image_defaults_to_pt_br(self):
        self.assertIn("ro.product.locale=pt-BR", read(os.path.join(OUT, "system", "build.prop")))


class NetflixTvFeaturesTest(unittest.TestCase):
    """A Netflix de TV (com.netflix.ninja) foi testada na rodada 14 e para no erro -13 (aparelho sem
    certificação Netflix). As features que ela exige não são declaradas: o aparelho não finge o que
    não é."""

    def test_no_netflix_tv_features_file(self):
        self.assertFalse(os.path.exists(os.path.join(TREE, "configs", "permissions",
                                                     "hy300-netflix-tv-test.xml")))

    def test_device_does_not_declare_netflix_features(self):
        mk = read(os.path.join(TREE, "device.mk"))
        self.assertNotIn("HY300_NETFLIX_TV_FEATURES", mk)
        self.assertNotIn("hy300-netflix-tv-test.xml", mk)

    def test_gles_stays_honest(self):
        self.assertIn("ro.opengles.version=196609", read(os.path.join(TREE, "device.mk")))


class GpuCompositionTest(unittest.TestCase):
    """Rodada 15: os planos de overlay do VOP2 pelo drm_hwcomposer garbavam a imagem (downscale além
    do limite do VOP e plano Smart com a Netflix de 352 de largura). Tudo é composto pela GPU."""

    def test_scaling_goes_to_the_gpu(self):
        self.assertEqual(read_vendor_props().get("vendor.hwc.drm.scale_with_gpu"), "1")

    def test_overlay_planes_are_off(self):
        self.assertEqual(read_vendor_props().get("ro.vendor.hwc.use_overlay_planes"), "0")

    @unittest.skipUnless(os.path.exists(os.path.join(TOP, "external", "drm_hwcomposer")),
                         "sem o drm_hwcomposer no checkout")
    def test_property_names_match_the_hwcomposer(self):
        source = read(os.path.join(TOP, "external", "drm_hwcomposer", "utils", "properties.cpp"))
        self.assertIn('"vendor.hwc.drm.scale_with_gpu"', source)
        self.assertIn('"ro.vendor.hwc.use_overlay_planes"', source)


class LargeScreenTest(unittest.TestCase):
    """Rodada 15: com 160 dpi o painel de 1024x600 tem sw600dp, tela grande para o framework. Assim
    o ignoreOrientationRequest vem ligado por padrão (DisplayContent.getIgnoreOrientationRequest) e
    o OVERRIDE_ANY_ORIENTATION_TO_USER vale (AppCompatAspectRatioOverrides): a Netflix de celular
    abre em paisagem, com o layout de tablet."""

    OVERRIDES = os.path.join(TREE, "configs", "appcompat", "compat_framework_overrides.xml")
    OVERRIDE_ANY_ORIENTATION_TO_USER = 310816437

    def test_density_gives_sw600dp(self):
        board = read(os.path.join(TREE, "BoardConfig.mk"))
        density = int(re.search(r"(?m)^TARGET_SCREEN_DENSITY := (\d+)", board).group(1))
        self.assertGreaterEqual(600 * 160 // density, 600)

    def test_netflix_orientation_override(self):
        root = ET.parse(self.OVERRIDES).getroot()
        self.assertEqual(root.tag, "overrides")
        changes = {int(c.get("changeId")): c for c in root.iter("change-overrides")}
        raw = changes[self.OVERRIDE_ANY_ORIENTATION_TO_USER].find("raw")
        packages = {v.get("packageName"): v.get("enabled") for v in raw.iter("raw-override-value")}
        self.assertEqual(packages, {"com.netflix.mediaclient": "true"})

    def test_overrides_go_to_the_static_product_path(self):
        # CompatConfig lê os overrides estáticos de /product/etc/appcompat.
        mk = read(os.path.join(TREE, "device.mk"))
        self.assertIn("configs/appcompat/compat_framework_overrides.xml:"
                      "$(TARGET_COPY_OUT_PRODUCT)/etc/appcompat/compat_framework_overrides.xml", mk)

    @unittest.skipUnless(os.path.exists(os.path.join(TOP, "frameworks", "base")),
                         "sem o frameworks/base no checkout")
    def test_change_id_matches_the_framework(self):
        source = read(os.path.join(TOP, "frameworks", "base", "core", "java", "android", "content",
                                   "pm", "ActivityInfo.java"))
        self.assertIn(f"OVERRIDE_ANY_ORIENTATION_TO_USER = {self.OVERRIDE_ANY_ORIENTATION_TO_USER}L",
                      source)


class SoftwareAv1Test(unittest.TestCase):
    """Rodada 14: o YouTube escolhia o AV1 de software (c2.android.av1-dav1d.decoder, media.swcodec a
    194 % de CPU) e o vídeo travava. O RK3566 não tem AV1 em hardware e os A55 não dão conta em
    tempo real: os dois decoders AV1 de software ficam desligados no media_codecs do vendor."""

    def test_software_av1_decoders_are_disabled(self):
        root = ET.parse(os.path.join(TREE, "configs", "media", "media_codecs.xml")).getroot()
        decoders = {c.get("name"): c for c in root.iter("MediaCodec")}
        for name in ("c2.android.av1-dav1d.decoder", "c2.android.av1.decoder"):
            self.assertEqual(decoders[name].get("update"), "true", name)
            self.assertEqual(decoders[name].get("enabled"), "false", name)

    def test_hw_decoders_stay(self):
        text = read(os.path.join(TREE, "configs", "media", "media_codecs.xml"))
        self.assertLess(text.index('<Include href="media_codecs_c2_rk.xml" />'),
                        text.index("c2.android.av1-dav1d.decoder"))


if __name__ == "__main__":
    unittest.main()
