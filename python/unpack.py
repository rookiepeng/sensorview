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
    az_conf = pd.Series(dtype=int)
    el_conf = pd.Series(dtype=int)
    amp = pd.Series()
    snr = pd.Series()
    af_type = pd.Series(dtype=object)
    rcs = pd.Series()
    sub_frame = pd.Series()
    veh_speed = pd.Series()
    veh_yaw_rate = pd.Series()

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
                veh_speed_temp = single_frame['speed'][()][0, 0]
                veh_yaw_rate_temp = single_frame['yaw'][()][0, 0]

                vun = single_frame['rdd2Data']['rdd_output']['Vun'][()][0, 0]

                if num_det > 0:
                    for rdop_det_idx in range(0, int(num_det)):
                        single_det = f[single_frame['afData']
                                       ['af_output'][rdop_det_idx, 0]]
                        rng_temp = pd.Series(single_det['range'][()][0, :])
                        speed_temp = pd.Series(
                            single_det['range_rate'][()][0, :])
                        az_temp = pd.Series(single_det['az'][()][0, :])
                        el_temp = pd.Series(single_det['el'][()][0, :])
                        az_conf_temp = pd.Series(
                            single_det['az_conf'][()][0, :])
                        el_conf_temp = pd.Series(
                            single_det['el_conf'][()][0, :])
                        af_type_temp = pd.Series(
                            np.zeros_like(az_temp, dtype=object))
                        af_type_temp[:] = single_det['type'][()][:, 0].astype(
                            np.uint8).tostring().decode("ascii")
                        amp_temp = pd.Series(
                            20*np.log10(single_det['rdop_amp'][()][0, :]))
                        snr_temp = pd.Series(single_det['SNR'][()][0, :])
                        dopp_shift_temp = pd.Series(
                            single_det['Dopp_shift'][()][0, :])
                        speed_temp = speed_temp - speed_temp / \
                            np.abs(speed_temp)*vun*dopp_shift_temp/np.pi

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
                        az_conf = az_conf.append(
                            az_conf_temp, ignore_index=True)
                        el_conf = el_conf.append(
                            el_conf_temp, ignore_index=True)
                        af_type = af_type.append(
                            af_type_temp, ignore_index=True)
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
                        veh_speed = veh_speed.append(pd.Series(np.ones_like(
                            rng_temp)*veh_speed_temp), ignore_index=True)
                        veh_yaw_rate = veh_yaw_rate.append(pd.Series(np.ones_like(
                            rng_temp)*veh_yaw_rate_temp), ignore_index=True)
        except Exception:
            print("Missing data"+str(frame_idx))

    temp_frame = 4*frame+sub_frame
    jump_position = temp_frame - \
        pd.concat([pd.Series(temp_frame[0]), temp_frame[0:-1]],
                  ignore_index=True)
    veh_angle = (veh_yaw_rate*c_chirp_period*jump_position).cumsum()
    veh_x = (veh_speed*c_chirp_period*jump_position *
             np.sin(veh_angle/180*np.pi)).cumsum()
    veh_y = (veh_speed*c_chirp_period*jump_position *
             np.cos(veh_angle/180*np.pi)).cumsum()

    det_list = pd.DataFrame()

    det_list['Frame'] = frame
    det_list['LookType'] = look_type_idx
    det_list['LookName'] = look_type_name
    det_list['Range'] = rng
    det_list['Speed'] = speed
    det_list['Azimuth'] = az
    det_list['Elevation'] = el
    det_list['AzConf'] = az_conf
    det_list['ElConf'] = el_conf
    det_list['AFType'] = af_type
    det_list['Amplitude'] = amp
    det_list['SNR'] = snr
    det_list['RCS'] = rcs
    det_list['VehYawRate'] = veh_yaw_rate
    det_list['VehSpeed'] = veh_speed

    det_list['Latitude'] = -det_list['Range']*np.sin((det_list['Azimuth']+veh_angle)/180*np.pi)*np.cos(
        det_list['Elevation']/180*np.pi) - veh_x
    det_list['Longitude'] = det_list['Range']*np.cos((det_list['Azimuth']+veh_angle)/180*np.pi)*np.cos(
        det_list['Elevation']/180*np.pi) + veh_y
    # det_list['Target_rng_y'] = det_list['Range']*np.cos((det_list['Azimuth']+veh_angle)/180*np.pi)*np.cos(
    #     det_list['Elevation']/180*np.pi)
    det_list['Height'] = -det_list['Range'] * \
        np.sin(det_list['Elevation']/180*np.pi)
    det_list['VehYaw'] = veh_angle
    det_list['VehLat'] = -veh_x
    det_list['VehLong'] = veh_y

    if save_list:
        det_list.to_pickle(file_name[:-4]+'.pkl')

    return det_list


