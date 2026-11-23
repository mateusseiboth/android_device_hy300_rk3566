/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#define LOG_TAG "hy300-tvinput"

#include <android-base/logging.h>
#include <android-base/properties.h>
#include <android/binder_manager.h>
#include <android/binder_process.h>

#include "HdmiInCore.h"
#include "TvInput.h"

using hy300::tvinput::TvInput;

int main() {
    ABinderProcess_setThreadPoolMaxThreadCount(0);
    const auto config = hy300::tvinput::buildHdmiInConfig(
            [](const char* name) { return android::base::GetProperty(name, ""); });

    // Os números de /dev/videoN e /dev/v4l-subdevN mudam com a ordem de probe; os nomes não.
    const std::filesystem::path sysfs = "/sys/class/video4linux";
    const auto video = hy300::tvinput::findV4l2Node(sysfs, "video", config.videoName);
    const auto subdev = hy300::tvinput::findV4l2Node(sysfs, "v4l-subdev", config.subdevName);
    LOG_IF(WARNING, !video || !subdev) << "entrada HDMI sem nó V4L2 (" << config.videoName
                                       << ", " << config.subdevName << ")";

    auto tvInput = ndk::SharedRefBase::make<TvInput>(
            config, video ? "/dev/" + *video : std::string(),
            subdev ? "/dev/" + *subdev : std::string());
    const std::string instance = std::string(TvInput::descriptor) + "/default";
    CHECK_EQ(AServiceManager_addService(tvInput->asBinder().get(), instance.c_str()), STATUS_OK);
    ABinderProcess_joinThreadPool();
    return EXIT_FAILURE;
}
