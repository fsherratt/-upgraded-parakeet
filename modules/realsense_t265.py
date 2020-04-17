import traceback
import sys
import time

import pyrealsense2 as rs

class rs_t265:
    def __init__(self):
        # Setup variables
        self.pipe = None
        self.cfg = None

    def __enter__(self):
        self.openConnection()

    def __exit__(self, exception_type, exception_value, traceback):
        if traceback:
            print(traceback.tb_frame)

        self.closeConnection()

    def openConnection(self):
        self.pipe = rs.pipeline()

        self.cfg = rs.config()
        self.cfg.enable_stream(rs.stream.pose)

        self.pipe.start(self.cfg)
        print('rs_t265:T265 Connection Open')

    def closeConnection(self):
        self.pipe.stop()
        print('rs_t265:T265 Connection Closed')

    def getFrame(self) -> tuple:
        try:
            frames = self.pipe.wait_for_frames()
        except RuntimeError:
            # Camera has probably disconnected
            traceback.print_exc(file=sys.stdout)

        pose = frames.get_pose_frame()

        try:
            data = pose.get_pose_data()
        except ValueError:
            return None

        pos = [data.translation.x, 
                data.translation.y, 
                data.translation.z]

        quat = [data.rotation.x, 
                data.rotation.y, 
                data.rotation.z, 
                data.rotation.w]

        conf = data.tracker_confidence

        return (time.time(), pos, quat, conf)


if __name__ == "__main__":   
    t265Obj = rs_t265()

    with t265Obj:
        while True:
            data_frame = t265Obj.getFrame()

            # print(i, pos, conf)

            print( ' Pos: {}\t Quat: {}\t Conf:{}'.format(
                    data_frame[1], 
                    data_frame[2], 
                    data_frame[3]) )

            time.sleep(0.5)