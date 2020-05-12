"""
This module contains all classes related to preprocessing of point data to
be added to the occupancy map
"""
import time

import numpy as np
from scipy.spatial.transform import Rotation as R
import cv2

from modules.async_message import AsyncMessageCallback
from modules import load_config, data_types

class MapPreprocess:
    """
    This class takes a localised point cloud and prepares it to
    be added to the global occupancy map
    """
    def __init__(self, config_file='conf/map.yaml'):
        self.conf = load_config.from_file(config_file)

        self.x_bins = None
        self.y_bins = None
        self.z_bins = None

        self._initialise_bin_dilimitators()

        self.last_time = time.time()

    def _initialise_bin_dilimitators(self):
        self.x_bins = np.linspace(self.conf.map.x_min,
                                  self.conf.map.x_max,
                                  self.conf.map.x_divisions)
        self.y_bins = np.linspace(self.conf.map.y_min,
                                  self.conf.map.y_max,
                                  self.conf.map.y_divisions)
        self.z_bins = np.linspace(self.conf.map.z_min,
                                  self.conf.map.z_max,
                                  self.conf.map.z_divisions)

    def process_local_point_cloud(self, point_cloud, pose):
        """
        Process batches of local point clouds
        """
        point_cloud = self._local_to_global(point_cloud, pose)

        map_points, point_count = self._discretise_point_cloud(point_cloud)

        map_points, point_count = self._batch_filter(map_points, point_count)

        self.publish_data_set(map_points, point_count)

    def publish_data_set(self, points, count):
        """
        Passes data to Rabbit MQ
        """
        new_time = time.time()
        tdif = new_time - self.last_time
        self.last_time = new_time
        print("Time:{:.4f}\tNumer of voxels: {}".format(tdif, points.shape[0]))

    def _local_to_global(self, local_points, pose):
        """
        Convert local points to a global coordinate system
        """
        rot = R.from_quat(pose.quaternion)

        global_points = rot.apply(local_points)
        global_points = np.add(global_points, pose.translation)

        return global_points

    def _discretise_point_cloud(self, points):
        """
        Take continous point cloud and discritise to map grid
        """
        x_sort = np.digitize(points[:, 0], self.x_bins) -1
        y_sort = np.digitize(points[:, 1], self.y_bins) -1
        z_sort = np.digitize(points[:, 2], self.z_bins) -1

        points = np.column_stack((x_sort, y_sort, z_sort))
        points = np.uint16(points)

        count = None
        points, count = self._compress_point_cloud(points)

        return points, count

    def _compress_point_cloud(self, points):
        """
        Take a discritised point cloud and compress to cummalative
        counts of unique points
        """
        points, count = np.unique(points, axis=0, return_counts=True)

        # Compress data
        points = np.uint16(points)
        count = np.uint16(count)

        return (points, count)

    def _batch_filter(self, points, count):
        """
        Final filtering stage before adding to the map
        """
        return points, count

class DepthMapAdapter(MapPreprocess):
    """
    Prepare D435 depth data for feeding into the occupancy map
    """
    def __init__(self, config_file='conf/map.yaml'):
        super().__init__(config_file)

        self.depth_min_range = 0.1
        self.depth_max_range = 10

        self.depth_message_queue = AsyncMessageCallback(queue_size=1)

        self._pose_data = None

    def depth_callback(self, data: data_types.Depth):
        """
        Recieve incoming depth data
        """
        if self._pose_data is None:
            return

        self.depth_message_queue.queue_message((data, self._pose_data))

    def pose_callback(self, data: data_types.Pose):
        """
        Recieve incoming pose data
        """
        self._pose_data = data

    def adapter_pipeline(self):
        """
        Run incoming data through all processing steps
        """
        msg = self.depth_message_queue.wait_for_message()

        if msg is None:
            return

        depth_data, pose_data = msg[1]

        depth_frame = self._pre_process(depth_data.depth, depth_data.intrin)
        coord = self._deproject_frame(depth_frame, depth_data.intrin)

        self.process_local_point_cloud(coord, pose_data)

    def _pre_process(self, depth_frame, intrin: data_types.Intrinsics):
        """
        Any pre-processing before deprojection
        """
        depth_frame, intrin = self._downscale_data(depth_frame, intrin)
        depth_frame = self._scale_depth_frame(depth_frame, intrin.scale)
        depth_frame = self._limit_depth_range(depth_frame)

        return depth_frame

    def _downscale_data(self, data_frame, intrin: data_types.Intrinsics):

        block_size = tuple(self.conf.depth_preprocess.downscale_block_size)
        shape = data_frame.shape

        new_shape = (shape[0]//block_size[0], block_size[0], shape[1]//block_size[1], block_size[1])
        new_data_frame = np.reshape(data_frame, new_shape)

        if self.conf.depth_preprocess.downscale_method == 'min_pool':
            new_data_frame = np.amin(new_data_frame, axis=(1, 3))

        elif self.conf.depth_preprocess.downscale_method == 'max_pool':
            new_data_frame = np.amax(new_data_frame, axis=(1, 3))
            
        else:
            new_data_frame = np.mean(new_data_frame, axis=(1, 3))

        new_intrin = data_types.Intrinsics(intrin.scale,
                                           intrin.ppx / block_size[1],
                                           intrin.ppy / block_size[0],
                                           intrin.fx,
                                           intrin.fy)

        return new_data_frame, new_intrin

    def _scale_depth_frame(self, depth_frame, scale):
        """
        Convert depth pixels into meter units
        """
        return depth_frame * scale

    def _limit_depth_range(self, depth_frame):
        """
        Limit the maximum/minimum range of the depth camera
        """
        depth_frame[np.logical_or(depth_frame < self.conf.depth_preprocess.min_range,
                                  depth_frame > self.conf.depth_preprocess.max_range)] = np.nan
        return depth_frame

    def _deproject_frame(self, depth_frame, intrin: data_types.Intrinsics):
        """
        Deproject depth image to local cartesian coordinate system
        """
        frame_shape = depth_frame.shape
        x_deproject, y_deproject = self._initialise_deprojection_matrix(frame_shape, intrin)

        z_coord = depth_frame
        x_coord = np.multiply(depth_frame, x_deproject)
        y_coord = np.multiply(depth_frame, y_deproject)

        z_coord = np.reshape(z_coord, (-1))
        x_coord = np.reshape(x_coord, (-1))
        y_coord = np.reshape(y_coord, (-1))

        coord = np.column_stack((z_coord, x_coord, y_coord)) # Output as FRD coordinates
        return coord[~np.isnan(z_coord), :]

    def _initialise_deprojection_matrix(self, matrix_shape, intrin: data_types.Intrinsics):
        """
        Initialise conversion matrix for converting the depth frame to a de-projected 3D
        coordinate system
        """
        matrix_height, matrix_width = matrix_shape

        x_deproject_row = (np.arange(matrix_width) - intrin.ppx) / intrin.fx
        y_deproject_col = (np.arange(matrix_height) - intrin.ppy) / intrin.fy

        x_deproject_matrix = np.tile(x_deproject_row, (matrix_height, 1))
        y_deproject_matrix = np.tile(y_deproject_col, (matrix_width, 1)).transpose()

        return x_deproject_matrix, y_deproject_matrix

if __name__ == "__main__":
    pass
