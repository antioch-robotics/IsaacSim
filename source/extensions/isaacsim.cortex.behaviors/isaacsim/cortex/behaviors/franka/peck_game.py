# SPDX-FileCopyrightText: Copyright (c) 2022-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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

""" This script gives an example of a behavior programmed entirely as a decider network (no state
machines). The behavior will monitor the blocks for movement, and whenever a block moves it will
reach down and peck it. It will always switch to the most recently moved block, aborting its
previous peck behavior if a new block is moved.

The top level Dispatch decider has three actions: peck, lift, and go_home. See the Dispatch
decider's decide() method for the specific implementation of choice of action. Simply put, if
there's an active block, then peck at it. If it doesn't have an active block, and it's currently too
close to the block, then lift a bit away from it. Otherwise, if none of that is true, just go home.

Crticial to the simplicity of this decision description is the monitoring of the relevant logical
information. The context object sets up a collection of monitors which monitor whether there's an
active block (one that's been moved, but hasn't yet been pecked), and whether the end-effector is
close to a block.

Note that the active block is automatically detected as the latest block that's moved. Likewise, the
context monitors also simply monitor to see whether that block is touched by the end-effector. When
the monitor observes that the active block has been touched, it deactivates the block. This
separation between observability and choice of action to make an observable change is a core
principle in decider network design for inducing reactivitiy.
"""

import time

import isaacsim.cortex.framework.math_util as math_util
import numpy as np
from isaacsim.cortex.framework.df import DfAction, DfDecider, DfDecision, DfLogicalState, DfNetwork
from isaacsim.cortex.framework.dfb import DfCloseGripper, DfLift, DfRobotApiContext, make_go_home
from isaacsim.cortex.framework.motion_commander import ApproachParams, MotionCommand, PosePq


class PeckContext(DfRobotApiContext):
    def __init__(self, robot):
        super().__init__(robot)
        self.diagnostics_message = ""
        self.add_monitors(
            [
                PeckContext.monitor_block_movement,
                PeckContext.monitor_active_target_p,
                PeckContext.monitor_active_block,
                PeckContext.monitor_eff_block_proximity,
                PeckContext.monitor_diagnostics,
            ]
        )

    def reset(self):
        self.blocks = []
        for _, block in self.robot.registered_obstacles.items():
            self.blocks.append(block)

        self.block_positions = self.get_latest_block_positions()
        self.active_block = None
        self.active_target_p = None
        self.is_eff_close_to_inactive_block = None

        self.time_at_last_diagnostics_print = None

    @property
    def has_active_block(self):
        return self.active_block is not None

    def clear_active_block(self):
        self.active_block = None
        self.active_target_p = None

    def get_latest_block_positions(self):
        block_positions = []
        for block in self.blocks:
            block_p, _ = block.get_world_pose()
            block_positions.append(block_p)
        return block_positions

    def monitor_block_movement(self):
        block_positions = self.get_latest_block_positions()
        for i in range(len(block_positions)):
            if np.linalg.norm(block_positions[i] - self.block_positions[i]) > 0.01:
                self.block_positions[i] = block_positions[i]
                self.active_block = self.blocks[i]

    def monitor_active_target_p(self):
        if self.active_block is not None:
            p, _ = self.active_block.get_world_pose()
            self.active_target_p = p + np.array([0.0, 0.0, 0.0325])

    def monitor_active_block(self):
        if self.active_target_p is not None:
            eff_p = self.robot.arm.get_fk_p()
            dist = np.linalg.norm(eff_p - self.active_target_p)
            if np.linalg.norm(eff_p - self.active_target_p) < 0.01:
                self.clear_active_block()

    def monitor_eff_block_proximity(self):
        self.is_eff_close_to_inactive_block = False

        eff_p = self.robot.arm.get_fk_p()
        for block in self.blocks:
            if block != self.active_block:
                block_p, _ = block.get_world_pose()
                if np.linalg.norm(eff_p - block_p) < 0.07:
                    self.is_eff_close_to_inactive_block = True
                    return

    def monitor_diagnostics(self):
        now = time.time()
        if self.time_at_last_diagnostics_print is None or (now - self.time_at_last_diagnostics_print) >= 1.0:
            if self.active_block is not None:
                self.diagnostics_message = f"active block:{self.active_block.name}"
            else:
                self.diagnostics_message = "No Active Block"
            self.time_at_last_diagnostics_print = now


class PeckAction(DfAction):
    def enter(self):
        self.block = self.context.active_block
        self.context.robot.arm.disable_obstacle(self.block)

    def step(self):
        target_p = self.context.active_target_p
        target_q = math_util.matrix_to_quat(
            math_util.make_rotation_matrix(az_dominant=np.array([0.0, 0.0, -1.0]), ax_suggestion=-target_p)
        )
        target = PosePq(target_p, target_q)
        approach_params = ApproachParams(direction=np.array([0.0, 0.0, -0.1]), std_dev=0.04)

        # Send the command each cycle so exponential smoothing will converge.
        self.context.robot.arm.send_end_effector(target, approach_params=approach_params)
        target_dist = np.linalg.norm(self.context.robot.arm.get_fk_p() - target.p)

    def exit(self):
        self.context.robot.arm.enable_obstacle(self.block)


class Dispatch(DfDecider):
    def enter(self):
        self.add_child("peck", PeckAction())
        self.add_child("lift", DfLift(height=0.1))
        self.add_child("go_home", make_go_home())

    def decide(self):
        if self.context.is_eff_close_to_inactive_block:
            return DfDecision("lift")

        if self.context.has_active_block:
            return DfDecision("peck")

        # If we aren't doing anything else, always just go home.
        return DfDecision("go_home")


def make_decider_network(robot):
    return DfNetwork(Dispatch(), context=PeckContext(robot))
