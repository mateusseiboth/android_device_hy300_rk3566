"""Rodada 13b: vídeo protegido (Widevine L3) e vídeo em SurfaceView.

- O Cobalt (YouTube para TV) usa a chave com.widevine.alpha, para a qual sempre exige decoder com
  "secure-playback" (require_secured_decoder=true). Sem nenhum, o player não abre ("Failed to find
  decoder ... mustSupportSecure=true"). Com a feature opcional nos decoders da Rockchip, ele abre
  "c2.rk.*.decoder.secure"; o MediaCodec cria o componente base e o L3 decifra para memória comum
  (testado no aparelho: 66 amostras cifradas, 60 quadros).
- O minigbm genérico (backend dumb) só aceita scanout em RGB, e o consumidor de uma SurfaceView
  (BLAST) pede TEXTURE|COMPOSER: nenhum buffer YUV de vídeo alocava (HardwareBuffer YCBCR_420_888
  com COMPOSER_OVERLAY falha no aparelho). O patch tira o scanout quando ele é só a dica do HWC.

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
"""
import os
import unittest
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.normpath(os.path.join(HERE, "..", ".."))
MINIGBM_PATCH = os.path.join(TREE, "patches", "external", "minigbm",
                             "0002-yuv-com-hw-composer-sem-scanout.patch")
CODECS = os.path.join(TREE, "configs", "media", "media_codecs_c2_rk.xml")
SECURE_DECODERS = ("c2.rk.avc.decoder", "c2.rk.vp9.decoder", "c2.rk.hevc.decoder")


def read(path):
    with open(path) as handle:
        return handle.read()


def find_codec(name):
    for codec in ET.parse(CODECS).getroot().iter("MediaCodec"):
        if codec.get("name") == name:
            return codec
    raise AssertionError(f"{name} não está em {CODECS}")


class SecurePlaybackFeatureTest(unittest.TestCase):
    def test_decoders_offer_secure_playback(self):
        for name in SECURE_DECODERS:
            features = {f.get("name"): f for f in find_codec(name).iter("Feature")}
            self.assertIn("secure-playback", features, name)

    def test_secure_playback_is_optional(self):
        # Obrigatória, o decoder deixaria de servir para vídeo sem DRM.
        for name in SECURE_DECODERS:
            feature = [f for f in find_codec(name).iter("Feature")
                       if f.get("name") == "secure-playback"][0]
            self.assertNotEqual(feature.get("required"), "true", name)


class MinigbmScanoutFallbackTest(unittest.TestCase):
    def test_patch_drops_scanout_only_for_the_composer_hint(self):
        patch = read(MINIGBM_PATCH)
        self.assertIn("+++ b/cros_gralloc/cros_gralloc_driver.cc", patch)
        self.assertIn("+\tif (!combo && (descriptor->droid_usage & GRALLOC_USAGE_HW_COMPOSER)) {",
                      patch)
        self.assertIn("+\t\tresolved_use_flags &= ~BO_USE_SCANOUT;", patch)

    def test_fallback_comes_before_giving_up(self):
        patch = read(MINIGBM_PATCH)
        self.assertLess(patch.index("~BO_USE_SCANOUT"), patch.index(" \tif (!combo)\n \t\treturn false;"))


if __name__ == "__main__":
    unittest.main()
