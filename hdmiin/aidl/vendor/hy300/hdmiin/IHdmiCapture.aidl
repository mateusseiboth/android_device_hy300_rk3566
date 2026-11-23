/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

package vendor.hy300.hdmiin;

import android.view.Surface;
import vendor.hy300.hdmiin.HdmiSignal;

/**
 * Captura da entrada HDMI do HY300 para uma Surface do app de TV input: o serviço do vendor lê o
 * /dev/video do rkisp e copia cada quadro pela RGA para os buffers da Surface. A imagem vira uma
 * camada comum do SurfaceFlinger (keystone e BCSH valem sobre ela).
 */
@VintfStability
interface IHdmiCapture {
    HdmiSignal getSignal();

    /** Começa (ou troca a Surface de) a prévia; segue a resolução da fonte sozinho. */
    void startPreview(in Surface surface);

    void stopPreview();
}
