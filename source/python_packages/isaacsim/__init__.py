# SPDX-FileCopyrightText: Copyright (c) 2018-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import ctypes
import glob
import os
import sys


def bootstrap_kernel():
    using_inner_kernel = False

    # isaac-sim path
    isaacsim_path = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))

    # check if it is a non-Python package manager installation
    split_path = isaacsim_path.split(os.sep)
    if len(split_path) >= 2 and split_path[-1] == "isaacsim" and split_path[-2] == "python_packages":
        return

    # kit path (internal kernel)
    if os.path.isdir(os.path.join(isaacsim_path, "kit", "extscore")):
        kit_path = os.path.join(isaacsim_path, "kit")
        using_inner_kernel = True
    # kit path (omniverse-kit kernel package)
    else:
        try:
            import omni.kit_app  # importing 'omni.kit_app' will bootstrap kernel

            kit_path = os.path.dirname(os.path.abspath(os.path.realpath(omni.kit_app.__file__)))
        except ModuleNotFoundError:
            print("Unable to find 'omniverse-kit' package")
            exit()

    # preload libcarb.so
    if using_inner_kernel:
        carb_library = "carb.dll" if sys.platform == "win32" else "libcarb.so"
        ctypes.PyDLL(os.path.join(kit_path, carb_library), mode=ctypes.RTLD_GLOBAL)

    # set environment variables
    if not os.environ.get("CARB_APP_PATH", None):
        os.environ["CARB_APP_PATH"] = kit_path
    if not os.environ.get("EXP_PATH", None):
        os.environ["EXP_PATH"] = os.path.join(isaacsim_path, "apps")
    if not os.environ.get("ISAAC_PATH", None):
        os.environ["ISAAC_PATH"] = os.path.join(isaacsim_path)

    # set environment variables (Jupyter)
    if os.environ.get("JPY_PARENT_PID", None):
        os.environ["ISAAC_JUPYTER_PYTHON_PACKAGE"] = "1"

    # set PYTHONPATH
    paths = []
    # kit
    if using_inner_kernel:
        paths += [
            os.path.join(kit_path, "kernel", "py"),
        ]
    # isaac-sim
    paths += [
        os.path.join(isaacsim_path, "exts", "isaacsim.simulation_app"),
        os.path.join(isaacsim_path, "extsDeprecated", "omni.isaac.kit"),
    ]
    # update sys.path
    for path in paths:
        if not path in sys.path:
            if not os.path.exists(path):
                print(f"PYTHONPATH: path doesn't exist ({path})")
                continue
            sys.path.insert(0, path)

    # log info
    import carb

    carb.log_info(f"Isaac Sim path: {isaacsim_path}")
    carb.log_info(f"Kit path: {kit_path}")
    carb.log_info(f"Using inner kernel: {using_inner_kernel}")


def expose_api():
    AppFramework, SimulationApp = None, None
    try:
        # try a direct import
        from isaacsim.simulation_app import AppFramework, SimulationApp
    except ImportError:
        # try to import API from isaacsim/simulation_app folder instead
        try:
            # get isaacsim/simulation_app folder path
            isaacsim_path = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
            path = glob.glob(
                os.path.join(
                    os.environ.get("ISAAC_PATH", isaacsim_path), "exts*", "isaacsim.simulation_app*", "isaacsim"
                )
            )[0]
            if os.path.exists(path):
                # register path
                sys.path.insert(0, path)
                # import API
                from simulation_app import AppFramework, SimulationApp

                # register module to support 'from isaacsim.simulation_app import SimulationApp'
                sys.modules["isaacsim.simulation_app"] = type(sys)("isaacsim.simulation_app")
                sys.modules["isaacsim.simulation_app.SimulationApp"] = SimulationApp
                sys.modules["isaacsim.simulation_app.AppFramework"] = AppFramework
            else:
                print(f"PYTHONPATH: path doesn't exist ({path})")
        except ImportError as e:
            print(f"Unable to expose 'isaacsim.simulation_app' API: {e}")
    return AppFramework, SimulationApp


def main():
    args = sys.argv[1:]
    using_inner_kernel = False

    # get paths
    # isaac-sim path
    isaacsim_path = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
    # kit path (internal kernel)
    if os.path.isdir(os.path.join(isaacsim_path, "kit", "extscore")):
        kit_path = os.path.join(isaacsim_path, "kit")
        using_inner_kernel = True
    # kit path (omniverse-kit kernel package)
    else:
        try:
            import omni.kit_app  # importing 'omni.kit_app' will bootstrap kernel

            kit_path = os.path.dirname(os.path.abspath(os.path.realpath(omni.kit_app.__file__)))
        except ModuleNotFoundError:
            print("Unable to find 'omniverse-kit' package")
            exit()

    # experience file
    experience = args[0] if len(args) and not args[0].startswith("-") else "isaacsim.exp.full"
    experience = experience if experience.endswith(".kit") else f"{experience}.kit"
    if not os.path.isfile(experience):
        for experience_dir in [os.path.join(isaacsim_path, "apps"), os.path.join(kit_path, "apps")]:
            if os.path.isfile(os.path.join(experience_dir, experience)):
                experience = os.path.join(experience_dir, experience)
                if len(args) and not args[0].startswith("-"):
                    args = args[1:]
                break
    if not os.path.isfile(experience):
        print(f"Invalid experience (.kit) file: {args[0] if len(args) else ''}")
        exit()

    # launch app
    if using_inner_kernel:
        sys.path.append(kit_path)
        from kit_app import KitApp
    else:
        from omni.kit_app import KitApp

    app = KitApp()
    app.startup([experience, "--ext-folder", os.path.join(isaacsim_path, "apps")] + args)
    while app.is_running():
        app.update()
    sys.exit(app.shutdown())


bootstrap_kernel()

# make isaacsim.simulation_app discoverable
AppFramework, SimulationApp = expose_api()
