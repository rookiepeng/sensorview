import h5py
import os
import numpy as np
import pandas as pd


def unpack_plotdata(path, file_name, save_list=True):
    c_look_names = ['MRLL', 'MRML', 'LRLL', 'LRML']
    c_firing_order = ['MRLL', 'LRLL', 'MRML', 'LRML']
    c_chirp_period = 60e-3

    f = h5py.File(os.path.join(path, file_name), 'r')

    frame_size = np.shape(f['plotData']['LRLL'])[0]

    frame = pd.Series(dtype=int)
    look_type_idx = pd.Series(dtype=int)
    look_type_name = pd.Series(dtype=object)
    rng = pd.Series()
    speed = pd.Series()
    az = pd.Series()
    el = pd.Series()
    amp = pd.Series()
    snr = pd.Series()
    rcs = pd.Series()

    sub_frame = pd.Series()
    vel_speed = pd.Series()
    vel_yaw = pd.Series()

    for frame_idx in range(0, frame_size):
        try:
            for look_num, look_idx in enumerate(c_firing_order):
                single_frame = f[f['plotData'][look_idx][frame_idx, 0]]

                look_type_temp = single_frame['look'][()][0, 0]
                frame_str = (
                    (single_frame['RawDataFile'][()]-48).ravel())[22:-4]
                frame_temp = int(str(frame_str)[1:-1].replace(" ", ""))

                num_det = single_frame['afData']['numDets'][()][0, 0]
                cr_resp = single_frame['rdd2Data']['CR_Resp'][()][0, :]
                vel_speed_temp = single_frame['speed'][()][0, 0]
                vel_yaw_temp = single_frame['yaw'][()][0, 0]

                if num_det > 0:
                    for rdop_det_idx in range(0, int(num_det)):
                        single_det = f[single_frame['afData']
                                       ['af_output'][rdop_det_idx, 0]]
                        rng_temp = pd.Series(single_det['range'][()][0, :])
                        speed_temp = pd.Series(
                            single_det['range_rate'][()][0, :])
                        az_temp = pd.Series(single_det['az'][()][0, :])
                        el_temp = pd.Series(single_det['el'][()][0, :])
                        amp_temp = pd.Series(
                            20*np.log10(single_det['rdop_amp'][()][0, :]))
                        snr_temp = pd.Series(single_det['SNR'][()][0, :])

                        look_name_temp = pd.Series(
                            np.zeros_like(snr_temp, dtype=object))
                        look_name_temp[:] = c_look_names[int(look_type_temp-1)]

                        rng_bin_temp = single_det['rindx'][()][0, :]
                        cr_resp_temp = cr_resp[int(rng_bin_temp[0])-1]
                        if cr_resp_temp == 0:
                            cr_resp_temp = 4.645275098003292e+03
                        cr = pd.Series(
                            20*np.log10((np.ones_like(rng_temp)*cr_resp_temp)))

                        rcs_temp = amp_temp-cr

                        rng = rng.append(rng_temp, ignore_index=True)
                        speed = speed.append(speed_temp, ignore_index=True)
                        az = az.append(az_temp, ignore_index=True)
                        el = el.append(el_temp, ignore_index=True)
                        amp = amp.append(amp_temp, ignore_index=True)
                        snr = snr.append(snr_temp, ignore_index=True)
                        rcs = rcs.append(rcs_temp, ignore_index=True)
                        look_type_name = look_type_name.append(
                            look_name_temp, ignore_index=True)
                        look_type_idx = look_type_idx.append(
                            pd.Series(np.ones_like(rng_temp)*look_type_temp), ignore_index=True)
                        frame = frame.append(pd.Series(np.ones_like(
                            rng_temp)*frame_temp), ignore_index=True)
                        sub_frame = sub_frame.append(pd.Series(np.ones_like(
                            rng_temp)*look_num), ignore_index=True)
                        vel_speed = vel_speed.append(pd.Series(np.ones_like(
                            rng_temp)*vel_speed_temp), ignore_index=True)
                        vel_yaw = vel_yaw.append(pd.Series(np.ones_like(
                            rng_temp)*vel_yaw_temp), ignore_index=True)
        except Exception:
            print("Missing data"+str(frame_idx))

    temp_frame = 4*frame+sub_frame
    jump_position = temp_frame - \
        pd.concat([pd.Series(temp_frame[0]), temp_frame[0:-1]],
                  ignore_index=True)
    vel_angle = (vel_yaw*c_chirp_period*jump_position).cumsum()
    vel_x = (vel_speed*c_chirp_period*jump_position *
             np.sin(vel_angle/180*np.pi)).cumsum()
    vel_y = (vel_speed*c_chirp_period*jump_position *
             np.cos(vel_angle/180*np.pi)).cumsum()

    det_list = pd.DataFrame()

    det_list['Frame'] = frame
    det_list['LookType'] = look_type_idx
    det_list['LookName'] = look_type_name
    det_list['Range'] = rng
    det_list['Speed'] = speed
    det_list['Azimuth'] = az
    det_list['Elevation'] = el
    det_list['Amp'] = amp
    det_list['SNR'] = snr
    det_list['RCS'] = rcs
    det_list['Target_loc_x'] = -det_list['Range']*np.sin((det_list['Azimuth']+vel_angle)/180*np.pi)*np.cos(
        det_list['Elevation']/180*np.pi) - vel_x
    det_list['Target_loc_y'] = det_list['Range']*np.cos((det_list['Azimuth']+vel_angle)/180*np.pi)*np.cos(
        det_list['Elevation']/180*np.pi) + vel_y
    det_list['Target_rng_y'] = det_list['Range']*np.cos((det_list['Azimuth']+vel_angle)/180*np.pi)*np.cos(
        det_list['Elevation']/180*np.pi)
    det_list['Target_loc_z'] = det_list['Range'] * \
        np.sin(det_list['Elevation']/180*np.pi)
    det_list['vel_angle'] = vel_angle
    det_list['vel_x'] = -vel_x
    det_list['vel_y'] = vel_y

    if save_list:
        det_list.to_pickle(file_name[:-4]+'.pkl')

    return det_list


