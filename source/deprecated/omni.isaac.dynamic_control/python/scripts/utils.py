# SPDX-FileCopyrightText: Copyright (c) 2021-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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

from pxr import Usd


def set_scene_physics_type(gpu=False, scene_path="/physicsScene"):
    import omni
    from pxr import Gf, PhysxSchema, UsdGeom, UsdPhysics

    stage = omni.usd.get_context().get_stage()
    scene = stage.GetPrimAtPath(scene_path)
    if not scene:
        scene = UsdPhysics.Scene.Define(stage, scene_path)
        scene.CreateGravityDirectionAttr().Set(Gf.Vec3f(0.0, 0.0, -1.0))
        scene.CreateGravityMagnitudeAttr().Set(9.81 / UsdGeom.GetStageMetersPerUnit(stage))
    physxSceneAPI = PhysxSchema.PhysxSceneAPI.Get(stage, scene_path)

    if physxSceneAPI.GetEnableCCDAttr().HasValue():
        physxSceneAPI.GetEnableCCDAttr().Set(True)
    else:
        physxSceneAPI.CreateEnableCCDAttr(True)

    if physxSceneAPI.GetEnableStabilizationAttr().HasValue():
        physxSceneAPI.GetEnableStabilizationAttr().Set(True)
    else:
        physxSceneAPI.CreateEnableStabilizationAttr(True)

    if physxSceneAPI.GetSolverTypeAttr().HasValue():
        physxSceneAPI.GetSolverTypeAttr().Set("TGS")
    else:
        physxSceneAPI.CreateSolverTypeAttr("TGS")

    if not physxSceneAPI.GetEnableGPUDynamicsAttr().HasValue():
        physxSceneAPI.CreateEnableGPUDynamicsAttr(False)

    if not physxSceneAPI.GetBroadphaseTypeAttr().HasValue():
        physxSceneAPI.CreateBroadphaseTypeAttr("MBP")

    if gpu:
        physxSceneAPI.GetEnableGPUDynamicsAttr().Set(True)
        physxSceneAPI.GetBroadphaseTypeAttr().Set("GPU")
    else:
        physxSceneAPI.GetEnableGPUDynamicsAttr().Set(False)
        physxSceneAPI.GetBroadphaseTypeAttr().Set("MBP")


def set_physics_frequency(frequency=60):
    import carb
    import omni

    omni.timeline.get_timeline_interface().set_time_codes_per_second(frequency)
    omni.timeline.get_timeline_interface().set_target_framerate(frequency)
    carb.settings.get_settings().set_bool("/app/runLoops/main/rateLimitEnabled", True)
    carb.settings.get_settings().set_int("/app/runLoops/main/rateLimitFrequency", int(frequency))
    carb.settings.get_settings().set_int("/persistent/simulation/minFrameRate", int(frequency))


async def simulate(seconds, dc=None, art=None, steps_per_sec=60):
    import omni

    for frame in range(int(steps_per_sec * seconds)):
        if art is not None and dc is not None:
            dc.wake_up_articulation(art)
        await omni.kit.app.get_app().next_update_async()


async def add_cube(stage, path, size, offset, physics=True, mass=0.0) -> Usd.Prim:
    import omni
    from pxr import UsdGeom, UsdPhysics

    cube_geom = UsdGeom.Cube.Define(stage, path)
    cube_prim = stage.GetPrimAtPath(path)
    cube_geom.CreateSizeAttr(size)
    cube_geom.AddTranslateOp().Set(offset)
    await omni.kit.app.get_app().next_update_async()  # Need this to avoid flatcache errors
    if physics:
        rigid_api = UsdPhysics.RigidBodyAPI.Apply(cube_prim)
        rigid_api.CreateRigidBodyEnabledAttr(True)
        if mass > 0:
            mass_api = UsdPhysics.MassAPI.Apply(cube_prim)
            mass_api.CreateMassAttr(mass)
    UsdPhysics.CollisionAPI.Apply(cube_prim)
    await omni.kit.app.get_app().next_update_async()
    return cube_prim
