import pyrealsense2 as rs
import traceback
import sys
import time
import numpy as np

class rs_d435:
    """
    Declare all the constants, tunable variables are public
    """
    def __init__(self):
        # public
        self.depth_width = 640
        self.depth_height = 480

        self.rgb_width = 640
        self.rgb_height = 480

        self.framerate = 30

        self.min_range = 0.1
        self.max_range = 10

        # private
        self._pipe = None

        self._intrin = None
        self._scale = 1

        self._FOV = None

        self._x_deproject_matrix = None
        self._y_deproject_matrix = None

    """
    with enter method opens D435 connection
    """
    def __enter__(self):
        self.open_connection()

    """
    with exit method closes the D435 connection
    """
    def __exit__(self, exception_type, exception_value, traceback):
        if traceback:
            print(traceback.tb_frame)
            self._exception_handle("rs_d435: __exit__: `{}`".format(exception_value))

        self.close_connection()
    
    """
    Open Connection to D435 camera
    """
    def open_connection(self):
        cfg = rs.config()
        cfg.enable_stream(rs.stream.depth, 
                                self.depth_width, self.depth_height,
                                rs.format.z16, 
                                self.framerate )
        cfg.enable_stream(rs.stream.color, 
                                self.rgb_width, self.rgb_height, 
                                rs.format.bgr8, 
                                self.framerate)

        self._pipe = rs.pipeline()
        
        try:
            self._pipe.start(cfg)
        except TimeoutError as e:
            self._exception_handle("rs_d435: open_connection: failed to connect to camera")
            raise e

        self._initialise_deprojection_matrix()

        print('rs_d435:D435 Connection Open')
    
    """
    Close connection to D435 camera
    """
    def close_connection(self):
        if self._pipe is None:
            return

        self._pipe.stop()
        self._pipe = None

        print('rs_d435:D435 Connection Closed')

    """
    Retrieve a data from the D435 camera
    """
    def get_frame(self) -> tuple:
        try:
            frames = self._pipe.wait_for_frames()
        except TimeoutError as e:         
            self._exception_handle("rs_d435: getFrame: timeout waiting for data frame")
            raise e

        depth_frame = frames.get_depth_frame()
        color_frame = frames.get_color_frame()

        try:
            depth_image = depth_frame.get_data()
            color_image = color_frame.get_data()
        except AttributeError:
            self._exception_handle("rs_d435: getFrame: frame contained no data")
            return None

        depth_image = np.asarray(depth_image, dtype=np.float32)
        color_image = np.asanyarray(color_image, dtype=np.uint8)

        depth_image = self._process_depth_frame(depth_image)
        depth_points = self._deproject_frame(depth_image)

        return (time.time(), depth_points, depth_image, color_image)

    """
    Returns the FOV of the connected camera
    """
    def get_fov(self) -> tuple:
        return self._FOV

    """
    Get camera intrinsics
    """
    def _get_intrinsics(self):
        profile = self._pipe.get_active_profile()

        self._intrin = profile.get_stream( rs.stream.depth ) \
                        .as_video_stream_profile() \
                        .get_intrinsics()

        self._scale = profile.get_device() \
                        .first_depth_sensor() \
                        .get_depth_scale()
                        
        self._FOV = rs.rs2_fov(self._intrin)

    """
    Initialise conversion matrix for converting the depth frame to a de-projected 3D 
    coordinate system
    """
    def _initialise_deprojection_matrix(self):
        self._get_intrinsics()
        
        x_deproject_row = (np.arange( self.depth_width ) - self._intrin.ppx) / self._intrin.fx
        y_deproject_col = (np.arange( self.depth_height ) - self._intrin.ppy) / self._intrin.fy

        self._x_deproject_matrix = np.tile( x_deproject_row, (self.depth_height, 1) )
        self._y_deproject_matrix = np.tile( y_deproject_col, (self.depth_width, 1) ).transpose()

    """
    Perform data pre-processing to depth frame
    """
    def _process_depth_frame(self, frame:np.array):
        frame = self._scale_depth_frame(frame)
        frame = self._limit_depth_range(frame)
        return frame

    """
    Scale the depth output to meteres
    """
    def _scale_depth_frame(self, frame:np.array):
        return frame * self._scale

    """
    Limit the maximum/minimum range of the depth camera
    """
    def _limit_depth_range(self, frame:np.array):
        frame[ np.logical_or(frame < self.min_range, frame > self.max_range) ] = np.nan
        return frame

    """
    Converts from depth frame to 3D local FED coordiate system
    """
    def _deproject_frame(self, frame:np.array) -> list:       
        Z = frame
        X = np.multiply( frame, self._x_deproject_matrix )
        Y = np.multiply( frame, self._y_deproject_matrix )

        Z = np.reshape(Z, (-1))
        X = np.reshape(X, (-1))
        Y = np.reshape(Y, (-1))

        return np.column_stack( (Z,X,Y) ) # Output as FRD coordinates

    """
    Function to collate interal class exceptions
    TODO: Log error - requires rabbit MQ stuff
    """
    def _exception_handle(self, err):
        print(err)

if __name__ == "__main__": #pragma: no cover
    import cv2

    d435Obj = rs_d435()

    with d435Obj:
        while True:
            frame = d435Obj.get_frame()

            depth = frame[2]
            depth = cv2.applyColorMap(cv2.convertScaleAbs(depth, alpha=50), cv2.COLORMAP_JET)

            np.nan_to_num(depth, nan=0)
            cv2.imshow('depth_frame', depth)
            cv2.imshow('color_frame', frame[3])
            cv2.waitKey(1)