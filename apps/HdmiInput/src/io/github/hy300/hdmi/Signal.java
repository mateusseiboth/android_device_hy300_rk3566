package io.github.hy300.hdmi;

/** O que a entrada HDMI tem agora. */
enum Signal {
    VIDEO, NO_SIGNAL, NO_CABLE;

    /** Resolução travada vale mais que o 5 V: algumas fontes não acionam o detector do cabo. */
    static Signal of(boolean cablePresent, int width, int height) {
        if (width > 0 && height > 0) return VIDEO;
        return cablePresent ? NO_SIGNAL : NO_CABLE;
    }
}
