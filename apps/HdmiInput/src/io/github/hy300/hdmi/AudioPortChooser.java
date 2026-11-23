package io.github.hy300.hdmi;

/** Escolhe uma porta de áudio pelo papel, tipo de dispositivo e endereço ALSA (sem Android, testável). */
final class AudioPortChooser {
    /** Valores de android.media.AudioPort.ROLE_*. */
    static final int ROLE_SOURCE = 1;
    static final int ROLE_SINK = 2;

    private AudioPortChooser() {}

    /** Índice da primeira porta que casa; -1 se nenhuma. Endereço nulo aceita qualquer um. */
    static int pick(int[] roles, int[] types, String[] addresses, int role, int type, String address) {
        for (int i = 0; i < roles.length; i++) {
            boolean addressMatches = address == null || address.equals(addresses[i]);
            if (roles[i] == role && types[i] == type && addressMatches) return i;
        }
        return -1;
    }
}
