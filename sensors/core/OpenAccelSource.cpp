/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#include "OpenAccelSource.h"

#include <fcntl.h>

#include <functional>
#include <map>

#include "IioAccelSource.h"
#include "InputAccelSource.h"
#include "RkGsensorControl.h"

namespace hy300::sensors {
namespace {

using SourceFactory =
        std::function<std::unique_ptr<AccelSource>(const AccelConfig&, const SysfsRoots&)>;

std::unique_ptr<AccelSource> openIio(const AccelConfig& config, const SysfsRoots& roots) {
    const auto device = findIioDevice(roots.iio, config.device);
    if (!device) {
        return nullptr;
    }
    return std::make_unique<IioAccelSource>(*device);
}

std::unique_ptr<AccelSource> openInput(const AccelConfig& config, const SysfsRoots& roots) {
    const auto event = findInputEvent(roots.input, config.device);
    if (!event) {
        return nullptr;
    }
    const int fd = open((roots.devInput / *event).c_str(), O_RDONLY | O_CLOEXEC | O_NONBLOCK);
    if (fd < 0) {
        return nullptr;
    }
    return std::make_unique<InputAccelSource>(fd);
}

const std::map<Backend, SourceFactory>& sourceFactories() {
    static const std::map<Backend, SourceFactory> kFactories = {
            {Backend::kRockchipGsensor, openInput},
            {Backend::kInput, openInput},
            {Backend::kIio, openIio},
    };
    return kFactories;
}

}  // namespace

std::unique_ptr<AccelSource> openAccelSource(const AccelConfig& config,
                                             const SysfsRoots& roots) {
    return sourceFactories().at(config.backend)(config, roots);
}

std::unique_ptr<AccelControl> openAccelControl(const AccelConfig& config) {
    if (config.backend != Backend::kRockchipGsensor) {
        return nullptr;
    }
    return std::make_unique<RkGsensorControl>(config.control);
}

}  // namespace hy300::sensors
