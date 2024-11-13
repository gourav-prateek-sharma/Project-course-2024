import os, sys, gzip, json
from pathlib import Path
from loguru import logger
import pandas as pd
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

PACKET_IN_DECISION_DELAY_MIN = 2 # 2 slots delay between decision and in packet

def get_scheduling_delay(packet, sched_sorted_dict, slots_per_frame=20, slots_duration_ms=0.5):
    idx=sched_sorted_dict.bisect_right(packet['ip.in_t']+PACKET_IN_DECISION_DELAY_MIN*slots_duration_ms*0.001)
    if idx < len(sched_sorted_dict):
        schedule_ts = sched_sorted_dict[sched_sorted_dict.keys()[idx]]['schedule_ts']
        return (schedule_ts-packet['ip.in_t'])*1000
    else:
        return None

def get_frame_alignment_delay(packet, sr_bsr_tx_sorted_list, slots_per_frame=20, slots_duration_ms=0.5):
    idx=sr_bsr_tx_sorted_list.bisect_right(packet['ip.in_t'])
    if idx < len(sr_bsr_tx_sorted_list):
        return (sr_bsr_tx_sorted_list[idx]-packet['ip.in_t'])*1000
    else:
        return None


def get_buffer_len(packet, bsrupd_sorted_dict, slots_per_frame=20, slots_duration_ms=0.5):
    idx=bsrupd_sorted_dict.bisect_right(packet['ip.in_t'])
    if idx < len(bsrupd_sorted_dict):
        return bsrupd_sorted_dict[bsrupd_sorted_dict.keys()[idx]]['len']
    else:
        return None

# delay between ip.in and first segment mac.in
def get_queueing_delay(packet):
    min_delay = np.inf
    for rlc_seg in packet['rlc.attempts']:
        if rlc_seg.get('mac.in_t')!=None and packet.get('ip.in_t')!=None and packet.get('rlc.attempts')!=None:
            min_delay = min(min_delay, rlc_seg['mac.in_t']-packet['ip.in_t'])
        else:
            logger.error(f"Packet {packet['id']} Either mac.in_t, ip.in_t or rlc.attempts not present")
            return None
    return min_delay*1000


# delay between ip.in and first segment mac.in  - frame alignment delay
def get_queueing_delay_wo_frame_alignment_delay(packet, sr_bsr_tx_sorted_list, slots_per_frame=20, slots_duration_ms=0.5):
    queueing_delay = get_queueing_delay(packet)
    frame_alignment_delay = get_frame_alignment_delay(packet, sr_bsr_tx_sorted_list, slots_per_frame=20, slots_duration_ms=0.5)
    if queueing_delay!=None and frame_alignment_delay!=None and queueing_delay>frame_alignment_delay:
        return queueing_delay-frame_alignment_delay
    else:
        return None

# delay between ip.in and first segment mac.in  - scheduling delay
def get_queueing_delay_wo_scheduling_delay(packet, sched_sorted_dict, slots_per_frame=20, slots_duration_ms=0.5):
    queueing_delay = get_queueing_delay(packet)
    scheduling_delay = get_scheduling_delay(packet, sched_sorted_dict, slots_per_frame=20, slots_duration_ms=0.5)
    if queueing_delay!=None and scheduling_delay!=None and queueing_delay>scheduling_delay:
        return queueing_delay-scheduling_delay
    else:
        return None

# return ran delay in millisecons
def get_ran_delay(packet):
    if packet.get('ip.out_t')!=None and packet.get('ip.in_t')!=None:
        return (packet['ip.out_t']-packet['ip.in_t'])*1000
    else:
        logger.error(f"Packet {packet['id']} either ip.in_t or ip.out_t not present")
        return None

def get_ran_delay_wo_frame_alignment_delay(packet, sr_bsr_tx_sorted_list, slots_per_frame=20, slots_duration_ms=0.5):
    if get_ran_delay(packet)>0 and get_frame_alignment_delay(packet, sr_bsr_tx_sorted_list, slots_per_frame=20, slots_duration_ms=0.5)>0:
        return get_ran_delay(packet)-get_frame_alignment_delay(packet, sr_bsr_tx_sorted_list, slots_per_frame=20, slots_duration_ms=0.5)
    else:
        return None

