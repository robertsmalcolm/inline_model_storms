# (C) British Crown Copyright 2022, Met Office.
# Please see LICENSE for license details.
import os
import numpy as np
import logging

from cftime import date2num, datetime
from netCDF4 import Dataset
import pandas as pd

logger = logging.getLogger(__name__)


def define_netcdf_metadata(var_cmpt, variable_units):
    """
    Define potential metadata for the netcdf variables
    """
    long_name = "unknown"
    description = "unknown"
    units = "1"

    var_components = var_cmpt.split("_")
    var = var_components[0]

    if "slp" in var or "psl" in var:
        standard_name = "air_pressure_at_mean_sea_level"
        long_name = "Sea Level Pressure"
        description = "Sea level pressure for tracked variable"
        units = variable_units["psl"]
    elif "sfcWind" in var:
        standard_name = "wind_speed"
        long_name = "Near-surface Wind Speed"
        description = "near-surface (usually 10 metres) wind speed"
        units = variable_units["sfcWind"]
    elif "orog" in var:
        standard_name = "surface_altitude"
        long_name = "Surface Altitude"
        description = "Surface altitude (height above sea level)"
        units = variable_units["orog"]
    elif "wind" in var:
        standard_name = "wind_speed"
        units = variable_units["wind"]
    elif "rv" in var:
        standard_name = "relative_vorticity"
        units = "s-1"
    elif "rh" in var:
        standard_name = "relative_humidity"
        units = "%"
    elif "ts" in var:
        standard_name = "surface_temperature"
        units = variable_units["ts"]
    elif "zg" in var:
        standard_name = "geopotential_height"
        long_name = "Geopotential Height"
        description = "Geopotential height difference"
        units = "m"
    elif "rsize" in var or "radius" in var:
        standard_name = "radius"
        long_name = "storm radius"
        description = "radius of the storm"
        units = "degrees"
    elif "ace" in var:
        standard_name = "ace"
        long_name = "Accumulated Cyclone Energy"
        description = "Instantaneous ACE of storm"
        units = "1"
    elif "pace" in var:
        standard_name = "ace"
        long_name = "Accumulated Cyclone Energy (from psl)"
        description = "Instantaneous ACE of storm using psl"
        units = "1"
    elif "ike" in var:
        standard_name = "ike"
        long_name = "Integrated Kinetic Energy"
        description = "Instantaneous IKE of storm"
        units = "1"
    elif "pdi" in var:
        standard_name = "pdi"
        long_name = "Potential Dissipation Index"
        description = "Instantaneous PDI of storm"
        units = "1"
    elif "max_core" in var:
        standard_name = "max_closed_contour"
        long_name = "Maximum closed contour within radius"
        description = "From TempestExtremes max_closed_contour_delta"
        units = "1"
    elif "rprof" in var:
        standard_name = "radial_profile"
        long_name = "storm radial profile"
        description = "radial profile of the storm"
        units = "degrees"
    else:
        standard_name = var
        long_name = var
        description = "Unknown variable"
        units = "1"

    return standard_name, long_name, description, units


def guess_variable_units(output_vars, variable_units):
    """
    in the case that variable_units are not passed into save_trajectories,
    we will guess them here
    :return:
    """
    units = {}
    units["psl"] = "Pa"
    units["sfcWind"] = "m s-1"
    units["zg"] = "m"
    units["orog"] = "m"
    units["wind"] = "m s-1"
    units["rvT63"] = "s-1"
    units["rvT42"] = "s-1"
    units["rv"] = "s-1"
    units["rh"] = "%"
    units["ts"] = "K"
    units["rsize"] = "degrees"
    units["radius"] = "degrees"
    units["ace"] = "1"
    units["acepsl"] = "1"
    units["ike"] = "1"
    units["pdi"] = "1"
    units["rprof"] = "degrees"

    if len(variable_units) == 0:
        variable_units_new = {}
    else:
        variable_units_new = variable_units.copy()

    for var in output_vars:
        varname = var.split("_")[0]
        if varname not in variable_units.keys():
            if varname in units.keys(): 
                variable_units_new[varname] = units[varname]
            else:
                variable_units_new[varname] = "1"
    return variable_units_new


