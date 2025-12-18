def compute_tof_difference_1(tof_rx_1, tof_rx_2, a, b, c, d):
    ## COMPUTES TOF OF SIMULATION.
    ## SEE ATTACHED DIAGRAM sys_diagram#1.img

    ## LENGTH
    # Cable Length
    a_len = a
    b_len = b
    rx_1_cable_len = b_len
    # Cable Length
    c_len = c
    d_len = d
    rx_2_cable_len = c_len + d_len + a_len

    ## TIME
    ## 1F = 1.5ns of delay in cable
    ns_per_ft = 1.5
    rx_1_cable_time = rx_1_cable_len * ns_per_ft
    rx_2_cable_time = rx_2_cable_len * ns_per_ft

    rx_1 = tof_rx_1 - rx_1_cable_time
    rx_air_tof = tof_rx_2 - rx_2_cable_time - rx_1
    # print(f"OverTheAirTOF: {rx_air_tof}")

    return rx_air_tof

if __name__ == "__main__":
    tof_rx_1 = 6
    tof_rx_2 = 15
    a = 3
    b = 1
    c = 10
    d = 50
    compute_tof_difference_1(tof_rx_1, tof_rx_2, a, b, c, d)
