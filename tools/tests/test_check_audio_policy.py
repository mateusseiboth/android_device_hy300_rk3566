"""Testes do tools/check_audio_policy.py: as regras do HAL de áudio AIDL de exemplo do AOSP sobre o
audio_policy_configuration.xml do vendor, no host, antes do boot.

Boot 6 (rodada 9): "HDMI In" (AUDIO_DEVICE_IN_HDMI) estava em <attachedDevices>. O HAL aborta em
convertModuleConfigToAidl (XsdcConversion.cpp, convertDevicePortsInModuleToAidl): um dispositivo
está em <attachedDevices> se e só se a conexão dele (tabela legado -> AIDL de
frameworks/av/media/audioaidlconversion/AidlConversionCppNdk.cpp) for vazia. HDMI tem conexão
"hdmi". O HAL reinicia em laço e o system_server fica preso no AudioService.

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import check_audio_policy  # noqa: E402

TREE = os.path.normpath(os.path.join(HERE, "..", ".."))
TOP = os.path.normpath(os.path.join(TREE, "..", "..", ".."))
CONVERSION = os.path.join(TOP, "frameworks", "av", "media", "audioaidlconversion",
                          "AidlConversionCppNdk.cpp")
BOOT6 = os.path.join(HERE, "data", "audio_primary_boot6.xml")
TABLE_EXCERPT = """
            {
                AUDIO_DEVICE_OUT_SPEAKER, make_AudioDeviceDescription(
                        AudioDeviceType::OUT_SPEAKER)
            },
            {
                AUDIO_DEVICE_IN_TV_TUNER, make_AudioDeviceDescription(
                        AudioDeviceType::IN_TV_TUNER)
            },
        append_AudioDeviceDescription(pairs,
                AUDIO_DEVICE_IN_HDMI, AUDIO_DEVICE_OUT_HDMI,
                AudioDeviceType::IN_DEVICE, AudioDeviceType::OUT_DEVICE,
                GET_DEVICE_DESC_CONNECTION(HDMI));
"""


class ConnectionTableTest(unittest.TestCase):
    def test_reads_single_and_paired_entries(self):
        table = check_audio_policy.parse_connection_table(TABLE_EXCERPT)
        self.assertEqual(table["AUDIO_DEVICE_OUT_SPEAKER"], "")
        self.assertEqual(table["AUDIO_DEVICE_IN_TV_TUNER"], "")
        self.assertEqual(table["AUDIO_DEVICE_IN_HDMI"], "HDMI")
        self.assertEqual(table["AUDIO_DEVICE_OUT_HDMI"], "HDMI")

    @unittest.skipUnless(os.path.exists(CONVERSION), "frameworks/av fora do checkout")
    def test_reads_the_real_table(self):
        with open(CONVERSION) as f:
            table = check_audio_policy.parse_connection_table(f.read())
        self.assertEqual(table["AUDIO_DEVICE_IN_HDMI"], "HDMI")
        self.assertEqual(table["AUDIO_DEVICE_IN_BUILTIN_MIC"], "")
        self.assertGreater(len(table), 50)


class RulesTest(unittest.TestCase):
    def setUp(self):
        self.table = check_audio_policy.parse_connection_table(TABLE_EXCERPT)

    def test_boot6_config_is_refused(self):
        problems = check_audio_policy.find_module_problems(BOOT6, self.table)
        self.assertTrue(any("HDMI In" in p and "attachedDevices" in p for p in problems), problems)

    def test_unknown_device_type_is_refused(self):
        xml = BOOT6.replace("boot6", "boot6")  # mesmo arquivo, tipo trocado abaixo
        with open(xml) as f:
            text = f.read().replace("AUDIO_DEVICE_OUT_SPEAKER", "AUDIO_DEVICE_OUT_NAO_EXISTE")
        problems = check_audio_policy.find_problems_in_text(text, self.table)
        self.assertTrue(any("AUDIO_DEVICE_OUT_NAO_EXISTE" in p for p in problems), problems)

    def test_r_submix_is_not_converted(self):
        # AudioPolicyConfigXmlConverter::init(): o módulo "r_submix" não passa pela conversão
        # (a configuração dele é fixa no HAL), então o "Remote Submix In" anexado não conta.
        text = """<module name="r_submix" halVersion="2.0">
            <attachedDevices><item>Remote Submix In</item></attachedDevices>
            <devicePorts>
                <devicePort tagName="Remote Submix In" type="AUDIO_DEVICE_IN_HDMI" role="source"/>
            </devicePorts></module>"""
        self.assertEqual(check_audio_policy.find_problems_in_text(text, self.table), [])

    def test_route_to_unknown_port_is_refused(self):
        with open(BOOT6) as f:
            text = f.read().replace('sources="primary output"', 'sources="nao existe"')
        problems = check_audio_policy.find_problems_in_text(text, self.table)
        self.assertTrue(any("nao existe" in p for p in problems), problems)


@unittest.skipUnless(os.path.exists(CONVERSION), "frameworks/av fora do checkout")
class TreeConfigTest(unittest.TestCase):
    def test_vendor_audio_policy_passes(self):
        problems = check_audio_policy.check_tree(TREE, TOP)
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
