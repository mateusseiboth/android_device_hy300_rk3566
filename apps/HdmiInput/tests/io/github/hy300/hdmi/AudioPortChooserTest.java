package io.github.hy300.hdmi;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

/** Escolha das portas do patch de áudio HDMI In -> alto-falante. */
public class AudioPortChooserTest {
    private static final int SOURCE = AudioPortChooser.ROLE_SOURCE;
    private static final int SINK = AudioPortChooser.ROLE_SINK;
    private static final int IN_HDMI = 0x80000010;
    private static final int OUT_SPEAKER = 0x2;

    @Test
    public void picksTheHdmiInputWithTheAlsaAddress() {
        int[] roles = {SINK, SOURCE, SOURCE};
        int[] types = {OUT_SPEAKER, 0x80000004, IN_HDMI};
        String[] addresses = {"", "", "CARD_1_DEV_0"};
        assertEquals(2, AudioPortChooser.pick(roles, types, addresses, SOURCE, IN_HDMI, "CARD_1_DEV_0"));
    }

    @Test
    public void anyAddressWhenNoneIsWanted() {
        int[] roles = {SINK, SINK};
        int[] types = {0x4, OUT_SPEAKER};
        String[] addresses = {"", ""};
        assertEquals(1, AudioPortChooser.pick(roles, types, addresses, SINK, OUT_SPEAKER, null));
    }

    @Test
    public void wrongRoleOrAddressIsNotChosen() {
        int[] roles = {SINK, SOURCE};
        int[] types = {IN_HDMI, IN_HDMI};
        String[] addresses = {"CARD_1_DEV_0", "CARD_2_DEV_0"};
        assertEquals(-1, AudioPortChooser.pick(roles, types, addresses, SOURCE, IN_HDMI, "CARD_1_DEV_0"));
    }
}
