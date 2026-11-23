"""Testes do configs/init/init.rk3566.rc: os gatilhos têm de disparar de verdade no build.

No primeiro boot o hy300-diag não rodou: o gatilho era "post-fs && property:ro.debuggable=1", e o
LineageOS sai do userdebug com ro.debuggable=0 (PRODUCT_NOT_DEBUGGABLE_IN_USERDEBUG). Por isso
aqui cada condição de propriedade dos nossos gatilhos é conferida contra o que o build grava:
- ro.boot.*: vem da cmdline do BoardConfig.mk (androidboot.*);
- outras ro.*: vêm dos build.prop da imagem montada (out/target/product/hy300), se existir.

Rodar, na raiz da árvore: python3 -I -m unittest discover -s tools/tests
(HY300_OUT aponta para outro out/target/product/hy300)
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.join(HERE, "..", "..")
RC = os.path.join(TREE, "configs", "init", "init.rk3566.rc")
BOARD = os.path.join(TREE, "BoardConfig.mk")
OUT = os.environ.get("HY300_OUT",
                     os.path.join(TREE, "..", "..", "..", "out", "target", "product", "hy300"))
BUILD_PROPS = ("system/build.prop", "vendor/build.prop", "product/etc/build.prop",
               "system_ext/etc/build.prop", "odm/etc/build.prop")
EARLY_EVENTS = {"early-init", "init", "late-init", "early-fs", "fs", "post-fs", "late-fs",
                "post-fs-data", "early-boot", "boot"}


def parse_rc(path):
    services, actions, current = {}, [], None
    with open(path) as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("service "):
                parts = line.split(maxsplit=2)
                current = {"kind": "service", "name": parts[1],
                           "command": parts[2] if len(parts) > 2 else "", "lines": []}
                services[current["name"]] = current
            elif line.startswith("on "):
                current = {"kind": "action", "trigger": line[3:], "lines": []}
                actions.append(current)
            elif current is not None:
                current["lines"].append(line)
    return services, actions


def split_trigger(trigger):
    event, props = None, {}
    for part in (p.strip() for p in trigger.split("&&")):
        if part.startswith("property:"):
            name, _, value = part[len("property:"):].partition("=")
            props[name] = value
        else:
            event = part
    return event, props


def read_cmdline_props():
    with open(BOARD) as f:
        text = f.read()
    props = {}
    for line in text.splitlines():
        if line.startswith("BOARD_KERNEL_CMDLINE"):
            for token in line.split():
                if token.startswith("androidboot.") and "=" in token:
                    key, _, value = token.partition("=")
                    props["ro.boot." + key[len("androidboot."):]] = value
    return props


def read_build_props():
    props = {}
    for rel in BUILD_PROPS:
        path = os.path.join(OUT, rel)
        if not os.path.exists(path):
            continue
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    props.setdefault(key, value)
    return props


class InitRcTest(unittest.TestCase):
    def setUp(self):
        self.services, self.actions = parse_rc(RC)

    def actions_starting(self, service):
        return [a for a in self.actions if f"start {service}" in a["lines"]]

    def test_started_services_are_defined(self):
        for action in self.actions:
            for line in action["lines"]:
                if line.startswith("start "):
                    self.assertIn(line.split()[1], self.services, action["trigger"])

    def test_diag_is_started_early_on_userdebug(self):
        actions = self.actions_starting("hy300-diag")
        self.assertEqual(len(actions), 1)
        event, props = split_trigger(actions[0]["trigger"])
        self.assertIn(event, EARLY_EVENTS)
        self.assertNotIn("ro.debuggable", props)
        self.assertEqual(props.get("ro.build.type"), "userdebug")

    def test_diag_runs_with_the_system_shell(self):
        # O sh do vendor (sh_vendor) força PATH=/vendor/bin:/vendor/xbin (MKSH_DEFPATH_OVERRIDE):
        # no boot 2 logcat, ip e iw saíram "inaccessible or not found".
        service = self.services["hy300-diag"]
        self.assertTrue(service.get("command", "").startswith("/system/bin/sh "), service)

    def test_net_starts_after_boot_completed_only_on_userdebug(self):
        actions = self.actions_starting("hy300-net")
        self.assertEqual(len(actions), 1)
        event, props = split_trigger(actions[0]["trigger"])
        self.assertIsNone(event)
        self.assertEqual(props.get("sys.boot_completed"), "1")
        self.assertEqual(props.get("ro.build.type"), "userdebug")
        self.assertTrue(self.services["hy300-net"]["command"].startswith("/system/bin/sh "))

    def test_alpine_trigger_needs_userdebug_and_adbd(self):
        # O shell do adb seta debug.hy300.alpine=1; na imagem de uso só funciona com o adb ligado.
        actions = self.actions_starting("hy300-alpine")
        self.assertEqual(len(actions), 1)
        event, props = split_trigger(actions[0]["trigger"])
        self.assertIsNone(event)
        self.assertEqual(props, {"debug.hy300.alpine": "1", "ro.build.type": "userdebug",
                                 "init.svc.adbd": "running"})
        service = self.services["hy300-alpine"]
        self.assertTrue(service["command"].startswith("/system/bin/sh /vendor/bin/hy300-alpine.sh"))
        for line in ("disabled", "oneshot", "seclabel u:r:su:s0", "user root"):
            self.assertIn(line, service["lines"])

    def test_board_cmdline_is_the_test_profile(self):
        # A imagem de uso é o mesmo build com androidboot.hy300.perfil=uso (lineage_prebuilt.py
        # variant); a variant só troca chave que já existe na cmdline.
        self.assertEqual(read_cmdline_props().get("ro.boot.hy300.perfil"), "teste")

    def test_wifi_modules_load_in_background_on_boot(self):
        actions = self.actions_starting("hy300-wifi-modules")
        self.assertEqual([split_trigger(a["trigger"])[0] for a in actions], ["boot"])
        self.assertIn("oneshot", self.services["hy300-wifi-modules"]["lines"])

    def test_cmdline_property_triggers_match_board_cmdline(self):
        cmdline = read_cmdline_props()
        for action in self.actions:
            _, props = split_trigger(action["trigger"])
            for name, value in props.items():
                if name.startswith("ro.boot.hy300."):
                    self.assertIn(name, cmdline, action["trigger"])

    def test_gpu_choice_covers_the_board_cmdline(self):
        # Padrão desde a rodada 4: GPU (a tempestade de IRQ do GPIO explicava as travadas).
        value = read_cmdline_props().get("ro.boot.hy300.gpu")
        self.assertEqual(value, "panfrost")
        triggers = [split_trigger(a["trigger"])[1].get("ro.boot.hy300.gpu") for a in self.actions]
        self.assertIn("panfrost", triggers)
        self.assertIn("sw", triggers)

    @unittest.skipUnless(os.path.exists(os.path.join(OUT, "system", "build.prop")),
                         "sem imagem montada em out/target/product/hy300")
    def test_build_property_triggers_hold_in_the_built_image(self):
        built = read_build_props()
        for action in self.actions:
            event, props = split_trigger(action["trigger"])
            if event not in EARLY_EVENTS:
                continue
            for name, value in props.items():
                if name.startswith("ro.") and not name.startswith("ro.boot."):
                    self.assertEqual(built.get(name), value,
                                     f"{action['trigger']}: {name} no build é {built.get(name)!r}")


if __name__ == "__main__":
    unittest.main()
