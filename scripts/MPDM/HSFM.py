import torch
from MPDM.RepulsiveForces import RepulsiveForces


class HSFM:
    def __init__(self, param):
        self.param = param
        self.rep_f = RepulsiveForces(self.param)

    def pose_propagation(self, force, state):
        DT = self.param.DT
        ps = self.param.pedestrians_speed
        rs = self.param.robot_speed
        kphi = self.param.k_angle
        kvphi = self.param.k_v_angle
        vx_vy_uncl = state[:, 3:5] + (force[:, :2] * DT)
        dx_dy = state[:, 3:5] * DT + (force[:, :2] * (DT ** 2)) * 0.5  # is there *0.5 or means **0.5?

        # //apply constrains:
        # torch.sqrt(vx_vy[:,0:1]**2 + vx_vy[:,1:2]**2)

        # TODO: check moving model

        pose_prop_v_unclamped = vx_vy_uncl.norm(dim=1)
        pose_prop_v = torch.clamp(pose_prop_v_unclamped, min=-ps, max=ps)
        pose_prop_v[0] = torch.clamp(pose_prop_v_unclamped[0], min=-rs, max=rs)
        vx_vy = torch.clamp(vx_vy_uncl, min=-ps, max=ps)
        vx_vy[0, :] = torch.clamp(vx_vy_uncl[0, :], min=-rs, max=rs)

        dr = dx_dy.norm(dim=1)  # torch.sqrt(dx_dy[:,0:1]**2 + dx_dy[:,1:2]**2)
        mask = (pose_prop_v * DT < dr)  # * torch.ones(state.shape[0])

        aa = (1. - (pose_prop_v * DT) / dr).view(-1, 1)
        bb = (dx_dy.t() * mask).t()
        dx_dy = dx_dy.clone() - (bb * aa)
        state[:, 0:2] = state[:, 0:2].clone() + dx_dy
        state[:, 3:5] = vx_vy
        # angle propagation
        prev_angle = state[:, 2].clone()
        state[:, 2] += -(kphi * (state[:, 2] - force[:, 2]) - kvphi * state[:,
                                                                      5]) * DT  # angle across force direction + angular speed
        state[:, 5] += state[:, 2] - prev_angle  # new angular speed
        return state

    def calc_cost_function(self, robot_goal, robot_init_pose, agents_state, policy=None):
        a = self.param.a
        b = self.param.b
        e = self.param.e
        robot_pose = agents_state[0, :3].clone()
        robot_speed = agents_state[0, 3:].clone()
        if torch.norm(robot_init_pose - robot_goal) < 1e-6:
            PG = torch.tensor([0.01]) #torch.ones(robot_pose.shape).requires_grad_(True)
        else:
            PG = (robot_pose - robot_init_pose).dot((-robot_init_pose +
                                                     robot_goal) / torch.norm(-robot_init_pose + robot_goal))

        # B = torch.zeros(len(agents_state), 1, requires_grad=False)

        agents_pose = agents_state[:, :2]
        delta = agents_pose - robot_pose[:2] + 1e-6
        norm = -torch.norm(delta, dim=1) / b

        B = torch.exp(norm)  # +0.5
        B = (-a * PG + 1 * B)
        B = B / len(agents_state)
        B = torch.clamp(B, min=0.0002)

        return B

    def calc_forces(self, state, goals):
        rep_force = self.rep_f.calc_rep_forces(
            state[:, 0:2], state[:, 3:5], param_lambda=1)
        # rep_force[0] = 0*rep_force[0]
        attr_force = self.force_goal(state, goals)
        return rep_force, attr_force

    def force_goal(self, input_state, goal):
        num_ped = len(input_state)
        k = self.param.socForcePersonPerson["k"] * torch.ones(num_ped)
        k[0] = self.param.socForceRobotPerson["k"]
        k = k.view(-1, 1)

        ps = self.param.pedestrians_speed
        rs = self.param.robot_speed
        desired_direction = goal[:, 0:3] - input_state[:, 0:3] + 1e-6
        v_desired_x_y_yaw = torch.zeros_like(desired_direction)
        norm_direction_lin = torch.sqrt(desired_direction.clone()[:, 0:1] ** 2 +
                                      desired_direction.clone()[:, 1:2] ** 2)
        norm_direction_rot = desired_direction.clone()[:, 2]

        # v_desired_ = torch.sqrt(v_desired_x_y_yaw.clone()[:, 0]**2+v_desired_x_y_yaw.clone()[:, 1]**2+v_desired_x_y_yaw.clone()[:, 2]**2)
        # torch.sqrt(
        #     v_desired_x_y_yaw.clone()[:, 0]**2 + 
        #     v_desired_x_y_yaw.clone()[:, 1]**2 + 
        #     v_desired_x_y_yaw.clone()[:, 2]**2)
        v_desired_x_y_yaw[1:, 0:2] = desired_direction[1:, 0:2] * ps / norm_direction_lin[1:, 0:2]
        v_desired_x_y_yaw[0, 0:2] = desired_direction[0, 0:2] * ps / norm_direction_lin[0, 0:2]

        # TODO: create param: desired rot speed
        v_desired_x_y_yaw[1:, 2] *= desired_direction[1:, 2] / norm_direction_rot[1:]
        v_desired_x_y_yaw[0, 2] *= desired_direction[0, 2] / norm_direction_rot[0]
        # print (pedestrians_speed)
        F_attr = k * (v_desired_x_y_yaw - input_state[:, 3:])
        return F_attr
