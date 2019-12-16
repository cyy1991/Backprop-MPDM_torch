import torch

input_state  = torch.tensor(([2.0,0.5,0.0,-1.],[2.0,0.5,0.0,-1.]))#, [1.0,2.5,0.0,0.0]) )
k = 2.2
DT = 0.2
pedestrians_speed = 0.5




def force_goal(input_state, goal):
	global pedestrians_speed

	# v_desired_x =  goal[:,0:1]  - input_state[:,0:1] 
	# v_desired_y =  goal[:,1:2]  - input_state[:,1:2] 
	v_desired_x_y =  goal[:,0:2]  - input_state[:,0:2] 

	v_desired_ = torch.sqrt(v_desired_x_y.clone()[:,0:1]**2 + v_desired_x_y.clone()[:,1:2]**2)
	v_desired_x_y *= pedestrians_speed / v_desired_
	# F_attr =torch.tensor([ k * (v_desired_x - input_state[:,2:3]), k * (v_desired_y - input_state[:,3:4]) ] )
	# F_attr = k * ( pedestrians_speed * ( (goal[:,0:2] - input_state[:,0:2]) / (goal[:,0:2] - input_state[:,0:2]).norm())) - input_state[:,2:4]
	F_attr = k * (v_desired_x_y - input_state[:,2:4])
	return F_attr

def pose_propagation(force, state):
	
	# vx = pose.v*cos(pose.theta) + force.fx*dt
	# vy = pose.v*sin(pose.theta) + force.fy*dt
	vx_vy_uncl = state[:,2:4] + (force*DT)
	dx_dy = state[:,2:4]*DT + (force*(DT**2))*0.5
	
	# dx = pose.v*cos(pose.theta)*dt + force.fx*dt*dt*0.5
	# dy = pose.v*sin(pose.theta)*dt + force.fy*dt*dt*0.5

	# //apply constrains:
	pose_prop_v_unclamped = vx_vy_uncl.norm(dim=1) #torch.sqrt(vx_vy[:,0:1]**2 + vx_vy[:,1:2]**2)
	pose_prop_v = torch.clamp(pose_prop_v_unclamped, max=pedestrians_speed)
	vx_vy = torch.clamp(vx_vy_uncl, max=pedestrians_speed)
	
	# pose_prop.v = sqrt( vx*vx + vy*vy )
	# if (pose_prop_v > pedestrians_speed):
	# 	pose_prop_v = torch.ones(pose_prop_v.shape) * pedestrians_speed
	dr = dx_dy.norm(dim=1)#torch.sqrt(dx_dy[:,0:1]**2 + dx_dy[:,1:2]**2)
	mask = (pose_prop_v * DT < dr) #* torch.ones(state.shape[0])
	# print ("mask ", mask)
	# print ("	dx_dy before ", dx_dy)
	# print ("	dx_dy.t()*mask).t() ", (dx_dy.t()*mask).t())
	# print ("	(dx_dy.t()*mask).t() * (1  - (  pose_prop_v * DT) / dr))\n	", ( (dx_dy.t()*mask).t() * (1  - (  pose_prop_v * DT) / dr)))
	# dx_dy[mask] = dx_dy[mask].clone() * pose_prop_v * DT / dr
	aa = (1.  - (  pose_prop_v * DT) / dr).view(-1,1)
	bb = (dx_dy.t()*mask).t()
	# print("aa ", aa)
	# print("bb ", bb)
	dx_dy = dx_dy.clone()  - ( bb * aa)

	# print ("	dx_dy after ", dx_dy)
	# if ( pose_prop_v * DT < dr ):
	# 	dx_dy = dx_dy.clone() *  pose_prop_v * DT / dr
	state[:,0:2] = state[:,0:2].clone() + dx_dy

	state[:,2:4] =  vx_vy
	# print ("F_attr ", force)
	# print("vx_vy ", vx_vy)
	# print ("state ", state) 
	# print ()
	# pose_prop.x = pose.x + dx
	# pose_prop.y = pose.y + dy
	# pose_prop.theta = atan2( dy, dx)
	# pose.w = ( pose_prop.theta - pose.theta ) / dt
	# pose_prop.time_stamp = pose.time_stamp + dt
	return state



def limit_speed(input_state, limit):

    ampl = torch.sqrt(input_state[:,0:1]**2 + input_state[:,1:2]**2)
    
    mask=torch.cat((ampl>limit,ampl>limit),dim=1)
    ampl_2D = torch.cat((ampl,ampl),dim=1)
    input_state[mask] = input_state[mask].clone() * limit / ampl_2D[mask]
    return input_state

def is_goal_achieved(state, goals):
    is_achieved = state[:,0:2] - goals
    is_achieved = torch.sqrt(is_achieved[:,0]**2 + is_achieved[:,1]**2)
    return is_achieved<0.3

def generate_new_goal(goals, is_achived, input_state):
    
    for i in range (is_achived.shape[0]):
        if is_achived[i].item() == True:
            goals[i,0] = 20*torch.rand(1)
            goals[i,1] = 20*torch.rand(1)
    return goals

def calc_new_pose(input):
    input[:,0:2] = input[:,0:2] + input[:,2:4] * DT
    return input

def calc_new_vel(input_state, forces):
    input_state[:,2:4] = (forces / 60.0 * DT  )+ input_state[:,2:4]
    input_state[:,2:4] = limit_speed(input_state[:,2:4], 1.0)
    return input_state





if __name__ == "__main__":

	input_state = input_state.view(-1,4)
	goal = torch.tensor(([4.0,1.0], [4.0,1.0]))#, [2.1,2.2]))
	goal = goal.view(-1,2)

	t = 0
	# plot_data = [[input_state.data[0,0].item()],[input_state.data[0,0].item()],[t]]
	plot_data = [[],[],[]]

	counter = 0
	for i in range(0, 600):
		F_attr = force_goal(input_state, goal)
		
		input_state = pose_propagation(F_attr, input_state)
		#calc_new_vel(input_state, F_attr)
		#input_state = calc_new_pose(input_state)
		t +=DT
		
		# print ("ped speed: ", torch.sqrt(input_state[0,2]**2 + input_state[0,3]**2))

		plot_data[0].append(input_state.data[0,0].item())
		plot_data[1].append(input_state.data[0,1].item())
		plot_data[2].append(t)
		res = is_goal_achieved(input_state, goal)
		if any(res) == True:
			# break
			goal = generate_new_goal(goal,res, input_state)
			print ("goal#, ",counter," changing goal, new goals are: ", goal)
			counter+=1
			print ()
	# print ((goal[:,0:2] - input_state[:,0:2]).norm())
	# print (goal[:,0:2] - input_state[:,0:2])

	print (F_attr)


	import matplotlib.pyplot as plt
	from mpl_toolkits.mplot3d import Axes3D


	fig = plt.figure()
	ax = fig.add_subplot(111, projection='3d')

	# fig, ax = plt.subplots()
	# fig = plt.figure()
	# ax = fig.add_subplot(111, projection='3d')

	ax.plot(plot_data[0],  plot_data[1],   plot_data[2],'ro',linewidth=1)
	# ax.plot(x2, y2, z,'ro',color='skyblue')
	# ax.plot(x3, y3, z,'ro',color='olive')
	# ax.plot(x4, y4, z,'ro',color='yellow')
	ax.set(zlabel='time (s)', ylabel='y', xlabel = "x",
		title='traj of persons')
	ax.grid()

	plt.show()