def get_ran_delay_wo_scheduling_delay(packet, sched_sorted_dict, slots_per_frame=20, slots_duration_ms=0.5):
    if get_ran_delay(packet)>0 and get_scheduling_delay(packet, sched_sorted_dict, slots_per_frame=20, slots_duration_ms=0.5):
        return get_ran_delay(packet)-get_scheduling_delay(packet, sched_sorted_dict, slots_per_frame=20, slots_duration_ms=0.5)
    else:
        return None

def get_retx_delay_seg(packet, rlc_seg):
    max_delay, min_delay = -np.inf, np.inf
    for mac_attempt in rlc_seg['mac.attempts']:
        if mac_attempt.get('phy.in_t')!=None:
            max_delay = max(max_delay, mac_attempt['phy.in_t'])
            min_delay = min(min_delay, mac_attempt['phy.in_t'])
        else:
            logger.error(f"Packet {packet['id']} phy.in_t not present")
            return None
    return (max_delay-min_delay)*1000

def get_max_rlc_seg(packet):
    max_delay = -np.inf
    max_rlc_seg = None
    for rlc_seg in packet['rlc.attempts']:
        if len(rlc_seg['mac.attempts'])>0 and get_retx_delay_seg(packet, rlc_seg)!=None:
            if get_retx_delay_seg(packet, rlc_seg) > max_delay:
                max_delay = get_retx_delay_seg(packet, rlc_seg)
                max_rlc_seg = rlc_seg
        else:
            logger.error(f"Packet {packet['id']} mac.attempts not present")
            return None
    return  max_rlc_seg

def get_retx_delay(packet):
    max_delay = -np.inf
    max_rlc_seg = get_max_rlc_seg(packet)
    if max_rlc_seg!=None and get_retx_delay_seg(packet, max_rlc_seg)!=None:
        return get_retx_delay_seg(packet, max_rlc_seg)
    else:
        return None
    # for rlc_seg in packet['rlc.attempts']:
    #     if len(rlc_seg['mac.attempts'])>0 and get_retx_delay_seg(packet, rlc_seg)!=None:
    #         if get_retx_delay_seg(packet, rlc_seg) > max_delay:
    #             max_delay = get_retx_delay_seg(packet, rlc_seg)
    #             max_rlc_seg = rlc_seg
    #     else:
    #         logger.error(f"Packet {packet['id']} mac.attempts not present")
    #         return None, None
    # return max_delay, max_rlc_seg

# retx delay is the retx delay of the first segment

# def get_retx_delay(packet):
#     phy_in_min_t, phy_in_max_t = np.inf, -np.inf
#     for rlc_seg in packet['rlc.attempts']:
#         if rlc_seg['so']==0: # only check the first segment
#             for mac_attempt in rlc_seg['mac.attempts']:
#                 if mac_attempt['phy.in_t'] != None:
#                     phy_in_min_t = min(phy_in_min_t,  mac_attempt['phy.in_t'])
#                     phy_in_max_t = max(phy_in_max_t, mac_attempt['phy.in_t'])
#     if phy_in_min_t<np.inf and phy_in_max_t>-np.inf:
#         return (phy_in_max_t-phy_in_min_t)*1000
#     else:
#         return None

# tx delay of first mac attempt of first segment
# def get_tx_delay(packet):
#     for rlc_seg in packet['rlc.attempts']:
#         for mac_attempt in rlc_seg['mac.attempts']:
#              if mac_attempt.get('phy.in_t')!=None and mac_attempt.get('phy.out_t')!=None:
#                  return (mac_attempt.get('phy.out_t')-mac_attempt.get('phy.in_t'))*1000

# re transmission delay of the first rlc segment
# def get_retx_delay(packet):
#     max_phy_delay = 0
#     for rlc_seg in packet['rlc.attempts']:
#         for mac_attempt in rlc_seg['mac.attempts']:
#              if mac_attempt.get('phy.in_t')!=None and mac_attempt.get('phy.out_t')!=None:
#                  pass

