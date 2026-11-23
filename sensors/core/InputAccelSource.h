/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <filesystem>
#include <optional>
#include <string>
#include <string_view>

#include "AccelSource.h"

namespace hy300::sensors {

// "eventN" de /sys/class/input cujo device/name é `name` (o /dev/input/eventN muda de número
// conforme a ordem de probe; o nome não).
std::optional<std::string> findInputEvent(const std::filesystem::path& root,
                                          std::string_view name);

// Lê um dispositivo de input com ABS_X/Y/Z (valores crus). A amostra só vale depois do
// SYN_REPORT; SYN_DROPPED descarta o que veio até o próximo SYN_REPORT. Fica com o fd.
class InputAccelSource : public AccelSource {
  public:
    explicit InputAccelSource(int fd);
    ~InputAccelSource() override;

    InputAccelSource(const InputAccelSource&) = delete;
    InputAccelSource& operator=(const InputAccelSource&) = delete;

    std::optional<Vec3> read() override;
    bool isScaled() const override { return false; }

  private:
    void handleEvent(unsigned type, unsigned code, int value);

    int fd_;
    Vec3 pending_;
    bool dropping_ = false;
    std::optional<Vec3> last_;
};

}  // namespace hy300::sensors