def unpack_session(path, file_name, save_list=True):
    look_names = ['MRLL', 'MRML', 'LRLL', 'LRML']
    c_firing_order = [0, 2, 1, 3]

    f = h5py.File(os.path.join(path, file_name))

    session_data = f['sess_data']

    frame_size = np.shape(session_data['plotData'])[1]

    frame = pd.Series(dtype=int)
    look_type_idx = pd.Series(dtype=int)
    look_type_name = pd.Series(dtype=object)
    rng = pd.Series()
    speed = pd.Series()
    az = pd.Series()
    el = pd.Series()
    az_conf = pd.Series(dtype=int)
    el_conf = pd.Series(dtype=int)
    amp = pd.Series()
    snr = pd.Series()
    af_type = pd.Series(dtype=object)
    # rng_bin = pd.Series(dtype=int)
    rcs = pd.Series()
    sub_frame = pd.Series(dtype=int)
    veh_speed = pd.Series()
    veh_yaw_rate = pd.Series()

    for frame_idx in range(0, frame_size):
        single_frame = f[session_data['plotData'][0, frame_idx]]

        look_type_temp = single_frame['look'][()][0, 0]
        frame_str = (
            (f[session_data['RawDataFile'][frame_idx, 0]][()]-48).ravel())[22:]
        frame_temp = int(str(frame_str)[1:-1].replace(" ", ""))

        num_det = single_frame['afData']['numDets'][()][0, 0]
        cr_resp = single_frame['rdd2Data']['CR_Resp'][()][0, :]
        veh_speed_temp = single_frame['speed'][()][0, 0]
        veh_yaw_rate_temp = single_frame['yaw'][()][0, 0]

        if num_det > 0:
            for rdop_det_idx in range(0, int(num_det)):
                single_det = f[single_frame['afData']
                               ['af_output'][rdop_det_idx, 0]]
                rng_temp = pd.Series(single_det['range'][()][0, :])
                speed_temp = pd.Series(single_det['range_rate'][()][0, :])
                az_temp = pd.Series(single_det['az'][()][0, :])
                el_temp = pd.Series(single_det['el'][()][0, :])
                az_conf_temp = pd.Series(single_det['az_conf'][()][0, :])
                el_conf_temp = pd.Series(single_det['el_conf'][()][0, :])
                af_type_temp = pd.Series(np.zeros_like(az_temp, dtype=object))
                af_type_temp[:] = single_det['type'][()][:, 0].astype(
                    np.uint8).tostring().decode("ascii")
                amp_temp = pd.Series(
                    20*np.log10(single_det['rdop_amp'][()][0, :]))
                snr_temp = pd.Series(single_det['SNR'][()][0, :])
                rcs_temp = pd.Series(np.zeros_like(snr_temp))
                look_name_temp = pd.Series(
                    np.zeros_like(snr_temp, dtype=object))
                look_name_temp[:] = look_names[int(look_type_temp-1)]

                sub_frame_temp = pd.Series(np.ones_like(
                    snr_temp))*c_firing_order[int(look_type_temp-1)]

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
                az_conf = az_conf.append(az_conf_temp, ignore_index=True)
                el_conf = el_conf.append(el_conf_temp, ignore_index=True)
                af_type = af_type.append(af_type_temp, ignore_index=True)
                amp = amp.append(amp_temp, ignore_index=True)
                snr = snr.append(snr_temp, ignore_index=True)
                rcs = rcs.append(rcs_temp, ignore_index=True)
                look_type_name = look_type_name.append(
                    look_name_temp, ignore_index=True)
                look_type_idx = look_type_idx.append(
                    pd.Series(np.ones_like(rng_temp)*look_type_temp), ignore_index=True)

                frame = frame.append(pd.Series(np.ones_like(
                    rng_temp)*frame_temp), ignore_index=True)

                sub_frame = sub_frame.append(sub_frame_temp, ignore_index=True)
                veh_speed = veh_speed.append(pd.Series(np.ones_like(
                    rng_temp)*veh_speed_temp), ignore_index=True)
                veh_yaw_rate = veh_yaw_rate.append(pd.Series(np.ones_like(
                    rng_temp)*veh_yaw_rate_temp), ignore_index=True)

    chirp_period = 60e-3

    det_list = pd.DataFrame()

    # det_list['Jump'] = jump_position
    det_list['Frame'] = frame
    det_list['SubFrame'] = sub_frame
    det_list['LookType'] = look_type_idx
    det_list['LookName'] = look_type_name
    det_list['Range'] = rng
    det_list['Speed'] = speed
    det_list['Azimuth'] = az
    det_list['Elevation'] = el
    det_list['AzConf'] = az_conf
    det_list['ElConf'] = el_conf
    det_list['AFType'] = af_type
    det_list['Amplitude'] = amp
    det_list['SNR'] = snr
    det_list['RCS'] = rcs
    det_list['VehYawRate'] = veh_yaw_rate
    det_list['VehSpeed'] = veh_speed

    det_list = det_list.sort_values(
        ['Frame', 'SubFrame'], ascending=[True, True])

    temp_frame = 4*det_list['Frame']+det_list['SubFrame']
    jump_position = temp_frame - \
        pd.concat([pd.Series(temp_frame[0]), temp_frame[0:-1]],
                  ignore_index=True)
    veh_angle = (det_list['VehYawRate'] * chirp_period*jump_position).cumsum()
    veh_x = (det_list['VehSpeed']*chirp_period*jump_position *
             np.sin(veh_angle/180*np.pi)).cumsum()
    veh_y = (veh_speed*chirp_period*jump_position *
             np.cos(veh_angle/180*np.pi)).cumsum()

    det_list['Latitude'] = -det_list['Range']*np.sin((det_list['Azimuth']+veh_angle)/180*np.pi)*np.cos(
        det_list['Elevation']/180*np.pi) - veh_x
    det_list['Longitude'] = det_list['Range']*np.cos((det_list['Azimuth']+veh_angle)/180*np.pi)*np.cos(
        det_list['Elevation']/180*np.pi) + veh_y
    # det_list['Target_rng_y'] = det_list['Range']*np.cos((det_list['Azimuth']+veh_angle)/180*np.pi)*np.cos(
    #     det_list['Elevation']/180*np.pi)
    det_list['Height'] = -det_list['Range'] * \
        np.sin(det_list['Elevation']/180*np.pi)
    det_list['VehYaw'] = veh_angle
    det_list['VehLat'] = -veh_x
    det_list['VehLong'] = veh_y

    if save_list:
        det_list.to_pickle(file_name[:-4]+'.pkl')

    return det_list
