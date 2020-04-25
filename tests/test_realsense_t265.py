from context import modules
from unittest import TestCase, mock

from modules import realsense_t265

class TestTemplate(TestCase):
    def setUp(self):
        self.t265 = realsense_t265.rs_t265()
    
    def tearDown(self):
        pass

    def test_import_success(self):
        self.assertTrue(True)

    @mock.patch('modules.realsense_t265.rs_t265._exception_handle')
    @mock.patch('pyrealsense2.pipeline.stop')
    @mock.patch('pyrealsense2.pipeline.start')
    def test_start_stop_connection(self, mock_start, mock_stop, mock_exception):
        import pyrealsense2 as rs
        self.t265._pipe = rs.pipeline()

        with self.t265:
            pass
        mock_start.assert_called()
        mock_stop.assert_called()

        try:
            with self.t265:
                self.t265.not_a_function()
        except:
            pass
        
        mock_exception.assert_called()
        mock_exception.reset_mock()

        mock_start.side_effect = TimeoutError()
        with self.assertRaises(TimeoutError):
            self.t265.open_connection()

        mock_exception.assert_called()

    @mock.patch('time.time')
    @mock.patch('modules.realsense_t265.rs_t265._exception_handle')
    @mock.patch('pyrealsense2.pipeline.wait_for_frames')
    @mock.patch('pyrealsense2.composite_frame.get_pose_frame')
    @mock.patch('pyrealsense2.pose_frame.get_pose_data')
    @mock.patch('modules.realsense_t265.rs_t265._convert_rotational_frame')
    @mock.patch('modules.realsense_t265.rs_t265._convert_positional_frame')
    def test_get_frames(self, mock_pos_transform, mock_rot_transform, 
                        mock_pose, mock_frame, mock_wait, mock_exception, mock_time):
        import pyrealsense2 as rs
        mock_pos_transform.side_effect = (lambda x: x) 
        mock_rot_transform.side_effect = (lambda x: x) 
        mock_wait.return_value = rs.composite_frame
        mock_frame.return_value = rs.pose_frame

        mock_pose_data = mock.PropertyMock()
        type(mock_pose_data.translation).x = mock.PropertyMock(return_value=1)
        type(mock_pose_data.translation).y = mock.PropertyMock(return_value=2)
        type(mock_pose_data.translation).z = mock.PropertyMock(return_value=3)

        type(mock_pose_data.rotation).x = mock.PropertyMock(return_value=0)
        type(mock_pose_data.rotation).y = mock.PropertyMock(return_value=0)
        type(mock_pose_data.rotation).z = mock.PropertyMock(return_value=0)
        type(mock_pose_data.rotation).w = mock.PropertyMock(return_value=1)

        type(mock_pose_data).tracker_confidence = mock.PropertyMock(return_value=3)

        mock_pose.return_value = mock_pose_data
        mock_time.return_value = 12

        self.t265._pipe = rs.pipeline()
        rtn_value = self.t265.get_frame()

        self.assertEqual(rtn_value[0],  12)
        self.assertListEqual(rtn_value[1], [1,2,3])
        self.assertListEqual(rtn_value[2], [0,0,0,1])
        self.assertEqual(rtn_value[3], 3)

        mock_pos_transform.assert_called()
        mock_rot_transform.assert_called()
        
        mock_pose.side_effect = AttributeError()
        rtn_value = self.t265.get_frame()
        
        mock_exception.assert_called()
        self.assertIsNone(rtn_value)

        mock_exception.reset_mock()
        mock_wait.side_effect = TimeoutError()
        with self.assertRaises(TimeoutError):
            self.t265.get_frame()

        mock_exception.assert_called()

    def test_convert_coordinate_frame(self):
        pass
        #TODO: Add in coordinate conversion tests