import marinenav_env.envs.marinenav_env as marinenav_env
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import copy
import scipy.spatial
import gym
import json

class EnvVisualizer:

    def __init__(self, seed:int=0, draw_dist:bool=False):
        self.env = marinenav_env.MarineNavEnv(seed)
        self.env.reset()
        self.fig = None # figure for visualization
        self.axis_graph = None # sub figure for the map
        self.robot_plot = None
        self.robot_last_pos = None
        self.robot_traj_plot = []
        self.sonar_beams_plot = []
        self.axis_action = None # sub figure for action command and steer data
        self.axis_sonar = None # sub figure for Sonar measurement
        self.axis_dvl = None # sub figure for DVL measurement
        self.axis_dist = None # sub figure for return distribution of actions

        self.episode_actions = [] # action sequence load from episode data
        self.episode_actions_quantiles = None
        self.episode_actions_taus = None

        self.draw_dist = draw_dist # whether to draw return distribution of actions

    def init_visualize(self):
        self.robot_last_pos = None

        x_pos = list(np.linspace(0,self.env.width,100))
        y_pos = list(np.linspace(0,self.env.height,100))

        pos_x = []
        pos_y = []
        arrow_x = []
        arrow_y = []
        for x in x_pos:
            for y in y_pos:
                v = self.env.get_velocity(x,y)
                pos_x.append(x)
                pos_y.append(y)
                arrow_x.append(v[0])
                arrow_y.append(v[1])
        
        # initialize subplot for the map, robot state and sensor measurments
        if self.draw_dist:
            self.fig = plt.figure(figsize=(32,16))
            spec = self.fig.add_gridspec(5,4)
            self.axis_dist = self.fig.add_subplot(spec[:,0])
            self.axis_graph = self.fig.add_subplot(spec[:,1:3])
            self.axis_action = self.fig.add_subplot(spec[0,3])
            self.axis_sonar = self.fig.add_subplot(spec[1:3,3])
            self.axis_dvl = self.fig.add_subplot(spec[3:,3])
        else:
            self.fig = plt.figure(figsize=(24,16))
            spec = self.fig.add_gridspec(5,3)
            self.axis_graph = self.fig.add_subplot(spec[:,:2])
            self.axis_action = self.fig.add_subplot(spec[0,2])
            self.axis_sonar = self.fig.add_subplot(spec[1:3,2])
            self.axis_dvl = self.fig.add_subplot(spec[3:,2])
        
        # plot current velocity in the map
        self.axis_graph.quiver(pos_x, pos_y, arrow_x, arrow_y)

        # plot obstacles in the map
        for obs in self.env.obstacles:
            self.axis_graph.add_patch(mpl.patches.Circle((obs.x,obs.y),radius=obs.r))

        self.axis_graph.set_aspect('equal')
        self.axis_graph.set_xlim([0.0,self.env.width])
        self.axis_graph.set_ylim([0.0,self.env.height])

        # plot start and goal state
        self.axis_graph.scatter(self.env.start[0],self.env.start[1],marker="o",color="r",s=80,zorder=6)
        self.axis_graph.scatter(self.env.goal[0],self.env.goal[1],marker="*",color="b",s=200,zorder=6)
    
    def plot_robot(self):
        if self.robot_plot != None:
            self.robot_plot.remove()

        d = np.matrix([[0.5*self.env.robot.length],[0.5*self.env.robot.width]])
        rot = np.matrix([[np.cos(self.env.robot.theta),-np.sin(self.env.robot.theta)], \
                         [np.sin(self.env.robot.theta),np.cos(self.env.robot.theta)]])
        d_r = rot * d
        xy = (self.env.robot.x-d_r[0,0],self.env.robot.y-d_r[1,0])

        angle_d = self.env.robot.theta / np.pi * 180
        self.robot_plot = self.axis_graph.add_patch(mpl.patches.Rectangle(xy,self.env.robot.length, \
                                                   self.env.robot.width,     \
                                                   color='g',angle=angle_d,zorder=6))

        if self.robot_last_pos != None:
            h = self.axis_graph.plot((self.robot_last_pos[0],self.env.robot.x),
                                    (self.robot_last_pos[1],self.env.robot.y),
                                    color='m')
            self.robot_traj_plot.append(h)
        
        self.robot_last_pos = [self.env.robot.x, self.env.robot.y]

    def plot_action_and_steer_state(self,action):
        self.axis_action.clear()

        a,w = self.env.robot.actions[action]
        self.axis_action.text(0,6,"Steer actions",fontweight="bold",fontsize=15)
        self.axis_action.text(0,5,f"Acceleration (m/s^2): {a:.2f}",fontsize=12)
        self.axis_action.text(0,4,f"Angular velocity (rad/s): {w:.2f}",fontsize=12)
        
        # robot steer state
        self.axis_action.text(0,2,"Steer states",fontweight="bold",fontsize=15)
        self.axis_action.text(0,1,f"Forward speed (m/s): {self.env.robot.speed:.2f}",fontsize=12)
        self.axis_action.text(0,0,f"Orientation (rad): {self.env.robot.theta:.2f}",fontsize=12)

        self.axis_action.set_ylim([-1.0,7.0])
        self.axis_action.set_xticks([])
        self.axis_action.set_yticks([])
        self.axis_action.spines["left"].set_visible(False)
        self.axis_action.spines["top"].set_visible(False)
        self.axis_action.spines["right"].set_visible(False)
        self.axis_action.spines["bottom"].set_visible(False)

    def plot_measurements(self):
        self.axis_sonar.clear()
        self.axis_dvl.clear()
        for plot in self.sonar_beams_plot:
            plot[0].remove()
        self.sonar_beams_plot.clear()
        
        abs_velocity_r, sonar_points_r, goal_r = self.env.get_observation(for_visualize=True)
        
        # plot Sonar beams in the world frame
        for point in self.env.robot.sonar.reflections:
            x = point[0]
            y = point[1]
            if point[-1] == 0:
                # compute beam range end point 
                x = self.env.robot.x + 0.5 * (x-self.env.robot.x)
                y = self.env.robot.y + 0.5 * (y-self.env.robot.y)
            else:
                # mark the reflection point
                self.sonar_beams_plot.append(self.axis_graph.plot(x,y,'rx'))

            self.sonar_beams_plot.append(self.axis_graph.plot([self.env.robot.x,x],[self.env.robot.y,y],'r--'))

        # plot Sonar reflections in the robot frame (rotate x-axis by 90 degree (upward) in the plot)
        low_angle = np.pi/2 + self.env.robot.sonar.beam_angles[0]
        high_angle = np.pi/2 + self.env.robot.sonar.beam_angles[-1]
        low_angle_d = low_angle / np.pi * 180
        high_angle_d = high_angle / np.pi * 180
        self.axis_sonar.add_patch(mpl.patches.Wedge((0.0,0.0),self.env.robot.sonar.range, \
                                               low_angle_d,high_angle_d,color="r",alpha=0.2))
        
        for i in range(np.shape(sonar_points_r)[1]):
            if sonar_points_r[2,i] == 1:
                # rotate by 90 degree 
                self.axis_sonar.plot(-sonar_points_r[1,i],sonar_points_r[0,i],'bx')

        self.axis_sonar.set_xlim([-self.env.robot.sonar.range-1,self.env.robot.sonar.range+1])
        self.axis_sonar.set_ylim([-1,self.env.robot.sonar.range+1])
        self.axis_sonar.set_aspect('equal')
        self.axis_sonar.set_title('Sonar measurement')

        # plot robot velocity in the robot frame (rotate x-axis by 90 degree (upward) in the plot)
        h1 = self.axis_dvl.arrow(0.0,0.0,0.0,1.0, \
                       color='k', \
                       width = 0.01, \
                       head_width = 0.06, \
                       head_length = 0.1, \
                       length_includes_head=True, \
                       label='steer direction')
        # rotate by 90 degree
        h2 = self.axis_dvl.arrow(0.0,0.0,-abs_velocity_r[1],abs_velocity_r[0], \
                       color='r',width=0.01, head_width = 0.06, \
                       head_length = 0.1, length_includes_head=True, \
                       label='velocity wrt seafloor')
        x_range = np.max([2,np.abs(abs_velocity_r[1])])
        y_range = np.max([2,np.abs(abs_velocity_r[0])])
        self.axis_dvl.set_xlim([-x_range,x_range])
        self.axis_dvl.set_ylim([-1,y_range])
        self.axis_dvl.set_aspect('equal')
        self.axis_dvl.legend(handles=[h1,h2])
        self.axis_dvl.set_title('DVL measurement')
    
    def plot_return_dist(self,quantiles,taus):
        self.axis_dist.clear()
        
        dist_interval = 1
        mean_bar = 0.25
        ylabelleft=[]
        ylabelright=[]

        quantiles = np.array(quantiles)
        for i, action in enumerate(self.env.robot.actions):
            q_mean = np.mean(quantiles[:,i])

            ylabelleft.append(
                "\n".join([f"a: {action[0]:.2f}",f"w: {action[1]:.2f}"])
            )

            ylabelright.append(f"mean: {q_mean:.2f}")
            
            self.axis_dist.axhline(i*dist_interval, color="black", linewidth=0.5, zorder=0)
            self.axis_dist.scatter(quantiles[:,i], i*np.ones(len(quantiles[:,i]))*dist_interval, marker="x")
            self.axis_dist.hlines(y=i*dist_interval, xmin=np.min(quantiles[:,i]), xmax=np.max(quantiles[:,i]), zorder=0)
            self.axis_dist.vlines(q_mean, ymin=i*dist_interval-mean_bar, ymax=i*dist_interval+mean_bar,linewidth=2)

        self.axis_dist.set_ylim([-1.0,i+1])
        self.axis_dist.set_yticks(range(0,i+1))
        self.axis_dist.set_yticklabels(labels=ylabelleft)
        # self.axis_dist.twinx().set_yticklabels(labels=ylabelright)

    def one_step(self,action):
        current_velocity = self.env.get_velocity(self.env.robot.x, self.env.robot.y)
        self.env.robot.update_state(action["action"],current_velocity)

        self.plot_robot()
        self.plot_measurements()
        self.plot_action_and_steer_state(action["action"])
        
        if self.draw_dist and self.dist_step % self.env.robot.N == 0:
            self.plot_return_dist(action["actions_quantiles"],action["actions_taus"])

        self.dist_step += 1

    def init_animation(self):
        # plot initial robot position
        self.plot_robot()

        # plot initial DVL and Sonar measurments
        self.plot_measurements() 

    def visualize_control(self,action_sequence):
        # update robot state and make animation when executing action sequence
        actions = []

        # counter for updating distributions plot
        self.dist_step = 0
        
        for i,a in enumerate(action_sequence):
            for _ in range(self.env.robot.N):
                action = {}
                action["action"] = a
                if self.draw_dist:
                    action["actions_quantiles"] = self.episode_actions_quantiles[i]
                    action["actions_taus"] = self.episode_actions_taus[i]
                actions.append(action)

        self.animation = animation.FuncAnimation(self.fig, self.one_step,frames=actions, \
                                                 init_func=self.init_animation,
                                                 interval=10,repeat=False)
        plt.show()

    def load_episode(self,episode_dict):
        episode = copy.deepcopy(episode_dict)

        # load env config
        self.env.sd = episode["env"]["seed"]
        self.env.width = episode["env"]["width"]
        self.env.height = episode["env"]["height"]
        self.env.r = episode["env"]["r"]
        self.env.v_rel_max = episode["env"]["v_rel_max"]
        self.env.p = episode["env"]["p"]
        self.env.v_range = copy.deepcopy(episode["env"]["v_range"])
        self.env.obs_r_range = copy.deepcopy(episode["env"]["obs_r_range"])
        self.env.clear_r = episode["env"]["clear_r"]
        self.env.start = np.array(episode["env"]["start"])
        self.env.goal = np.array(episode["env"]["goal"])
        self.env.goal_dis = episode["env"]["goal_dis"]
        self.env.timestep_penalty = episode["env"]["timestep_penalty"]
        # self.env.energy_penalty = np.matrix(episode["env"]["energy_penalty"])
        self.env.collision_penalty = episode["env"]["collision_penalty"]
        self.env.goal_reward = episode["env"]["goal_reward"]
        self.env.discount = episode["env"]["discount"]

        # load vortex cores
        self.env.cores.clear()
        centers = None
        for i in range(len(episode["env"]["cores"]["positions"])):
            center = episode["env"]["cores"]["positions"][i]
            clockwise = episode["env"]["cores"]["clockwise"][i]
            Gamma = episode["env"]["cores"]["Gamma"][i]
            core = marinenav_env.Core(center[0],center[1],clockwise,Gamma)
            self.env.cores.append(core)
            if centers is None:
                centers = np.array([[core.x,core.y]])
            else:
                c = np.array([[core.x,core.y]])
                centers = np.vstack((centers,c))
        
        if centers is not None:
            self.env.core_centers = scipy.spatial.KDTree(centers)

        # load obstacles
        self.env.obstacles.clear()
        centers = None
        for i in range(len(episode["env"]["obstacles"]["positions"])):
            center = episode["env"]["obstacles"]["positions"][i]
            r = episode["env"]["obstacles"]["r"][i]
            obs = marinenav_env.Obstacle(center[0],center[1],r)
            self.env.obstacles.append(obs)
            if centers is None:
                centers = np.array([[obs.x,obs.y]])
            else:
                c = np.array([[obs.x,obs.y]])
                centers = np.vstack((centers,c))

        if centers is not None:
            self.env.obs_centers = scipy.spatial.KDTree(centers)

        # load robot config
        self.env.robot.dt = episode["robot"]["dt"]
        self.env.robot.N = episode["robot"]["N"]
        self.env.robot.length = episode["robot"]["length"]
        self.env.robot.width = episode["robot"]["width"]
        self.env.robot.r = episode["robot"]["r"]
        self.env.robot.max_speed = episode["robot"]["max_speed"]
        self.env.robot.a = np.array(episode["robot"]["a"])
        self.env.robot.w = np.array(episode["robot"]["w"])
        self.env.robot.compute_k()
        self.env.robot.compute_actions()
        self.env.robot.init_theta = episode["robot"]["init_theta"]
        self.env.robot.init_speed = episode["robot"]["init_speed"]

        # load sonar config
        self.env.robot.sonar.range = episode["robot"]["sonar"]["range"]
        self.env.robot.sonar.angle = episode["robot"]["sonar"]["angle"]
        self.env.robot.sonar.num_beams = episode["robot"]["sonar"]["num_beams"]
        self.env.robot.sonar.compute_phi()
        self.env.robot.sonar.compute_beam_angles()

        # load action sequence
        self.episode_actions = copy.deepcopy(episode["robot"]["action_history"])

        # update env action and observation space
        self.env.action_space = gym.spaces.Discrete(self.env.robot.compute_actions_dimension())
        obs_len = 2 + 2 + 2 * self.env.robot.sonar.num_beams
        self.env.observation_space = gym.spaces.Box(low = -np.inf * np.ones(obs_len), \
                                                    high = np.inf * np.ones(obs_len), \
                                                    dtype = np.float32)

        if self.draw_dist:
            # load action quantiles and taus
            self.episode_actions_quantiles = episode["robot"]["actions_quantiles"]
            self.episode_actions_taus = episode["robot"]["actions_taus"]

    def load_episode_from_eval_file(self,filename,id):
        eval_file = np.load(filename,allow_pickle=True)
        episode = copy.deepcopy(eval_file["episode_data"][id])
        self.load_episode(episode)

    def load_episode_from_json_file(self,filename):
        with open(filename,"r") as f:
            episode = json.load(f)
        self.load_episode(episode)

    def play_episode(self):
        self.robot_last_pos = None
        for plot in self.robot_traj_plot:
            plot[0].remove()
        self.robot_traj_plot.clear()

        current_v = self.env.get_velocity(self.env.start[0],self.env.start[1])
        self.env.robot.reset_state(self.env.start[0],self.env.start[1], current_velocity=current_v)

        self.init_visualize()

        self.visualize_control(self.episode_actions)