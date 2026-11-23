"""Nenhum vídeo de app pode escapar do keystone por um caminho direto ao VOP2: o SurfaceFlinger
manda toda camada para a composição pelo cliente com keystone (patches/frameworks/native), e o
vídeo em túnel (sideband do decodificador direto para o compositor) não pode ser anunciado nos
media_codecs: os apps só pedem túnel quando o codec declara "tunneled-playback".

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
"""
import glob
import os
import unittest
import xml.etree.ElementTree as ET

TREE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")


class NoTunneledPlaybackTest(unittest.TestCase):
    def test_no_codec_declares_tunneled_playback(self):
        for path in glob.glob(os.path.join(TREE, "configs", "media", "*.xml")):
            for feature in ET.parse(path).getroot().iter("Feature"):
                self.assertNotEqual(feature.get("name"), "tunneled-playback",
                                    f"{os.path.basename(path)} anuncia vídeo em túnel")


if __name__ == "__main__":
    unittest.main()