def save_trajectories_netcdf(
    directory,
    savefname,
    storms,
    calendar,
    time_units,
    variable_units,
    frequency,
    um_suiteid,
    resolution_code,
    cmd_detect,
    cmd_stitch,
    column_names,
    startperiod="",
    endperiod="",
):

    """
    Create netcdf file for the tracks.
    May need metadata from a model nc file, so may need to create at a time when
    these are available

    :param str directory: directory path
    :param str savefname: filename to save netcdf file to
    :param list storms: The loaded trajectories.
    :param str calendar: netcdf calendar type
    :param str time_units: units string for the time coordinate
    :param str variable_units: units for the different variables
    :param str frequency:
    :param str um_suiteid: UM suiteid for netcdf metadata
    :param str resolution_code: String describing model resolution
    :param str cmd_detect: the TempestExtremes detect command string
    :param str cmd_stitch: the TempestExtremes stitch command string
    :param dict column_names: output variable names derived from the Tempest command
    :param str startperiod: An optional time string for the start of this data
    :param str endperiod: AN optional time string for the end of this data period
    """
    logger.debug("making netCDF of outputs")
    logger.debug(f"open nc file {os.path.join(directory, savefname)}")
    nc = Dataset(os.path.join(directory, savefname), "w", format="NETCDF4")
    nc.title = "Tempest TC tracks"
    nc.directory = directory
    nc.tracked_data_frequency = frequency
    logger.debug(f"nc.title {nc.title}")

    nc.mo_runid = um_suiteid
    nc.grid = resolution_code
    nc.start_date = startperiod
    nc.end_date = endperiod
    nc.institution_id = "MOHC"
    nc.algorithm = "TempestExtremes_v2"
    nc.algorithm_ref = (
        "Ullrich and Zarzycki 2017; Zarzycki and Ullrich 2017; " + "Ullrich et al. 2020"
    )
    nc.detect_cmd = cmd_detect
    nc.stitch_cmd = cmd_stitch

    record_length = 0
    tracks = 0
    for storm in storms:
        tracks += 1
        storm_length = storm["length"]
        record_length += storm_length

    nc.createDimension("tracks", size=tracks)
    nc.createDimension("record", size=record_length)

    nc.createVariable("FIRST_PT", np.int32, ("tracks"))
    nc.createVariable("NUM_PTS", np.int32, ("tracks"))
    nc.createVariable("TRACK_ID", np.int32, ("tracks"))
    nc.createVariable("index", np.int32, ("record"))
    nc.createVariable("time", "f8", ("record"))
    nc.createVariable("lon", "f4", ("record"))
    nc.createVariable("lat", "f4", ("record"))

    #output_vars_all = list(column_names.keys()).copy()
    #output_vars_all = storms.columns
    output_vars_all = list(storms[0].keys())
    print('output_vars_all ',output_vars_all)
    for pos in ["i", "j", "lon", "lat", "year", "month", "day", "hour", "length"]:
        output_vars_all.remove(pos)

    list_dim_created = False
    for var in output_vars_all:
        if "list" in str(type(storm[var][0])):
            list_size = len(storm[var][0])
            if not list_dim_created:
                nc.createDimension("record_profile", size=record_length * list_size)
                list_dim_created = True
            nc.createVariable(var, "f8", ("record_profile"))
        else:
            nc.createVariable(var, "f8", ("record"))

    nc.variables["FIRST_PT"].units = "ordinal"
    nc.variables["FIRST_PT"].long_name = "first_pt"
    nc.variables["FIRST_PT"].description = "Index to first point of this track number"

    nc.variables["NUM_PTS"].units = "ordinal"
    nc.variables["NUM_PTS"].long_name = "num_pts"
    nc.variables["NUM_PTS"].description = "Number of points for this track"

    nc.variables["TRACK_ID"].units = "ordinal"
    nc.variables["TRACK_ID"].long_name = "track_id"
    nc.variables["TRACK_ID"].description = "Tropical cyclone track number"

    nc.variables["index"].units = "ordinal"
    nc.variables["index"].long_name = "track_id"
    nc.variables["index"].description = "Track sequence number (0 - length of track-1)"

    nc.variables["lat"].units = "degrees_north"
    nc.variables["lat"].standard_name = "latitude"
    nc.variables["lat"].long_name = "latitude"
    nc.variables[
        "lat"
    ].description = "Latitude (degrees north) associated with tracked variable"

    nc.variables["lon"].units = "degrees_east"
    nc.variables["lon"].standard_name = "longitude"
    nc.variables["lon"].long_name = "longitude"
    nc.variables[
        "lon"
    ].description = "Longitude (degrees east) associated with tracked variable"

    nc.variables["time"].units = time_units
    nc.variables["time"].calendar = calendar
    nc.variables["time"].standard_name = "time"
    nc.variables["time"].long_name = "time"

    #if len(variable_units) == 0:
    variable_units_new = guess_variable_units(output_vars_all, variable_units)

    for var in output_vars_all:
        standard_name, long_name, description, v_units = define_netcdf_metadata(
            var, variable_units_new
        )
        logger.debug(f"var, units {var} {v_units} ")
        nc.variables[var].standard_name = standard_name
        nc.variables[var].long_name = long_name
        nc.variables[var].description = description
        nc.variables[var].units = str(v_units)

    # read the storms and write the values to the file
    # track: first_pt, num_pts, track_id
    # record: lat, lon, time, psl, index(0:tracklen-1)
    first_pt = []
    num_pts = []
    track_id = []
    lon = []
    lat = []
    time = []
    index = []

    variables_to_write = {}
    for var in output_vars_all:
        variables_to_write[var] = []

    first_pt_index = 0
    for ist, storm in enumerate(storms):
        first_pt.append(first_pt_index)
        num_pts.append(storm["length"])
        track_id.append(ist)
        first_pt_index += storm["length"]

        for ipt in range(storm["length"]):
            t1 = date2num(
                datetime(
                    storm["year"][ipt],
                    storm["month"][ipt],
                    storm["day"][ipt],
                    storm["hour"][ipt],
                    calendar=calendar,
                ),
                time_units,
                calendar=calendar,
            )
            time.append(t1)
            index.append(ipt)
            lon.append(storm["lon"][ipt])
            lat.append(storm["lat"][ipt])
            for var in output_vars_all:
                if "rprof" in var:
                    variables_to_write[var].append(storm[var][ipt][:])
                else:
                    variables_to_write[var].append(storm[var][ipt])

    logger.debug(f"first_pt {first_pt} ")
    logger.debug(f"tracks, record_length {tracks} {record_length} ")
    logger.debug(f"len(first_pt) {len(first_pt)} ")
    logger.debug(f"len(lon) {len(lon)} ")

    # now write variables to netcdf
    nc.variables["FIRST_PT"][:] = first_pt
    nc.variables["NUM_PTS"][:] = num_pts
    nc.variables["TRACK_ID"][:] = track_id
    nc.variables["index"][:] = index
    nc.variables["lon"][:] = lon
    nc.variables["lat"][:] = lat
    nc.variables["time"][:] = time
    for var in output_vars_all:
        logger.debug(f"var {var} ")
        nc.variables[var][:] = variables_to_write[var]
    logger.debug(f"written nc file {nc.variables}")

    nc.close()
