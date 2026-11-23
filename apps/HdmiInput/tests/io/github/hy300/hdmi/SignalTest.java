package io.github.hy300.hdmi;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

/** Estado mostrado na tela a partir do sinal que o serviço de captura informa. */
public class SignalTest {
    @Test
    public void lockedTimingIsVideo() {
        assertEquals(Signal.VIDEO, Signal.of(true, 1920, 1080));
    }

    @Test
    public void cableWithoutTimingIsNoSignal() {
        assertEquals(Signal.NO_SIGNAL, Signal.of(true, 0, 0));
    }

    @Test
    public void noCableIsNoCable() {
        assertEquals(Signal.NO_CABLE, Signal.of(false, 0, 0));
    }

    @Test
    public void someSourcesLockWithoutTheFiveVolts() {
        assertEquals(Signal.VIDEO, Signal.of(false, 1280, 720));
    }
}
