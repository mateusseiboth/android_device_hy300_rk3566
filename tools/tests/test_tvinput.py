"""Testes da entrada HDMI (tvinput/ e o HDMI In do audio_policy): a lógica do HAL de TV input é
compilada e testada no host, e o endereço ALSA tem de ser o mesmo no audio_policy e na prop do
HAL (senão o framework não acha o HDMI In e não liga o áudio).

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
"""
import os
import re
import sys
import unittest
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import host_gtest  # noqa: E402

TREE = os.path.join(HERE, "..", "..")
TVINPUT = os.path.join(TREE, "tvinput")
POLICY = os.path.join(TREE, "configs", "audio", "hy300_primary_audio_policy_configuration.xml")


@unittest.skipUnless(host_gtest.find_compiler() and host_gtest.has_gtest(host_gtest.find_compiler()),
                     "sem compilador C++ ou gtest no host")
class TvInputCoreGtest(unittest.TestCase):
    def test_gtest_of_the_core_passes(self):
        result = host_gtest.run_sources(
            [os.path.join(TVINPUT, "core", "HdmiInCore.cpp"),
             os.path.join(TVINPUT, "tests", "HdmiInCoreTest.cpp")],
            [f"-I{os.path.join(TVINPUT, 'core')}"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASSED", result.stdout)


class HdmiAudioRouteTest(unittest.TestCase):
    def setUp(self):
        self.module = ET.parse(POLICY).getroot()

    def hdmi_port(self):
        return next(p for p in self.module.iter("devicePort") if p.get("tagName") == "HDMI In")

    def test_hdmi_in_is_a_built_in_capture_device(self):
        # Boot 6: AUDIO_DEVICE_IN_HDMI tem conexão "hdmi" e o HAL de áudio de exemplo aborta se um
        # dispositivo com conexão estiver em <attachedDevices>. O RK628 é soldado na placa: o HDMI
        # In entra como AUDIO_DEVICE_IN_TV_TUNER (embutido, conexão vazia), sempre presente.
        self.assertEqual(self.hdmi_port().get("type"), "AUDIO_DEVICE_IN_TV_TUNER")

    def test_tv_input_hal_announces_the_same_device_type(self):
        with open(os.path.join(TREE, "tvinput", "hal", "TvInput.cpp")) as source:
            text = source.read()
        self.assertIn("AudioDeviceType::IN_TV_TUNER", text)
        self.assertNotIn("CONNECTION_HDMI", text)

    def test_hdmi_app_patches_from_the_same_device_type(self):
        with open(os.path.join(TREE, "apps", "HdmiInput", "src", "io", "github", "hy300", "hdmi",
                               "AudioRoute.java")) as source:
            text = source.read()
        self.assertIn("AudioSystem.DEVICE_IN_TV_TUNER", text)
        self.assertNotIn("DEVICE_IN_HDMI", text)

    def test_hdmi_in_address_matches_the_hal_property(self):
        with open(os.path.join(TREE, "device.mk")) as mk:
            prop = re.search(r"ro\.vendor\.hy300\.hdmiin\.audio_address=(\S+)", mk.read())
        self.assertEqual(self.hdmi_port().get("address"), prop.group(1))

    def test_hdmi_in_is_recordable_but_not_routed_to_the_speaker(self):
        routes = {(r.get("sink"), r.get("sources")) for r in self.module.iter("route")}
        self.assertIn(("hdmi input", "HDMI In"), routes)
        self.assertFalse(any(sink == "Speaker" and "HDMI In" in sources
                             for sink, sources in routes))

    def test_hdmi_in_is_attached(self):
        items = [item.text for item in self.module.find("attachedDevices")]
        self.assertIn("HDMI In", items)


class TvInputHalFilesTest(unittest.TestCase):
    def test_rc_declares_the_aidl_interface(self):
        with open(os.path.join(TVINPUT, "hal", "android.hardware.tv.input-service.hy300.rc")) as rc:
            self.assertIn("interface aidl android.hardware.tv.input.ITvInput/default", rc.read())

    def test_links_the_audio_types_that_tv_input_v1_imports(self):
        # Sem ela o link falha: AudioDeviceDescription::CONNECTION_HDMI fica indefinido (build da
        # rodada 8).
        with open(os.path.join(TVINPUT, "Android.bp")) as bp:
            self.assertIn('"android.media.audio.common.types-V1-ndk"', bp.read())


if __name__ == "__main__":
    unittest.main()