def get_tx_delay(packet):
    max_rlc_seg = get_max_rlc_seg(packet)
    max_delay = -np.inf
    for mac_attempt in max_rlc_seg['mac.attempts']:
        if mac_attempt.get('phy.in_t')!=None and mac_attempt.get('phy.out_t')!=None:
            max_delay = max(max_delay, (mac_attempt['phy.out_t']-mac_attempt['phy.in_t']))
        else:
            logger.error(f"Packet {packet['id']} phy.in_t or phy.in_t not present")
    if max_delay>-np.inf:
        return max_delay*1000
    else:
        return None

def get_segmentation_delay(packet):
    retx_delay = get_retx_delay(packet)
    tx_delay =  get_tx_delay(packet)
    if tx_delay!=None and retx_delay!=None and packet['rlc.in_t']!=None and packet['rlc.out_t']!=None:
        return (packet['rlc.out_t']-packet['rlc.in_t'])*1000-tx_delay-retx_delay
    else:
        return None

def get_segmentation_delay_wo_frame_alignment_delay(packet, sr_bsr_tx_sorted_list, slots_per_frame=20, slots_duration_ms=0.5):
    segmentation_delay = get_segmentation_delay(packet)
    frame_alignment_delay = get_frame_alignment_delay(packet, sr_bsr_tx_sorted_list, slots_per_frame=20, slots_duration_ms=0.5)
    if segmentation_delay!=None and frame_alignment_delay!=None and segmentation_delay>=frame_alignment_delay:
        return segmentation_delay-frame_alignment_delay
    else:
        return None

def get_segmentation_delay_wo_scheduling_delay(packet, sched_sorted_dict, slots_per_frame=20, slots_duration_ms=0.5):
    segmentation_delay = get_segmentation_delay(packet)
    scheduling_delay = get_scheduling_delay(packet, sched_sorted_dict, slots_per_frame=20, slots_duration_ms=0.5)
    if segmentation_delay!=None and scheduling_delay!=None and segmentation_delay>=scheduling_delay:
        return segmentation_delay-scheduling_delay
    else:
        return None

def get_segments(packet):
    return len(set([rlc_seg['so'] for rlc_seg in packet['rlc.attempts']]))

def get_mcs(packet, mcs_sorted_dict, slots_per_frame=20, slots_duration_ms=0.5):
    idx=mcs_sorted_dict.bisect_right(packet['ip.in_t']+PACKET_IN_DECISION_DELAY_MIN*slots_duration_ms*0.001)
    if idx < len(mcs_sorted_dict):
        return mcs_sorted_dict[mcs_sorted_dict.keys()[idx]]['mcs']
    else:
        return None    

def get_tb(packet, tb_sorted_dict, slots_per_frame=20, slots_duration_ms=0.5):
    idx=tb_sorted_dict.bisect_right(packet['ip.in_t']+PACKET_IN_DECISION_DELAY_MIN*slots_duration_ms*0.001)
    if idx < len(tb_sorted_dict):
        return tb_sorted_dict[tb_sorted_dict.keys()[idx]]
    else:
        return None

def get_rlc_reassembely_delay(packet):
    return (packet['ip.out_t']-packet['rlc.out_t'])*1000


def get_tbs(packet, sched_sorted_dict, slots_duration_ms=0.5):
    # Adjust packet arrival time by adding a processing delay
    adjusted_time = (
        packet["ip.in_t"] + PACKET_IN_DECISION_DELAY_MIN * slots_duration_ms * 0.001
    )

    # Find the smallest index where the key is strictly greater than the adjusted time
    idx = sched_sorted_dict.bisect_right(adjusted_time)

    # Check if the index is within bounds
    if idx < len(sched_sorted_dict):
        # Return the TBS value for the closest match after the adjusted packet time
        if "tbs" in sched_sorted_dict[sched_sorted_dict.keys()[idx]]["cause"]:
            result=sched_sorted_dict[sched_sorted_dict.keys()[idx]]["cause"]["tbs"]
        else:
            result=None
        return result
    else:
        # Return None if there is no suitable TBS entry
        return None