def unpack_session(path, file_name, save_list=True):
    # path = './'
    # file_name = 'Session_02_Oct_2019_07_25_20_Set51to100.mat'

    look_names = ['MRLL', 'MRML', 'LRLL', 'LRML']

    f = h5py.File(os.path.join(path, file_name))

    sess_data = f['sess_data']

    frame_size = np.shape(sess_data['plotData'])[1]

    frame = pd.Series()
    look_type = pd.Series()
    look_type_name = pd.Series(dtype=object)
    rng = pd.Series()
    speed = pd.Series()
    az = pd.Series()
    el = pd.Series()
    amp = pd.Series()
    snr = pd.Series()
    # rng_bin = pd.Series(dtype=int)
    rcs = pd.Series()
    # sub_frame = pd.Series()
    can_speed = pd.Series()
    can_yaw = pd.Series()

    for frame_idx in range(0, frame_size):
        single_frame = f[sess_data['plotData'][0, frame_idx]]

        look_type_temp = single_frame['look'][()][0, 0]
        # frame_str = (
        #     (f[sess_data['RawDataFile'][frame_idx, 0]][()]-48).ravel())[22:-4]
        frame_str = (
            (f[sess_data['RawDataFile'][frame_idx, 0]][()]-48).ravel())[22:]
        frame_temp = int(str(frame_str)[1:-1].replace(" ", ""))

        num_rdop_det = np.shape(single_frame['afData']['af_output'])[0]

        cr_resp = single_frame['rdd2Data']['CR_Resp'][()][0, :]
        can_speed_temp = single_frame['speed'][()][0, 0]
        can_yaw_temp = single_frame['yaw'][()][0, 0]

        for rdop_det_idx in range(0, num_rdop_det):
            single_det = f[single_frame['afData']
                           ['af_output'][rdop_det_idx, 0]]
            rng_temp = pd.Series(single_det['range'][()][0, :])
            speed_temp = pd.Series(single_det['range_rate'][()][0, :])
            az_temp = pd.Series(single_det['az'][()][0, :])
            el_temp = pd.Series(single_det['el'][()][0, :])
            amp_temp = pd.Series(single_det['amp'][()][0, :])
            snr_temp = pd.Series(single_det['SNR'][()][0, :])
            rcs_temp = pd.Series(np.zeros_like(snr_temp))
            look_name_temp = pd.Series(np.zeros_like(snr_temp, dtype=object))
            look_name_temp[:] = look_names[int(look_type_temp-1)]

            rng = rng.append(rng_temp, ignore_index=True)
            speed = speed.append(speed_temp, ignore_index=True)
            az = az.append(az_temp, ignore_index=True)
            el = el.append(el_temp, ignore_index=True)
            amp = amp.append(amp_temp, ignore_index=True)
            snr = snr.append(snr_temp, ignore_index=True)
            rcs = rcs.append(rcs_temp, ignore_index=True)
            look_type_name = look_type_name.append(
                look_name_temp, ignore_index=True)

            look_type = look_type.append(
                pd.Series(np.ones_like(rng_temp)*look_type_temp), ignore_index=True)

            frame = frame.append(pd.Series(np.ones_like(
                rng_temp)*frame_temp), ignore_index=True)
    #         sub_frame = sub_frame.append(pd.Series(np.ones_like(
    #             rng_temp)*look_num), ignore_index=True)
            can_speed = can_speed.append(pd.Series(np.ones_like(
                rng_temp)*can_speed_temp), ignore_index=True)
            can_yaw = can_yaw.append(pd.Series(np.ones_like(
                rng_temp)*can_yaw_temp), ignore_index=True)

    chirp_period = 60e-3*4

    temp_frame = frame
    jump_position = temp_frame - \
        pd.concat([pd.Series(temp_frame[0]), temp_frame[0:-1]],
                  ignore_index=True)
    vel_angle = (can_yaw*chirp_period*jump_position).cumsum()
    vel_x = (can_speed*chirp_period*jump_position *
             np.sin(vel_angle/180*np.pi)).cumsum()
    vel_y = (can_speed*chirp_period*jump_position *
             np.cos(vel_angle/180*np.pi)).cumsum()

    det_list = pd.DataFrame()

    det_list['Frame'] = frame
    det_list['LookType'] = look_type
    det_list['LookName'] = look_type_name
    det_list['Range'] = rng
    det_list['Speed'] = speed
    det_list['Azimuth'] = az
    det_list['Elevation'] = el
    det_list['Amp'] = amp
    det_list['SNR'] = snr
    det_list['RCS'] = rcs
    det_list['Target_loc_x'] = -det_list['Range']*np.sin((det_list['Azimuth']+vel_angle)/180*np.pi)*np.cos(
        det_list['Elevation']/180*np.pi) - vel_x
    det_list['Target_loc_y'] = det_list['Range']*np.cos((det_list['Azimuth']+vel_angle)/180*np.pi)*np.cos(
        det_list['Elevation']/180*np.pi) + vel_y
    det_list['Target_rng_y'] = det_list['Range']*np.cos((det_list['Azimuth']+vel_angle)/180*np.pi)*np.cos(
        det_list['Elevation']/180*np.pi)
    det_list['Target_loc_z'] = det_list['Range'] * \
        np.sin(det_list['Elevation']/180*np.pi)
    det_list['vel_angle'] = vel_angle
    det_list['vel_x'] = -vel_x
    det_list['vel_y'] = vel_y

    if save_list:
        det_list.to_pickle(file_name[:-4]+'.pkl')

    return det_list
