from MPDM.optimization import Linear
import torch.nn as nn
import torch
import numpy as np
import math


class MPDM:
    def __init__(self, param, sfm, policys=None):
        self.param = param
        self.map = None
        self.goals = None
        self.policys = policys
        self.sfm = sfm
        self.modules = []
        self.path = None
        self.states = None
        ###### MODEL CREATING ######
        for i in range(0, self.param.number_of_layers):
            self.modules.append(Linear(self.sfm))
        self.sequential = nn.Sequential(*self.modules)

    def is_init(self):
        return self.states is not None

    def update_state(self, robot, peds, robot_goal, peds_goals, map=None):
        try:
            states = []
            goals = []
            self.map = map
            states.append(robot)
            goals.append(robot_goal)
            for i in range(len(peds)):
                states.append(peds[i])
                goals.append(goals[i])
            states = np.array(states)
            goals = np.array(goals)
            self.goals = torch.from_numpy(goals)
            self.states = torch.from_numpy(states)
            # TODO: convert to tensor
        except:
            self.states = None
        # [
        # robot [x,y,yaw,vx,vy,vyaw],
        # ped1 [x,y,yaw,vx,vy,vyaw],
        # ped2 [x,y,yaw,vx,vy,vyaw],
        # ...
        # ]

    def predict(self, epoch=20):
        # TODO: try to work without 0) policys 1) map 2) goals 3) peds
        # only for test
        # self.robot =
        # only for test

        cost, states = self.optimize(epoch)
        self.path = None # TODO: fix it
        return True

    def get_robot_path(self,):
        return self.path

    def optimize(self, epochs):
        if self.states is None:
            return None

        for epoch_numb in range(0, epochs):
            max_cost = -math.inf
            # inner_data = self.states.clone().detach()  # TODO: why copy and detach twice ?
            # inner_data = np.append(inner_data[:,:2],inner_data[:,3:5], axis=1)
            # luti pizdec
            inner_data = torch.from_numpy(np.append(self.states[:, :2].clone().detach(
            ), self.states[:, 3:5].clone().detach(), axis=1)).clone().detach()
            inner_data.requires_grad_(True)
            goals = self.goals[:, :2].clone().detach()
            goals.requires_grad_(True)
            robot_init_pose = inner_data[0, 0:2]
            stacked_trajectories_for_visualizer = None  # ???
            ### FORWARD PASS ####
            cost = torch.zeros(len(inner_data-1), 1).requires_grad_(True)
            probability_matrix, goal_prob, vel_prob = self.get_probability(
                inner_data, goals, self.param)
            # goal_prob[0] = 1. # what?
            _, cost, stacked_trajectories_for_visualizer, _, _, _ = self.sequential(
                (inner_data, cost, stacked_trajectories_for_visualizer, goals, robot_init_pose, self.policys))

            # print (goals)
            #### VISUALIZE ####
            # if param.do_visualization and None not in [ped_goals_visualizer, initial_pedestrians_visualizer, pedestrians_visualizer, robot_visualizer, learning_vis, initial_ped_goals_visualizer]:
            #     ped_goals_visualizer.publish(goals)
            #     # initial_pedestrians_visualizer.publish(observed_state)
            #     pedestrians_visualizer.publish(starting_poses[1:])
            #     robot_visualizer.publish(starting_poses[0:1])
            #     learning_vis.publish(stacked_trajectories_for_visualizer)
            #     initial_ped_goals_visualizer.publish(param.goal)

            #### CALC GRAD ####

            prob_cost = cost * (probability_matrix) * (goal_prob) * vel_prob

            prob_cost.sum().backward()
            total_cost = prob_cost.sum().item()
            if total_cost > max_cost:
                max_cost = total_cost
                max_cost_state = inner_data.clone().detach()
            gradient = inner_data.grad
            gradient[0, :] *= 0

            if gradient is not None:
                with torch.no_grad():

                    delta_pose = self.param.lr * gradient[1:, 0:2]
                    delta_vel = 100*self.param.lr * gradient[1:, 2:4]
                    delta_pose = torch.clamp(delta_pose, max=0.01, min=-0.01)
                    delta_vel = torch.clamp(delta_vel, max=0.02, min=-0.02)
                    # starting_poses[1:, 0:2] = starting_poses[1:,
                    #                                          0:2] + delta_pose
                    # starting_poses[1:, 2:4] = starting_poses[1:,
                    #                                          2:4] + delta_vel
                    goals.grad[0, :] = goals.grad[0, :] * 0

                    goals = (goals + torch.clamp(self.param.lr * 10 * goals.grad,
                                                 max=0.2, min=-0.2))  # .requires_grad_(True)

            goals.requires_grad_(True)

            if goals.grad is not None:
                goals.grad.data.zero_()
            if inner_data.grad is not None:
                inner_data.grad.data.zero_()
            # if starting_poses.grad is not None:
            #     starting_poses.grad.data.zero_()
        return max_cost, max_cost_state

    def get_probability(self, inner_data, goals, param):

        # pose
        num_ped = len(inner_data)  # -1
        input_state_std = param.pose_std_coef * torch.rand((num_ped, 4))
        input_state_std[:, 2:4] = param.velocity_std_coef * \
            torch.rand((num_ped, 2))
        agents_pose_distrib = torch.distributions.normal.Normal(
            inner_data, input_state_std)
        index_X, index_Y = 0, 1
        probability = torch.exp(agents_pose_distrib.log_prob(
            inner_data)) * torch.sqrt(2 * math.pi * agents_pose_distrib.stddev**2)
        probability_ = 0.5*(probability[:, index_X] + probability[:, index_Y])
        probability_matrix = probability_.view(-1, 1).requires_grad_(True)
        # velocity
        index_X, index_Y = 2, 3
        probability_ = 0.5*(probability[:, index_X] + probability[:, index_Y])
        vel_prob = probability_.view(-1, 1).requires_grad_(True)

        # goal
        goal_std = param.goal_std_coef * torch.rand((num_ped, 2))
        goal_distrib = torch.distributions.normal.Normal(goals, goal_std)
        index_X, index_Y = 0, 1
        probability = torch.exp(goal_distrib.log_prob(
            goals)) * torch.sqrt(2 * math.pi * goal_distrib.stddev**2)
        probability_ = 0.5*(probability[:, index_X] + probability[:, index_Y])
        goal_prob = probability_.view(-1, 1).requires_grad_(True)

        agents_pose_distrib
        return probability_matrix, goal_prob, vel_prob
