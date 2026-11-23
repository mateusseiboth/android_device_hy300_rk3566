/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <cstdint>
#include <filesystem>
#include <functional>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

// Lógica do HAL de TV input da entrada HDMI do HY300: RK628 (HDMI -> MIPI CSI) -> csi2-dphy0
// -> rkisp-vir0. O sinal (5 V do cabo e resolução) vem do subdev V4L2 do RK628; a imagem, do
// /dev/videoN do rkisp; o áudio, da placa ALSA "rockchiphdmiin". Sem dependência do Android.
namespace hy300::tvinput {

constexpr int32_t kDeviceId = 0;
constexpr int32_t kPortId = 1;
constexpr int32_t kStreamId = 0;
// 'H','3','0','0': marca o sideband deste HAL para quem for consumi-lo (compositor).
constexpr int32_t kSidebandMagic = 0x48333030;

struct HdmiInConfig {
    std::string videoName = "rkisp_mainpath";  // nome do /dev/videoN de captura
    std::string subdevName = "rk628";          // trecho do nome do subdev do RK628
    std::string audioAddress = "CARD_1_DEV_0";  // endereço do HDMI In no audio_policy (ALSA)
    int pollMs = 500;
};

using PropertyGetter = std::function<std::string(const char* name)>;

// ro.vendor.hy300.hdmiin.{video,subdev,audio_address,poll_ms}.
HdmiInConfig buildHdmiInConfig(const PropertyGetter& get);

// "videoN" ou "v4l-subdevN" (kind) de /sys/class/video4linux cujo name contém `name`.
std::optional<std::string> findV4l2Node(const std::filesystem::path& root, std::string_view kind,
                                        std::string_view name);

struct Size {
    int32_t width = 0;
    int32_t height = 0;
    bool operator==(const Size&) const = default;
};

struct SignalState {
    bool cablePresent = false;     // V4L2_CID_DV_RX_POWER_PRESENT
    std::optional<Size> timing;    // VIDIOC_SUBDEV_QUERY_DV_TIMINGS travado
    bool operator==(const SignalState&) const = default;
};

enum class Cable { kUnknown, kConnected, kDisconnected };
Cable toCable(const SignalState& state);

struct StreamConfig {
    int32_t streamId = kStreamId;
    int32_t width = 0;
    int32_t height = 0;
};

// Um stream com a resolução detectada; nenhum sem sinal travado.
std::vector<StreamConfig> buildStreamConfigs(const SignalState& state);

// Guarda o último estado informado ao framework; update() diz se mudou (e o primeiro conta).
class HdmiInTracker {
  public:
    bool update(const SignalState& state);
    const SignalState& current() const { return current_; }

  private:
    std::optional<SignalState> reported_;
    SignalState current_;
};

std::vector<int32_t> buildSidebandInts(const Size& size, uint32_t fourcc);

}  // namespace hy300::tvinput
