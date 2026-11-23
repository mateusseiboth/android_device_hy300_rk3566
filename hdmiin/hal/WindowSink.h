/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <android/native_window.h>

#include "PreviewPump.h"

namespace hy300::hdmiin {

// Buffers da Surface do app (BufferQueue do SurfaceFlinger): RGBA 8888 no tamanho da captura,
// para a GPU e o compositor. A escala para a tela é do SurfaceFlinger (com o keystone).
class WindowSink : public FrameSink {
  public:
    explicit WindowSink(ANativeWindow* window);
    ~WindowSink() override;

    WindowSink(const WindowSink&) = delete;
    WindowSink& operator=(const WindowSink&) = delete;

    bool setGeometry(uint32_t width, uint32_t height);
    std::optional<GraphicTarget> dequeue() override;
    void queue(const GraphicTarget& target) override;
    void cancel(const GraphicTarget& target) override;

  private:
    ANativeWindow* window_;
};

}  // namespace hy300::hdmiin
