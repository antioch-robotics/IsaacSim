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
import re
from typing import Optional

import carb
import numpy as np
from isaacsim.core.api.robots.robot import Robot
from isaacsim.core.utils.prims import define_prim, get_prim_at_path
from isaacsim.core.utils.types import ArticulationAction


class WheeledRobot(Robot):
    """
    This class wraps and manages the articualtion for a two wheeled differential robot base. It is designed to be managed by the `World` simulation context and provides and API for applying actions, retrieving dof parameters, etc...

    Creating a wheeled robot can be done in a number of different ways, depending on the use case.

    * Most commonly, the robot and stage are preloaded, in which case only the prim path to the articualtion root and the joint labels are required. Joint labels can take the form of either the joint names or the joint indices in the articulation.

    .. code-block:: python

        jetbot = WheeledRobot(prim_path="/path/to/jetbot",
                            name="Joan",
                            wheel_dof_names=["left_wheel_joint", "right_wheel_joint"]
                            )

        armbot = WheeledRobot(prim_path="path/to/armbot"
                                name="Weird_Arm_On_Wheels_Bot",
                                wheel_dof_indices=[7, 8]
                            )

    * Alternatively, this class can create and populate a new reference on the stage.  This is done with the `create_robot` parameter set to True.

    .. code-block:: python

        carter = WheeledRobot(prim_path="/desired/path/to/carter",
                                name = "Jimmy",
                                wheel_dof_names=["joint_wheel_left", "joint_wheel_right"],
                                create_robot = True,
                                usd_path = "/Isaac/Robots/NVIDIA/NovaCarter/nova_carter.usd",
                                position = np.array([0,1,0])
                            )

    .. hint::

        In all cases, either `wheel_dof_names` or `wheel_dof_indices` must be specified!


    Args:
        prim_path (str): The stage path to the root prim of the articulation.
        name ([str]): The name used by `World` to identify the robot. Defaults to "wheeled_robot"
        robot_path (optional[str]): relative path from prim path to the robot.
        wheel_dof_names (semi-optional[str]): names of the wheel joints. Either this or the wheel_dof_indicies must be specified.
        wheel_dof_indices: (semi-optional[int]): indices of the wheel joints in the articulation. Either this or the wheel_dof_names must be specified.
        usd_path (optional[str]): nucleus path to the robot asset. Used if create_robot is True
        create_robot (bool): create robot at prim_path using asset from usd_path. Defaults to False
        position (Optional[np.ndarray], optional): The location to create the robot when create_robot is True. Defaults to None.
        orientation (Optional[np.ndarray], optional): The orientation of the robot when crate_robot is True. Defaults to None.
    """

    def __init__(
        self,
        prim_path: str,
        name: str = "wheeled_robot",
        robot_path: Optional[str] = None,
        wheel_dof_names: Optional[str] = None,
        wheel_dof_indices: Optional[int] = None,
        usd_path: Optional[str] = None,
        create_robot: Optional[bool] = False,
        position: Optional[np.ndarray] = None,
        orientation: Optional[np.ndarray] = None,
    ) -> None:
        prim = get_prim_at_path(prim_path)
        if not prim.IsValid():
            if create_robot:
                prim = define_prim(prim_path, "Xform")
                if usd_path:
                    prim.GetReferences().AddReference(usd_path)
                else:
                    carb.log_error("no valid usd path defined to create new robot")
            else:
                carb.log_error("no prim at path %s", prim_path)

        if robot_path is not None:
            robot_path = "/" + robot_path
            # regex: remove all prefixing "/", need at least one prefix "/" to work
            robot_path = re.sub("^([^\/]*)\/*", "", "/" + robot_path)
            prim_path = prim_path + "/" + robot_path

        super().__init__(
            prim_path=prim_path, name=name, position=position, orientation=orientation, articulation_controller=None
        )
        self._wheel_dof_names = wheel_dof_names
        self._wheel_dof_indices = wheel_dof_indices
        # TODO: check the default state and how to reset
        return

    @property
    def wheel_dof_indices(self):
        """[summary]

        Returns:
            int: [description]
        """
        return self._wheel_dof_indices

    def get_wheel_positions(self):
        """[summary]

        Returns:
            List[float]: [description]
        """
        full_dofs_positions = self.get_joint_positions()
        wheel_joint_positions = [full_dofs_positions[i] for i in self._wheel_dof_indices]
        return wheel_joint_positions

    def set_wheel_positions(self, positions) -> None:
        """[summary]

        Args:
            positions (Tuple[float, float]): [description]
        """
        full_dofs_positions = [None] * self.num_dof
        for i in range(self._num_wheel_dof):
            full_dofs_positions[self._wheel_dof_indices[i]] = positions[i]
        self.set_joint_positions(positions=np.array(full_dofs_positions))
        return

    def get_wheel_velocities(self):
        """[summary]

        Returns:
            Tuple[np.ndarray, np.ndarray]: [description]
        """

        full_dofs_velocities = self.get_joint_velocities()
        wheel_dof_velocities = [full_dofs_velocities[i] for i in self._wheel_dof_indices]
        return wheel_dof_velocities

    def set_wheel_velocities(self, velocities) -> None:
        """[summary]

        Args:
            velocities (Tuple[float, float]): [description]
        """
        full_dofs_velocities = [None] * self.num_dof
        for i in range(self._num_wheel_dof):
            full_dofs_velocities[self._wheel_dof_indices[i]] = velocities[i]
        self.set_joint_velocities(velocities=np.array(full_dofs_velocities))
        return

    def apply_wheel_actions(self, actions: ArticulationAction) -> None:
        """applying action to the wheels to move the robot

        Args:
            actions (ArticulationAction): [description]
        """
        actions_length = actions.get_length()
        if actions_length is not None and actions_length != self._num_wheel_dof:
            raise Exception("ArticulationAction passed should be the same length as the number of wheels")
        joint_actions = ArticulationAction()
        if actions.joint_positions is not None:
            joint_actions.joint_positions = np.zeros(self.num_dof)  # for all dofs of the robot
            for i in range(self._num_wheel_dof):  # set only the ones that are the wheels
                joint_actions.joint_positions[self._wheel_dof_indices[i]] = actions.joint_positions[i]
        if actions.joint_velocities is not None:
            joint_actions.joint_velocities = np.zeros(self.num_dof)
            for i in range(self._num_wheel_dof):
                joint_actions.joint_velocities[self._wheel_dof_indices[i]] = actions.joint_velocities[i]
        if actions.joint_efforts is not None:
            joint_actions.joint_efforts = np.zeros(self.num_dof)
            for i in range(self._num_wheel_dof):
                joint_actions.joint_efforts[self._wheel_dof_indices[i]] = actions.joint_efforts[i]
        self.apply_action(control_actions=joint_actions)
        return

    def initialize(self, physics_sim_view=None) -> None:
        """[summary]"""
        super().initialize(physics_sim_view=physics_sim_view)
        if self._wheel_dof_names is not None:
            self._wheel_dof_indices = [
                self.get_dof_index(self._wheel_dof_names[i]) for i in range(len(self._wheel_dof_names))
            ]
        elif self._wheel_dof_indices is None:
            carb.log_error("need to have either wheel names or wheel indices")

        self._num_wheel_dof = len(self._wheel_dof_indices)

        return

    def post_reset(self) -> None:
        """[summary]"""
        super().post_reset()
        self._articulation_controller.switch_control_mode(mode="velocity")
        return

    def get_articulation_controller_properties(self):
        return self._wheel_dof_names, self._wheel_dof_indices
