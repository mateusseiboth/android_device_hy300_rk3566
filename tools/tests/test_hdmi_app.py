"""Testes do app da entrada HDMI (apps/HdmiInput): a lógica sem Android (escolha das portas do
patch de áudio, estado do sinal) com JUnit no host, e o manifesto: o serviço tem de ser um TV
input de hardware (permissões) e a tela tem de atender o "passthrough" do seletor de entradas.

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
"""
import glob
import os
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "..", "apps", "HdmiInput")
ANDROID = "{http://schemas.android.com/apk/res/android}"


def find_jar(name):
    for root in (os.path.expanduser("~/.gradle"), os.path.expanduser("~/.m2")):
        found = glob.glob(os.path.join(root, "**", name), recursive=True)
        if found:
            return found[0]
    return None


JUNIT = find_jar("junit-4.13.2.jar")
HAMCREST = find_jar("hamcrest-core-1.3.jar")


@unittest.skipUnless(shutil.which("javac") and JUNIT and HAMCREST, "sem javac ou JUnit no host")
class HdmiAppLogicTest(unittest.TestCase):
    def test_junit_of_the_logic_passes(self):
        sources = [os.path.join(APP, "src", "io", "github", "hy300", "hdmi", name)
                   for name in ("AudioPortChooser.java", "Signal.java")]
        sources += glob.glob(os.path.join(APP, "tests", "**", "*.java"), recursive=True)
        with tempfile.TemporaryDirectory() as out:
            subprocess.run(["javac", "-d", out, "-cp", JUNIT, *sources], check=True,
                           capture_output=True)
            result = subprocess.run(
                ["java", "-cp", os.pathsep.join([out, JUNIT, HAMCREST]),
                 "org.junit.runner.JUnitCore", "io.github.hy300.hdmi.AudioPortChooserTest",
                 "io.github.hy300.hdmi.SignalTest"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class HdmiAppManifestTest(unittest.TestCase):
    def setUp(self):
        self.manifest = ET.parse(os.path.join(APP, "AndroidManifest.xml")).getroot()

    def test_service_is_a_hardware_tv_input(self):
        permissions = {p.get(ANDROID + "name") for p in self.manifest.iter("uses-permission")}
        self.assertIn("android.permission.TV_INPUT_HARDWARE", permissions)
        service = self.manifest.find("application/service")
        self.assertEqual(service.get(ANDROID + "permission"), "android.permission.BIND_TV_INPUT")
        actions = {a.get(ANDROID + "name") for a in service.iter("action")}
        self.assertIn("android.media.tv.TvInputService", actions)

    def test_activity_opens_from_the_input_picker(self):
        datas = list(self.manifest.find("application/activity").iter("data"))
        self.assertTrue(any(d.get(ANDROID + "pathPrefix") == "/passthrough" for d in datas))

    def test_privileged_permissions_are_granted(self):
        root = ET.parse(os.path.join(APP, "privapp-permissions-hy300-hdmi.xml")).getroot()
        granted = {p.get("name") for p in root.iter("permission")}
        self.assertEqual(granted, {"android.permission.TV_INPUT_HARDWARE",
                                   "android.permission.MODIFY_AUDIO_ROUTING"})


if __name__ == "__main__":
    unittest.main()
