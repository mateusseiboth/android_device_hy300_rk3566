/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

package vendor.hy300.hdmiin;

/** Estado da entrada HDMI (RK628): 5 V do cabo e a resolução travada (0 sem sinal). */
@VintfStability
parcelable HdmiSignal {
    boolean cablePresent;
    int width;
    int height;
}
