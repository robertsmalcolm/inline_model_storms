# (C) British Crown Copyright 2022, Met Office.
# Please see LICENSE for license details.
import datetime
import logging
from shutil import copyfile

import cftime
import numpy as np
from scipy import interpolate

logger = logging.getLogger(__name__)


# cftime v1.0.0 doesn't allow a keyword to the datetime method to specify,
# but this introduced in v1.2.0 and so will have to use the code below to
# specify the type of datetime object to create
DATETIME_TYPES = {
    "noleap": cftime.DatetimeNoLeap,
    "365_day": cftime.DatetimeNoLeap,
    "all_leap": cftime.DatetimeAllLeap,
    "360_day": cftime.Datetime360Day,
    "julian": cftime.DatetimeJulian,
    "gregorian": cftime.DatetimeGregorian,
    "standard": cftime.DatetimeGregorian,
    "proleptic_gregorian": cftime.DatetimeProlepticGregorian,
}


def convert_date_to_step(cube, year, month, day, hour, time_period):
    """
    Calculate the step number, with the first time in a file have a step number
    of one. All calendars are handled.

    :param cube: A cube loaded from a data file from the current period.
    :type cube: :py:obj:`iris.cube.Cube`
    :param int year: The current year.
    :param int month: The current month.
    :param int day: The current day of month.
    :param int hour: The current hour.
    :param int time_period: The time period in hours between time points in the
        data.
    :returns: The time index at the specified time point.
    :rtype: int
    """
    calendar = cube.coord("time").units.calendar

    current_datetime = DATETIME_TYPES[calendar](year, month, day, hour)
    first_point = cube.coord("time").units.num2date(cube.coord("time").points[0])
    time_delta = current_datetime - first_point
    seconds_in_hour = 60**2
    step = round(time_delta.total_seconds() / (time_period * seconds_in_hour)) + 1
    print('step ',step, time_delta, time_delta.total_seconds(), time_period, seconds_in_hour)
    return step


def convert_date_to_step_csv(cube, year, month, day, hour, time_period):
    """
    Calculate the step number, with the first time in a file have a step number
    of one. All calendars are handled.

    :param cube: A cube loaded from a data file from the current period.
    :type cube: :py:obj:`iris.cube.Cube`
    :param list(int) year: Years of each storm point.
    :param int month: The current month.
    :param int day: The current day of month.
    :param int hour: The current hour.
    :param int time_period: The time period in hours between time points in the
        data.
    :returns: The time index at the specified time point.
    :rtype: int
    """
    calendar = cube.coord("time").units.calendar

    times = []
    for i, iday in enumerate(day):
        times.append(DATETIME_TYPES[calendar](year[i], month[i], day[i], hour[i]))
    
    time_delta = [x - times[0] for x in times]
    seconds_in_hour = 60**2

    step = []
    for i, iday in enumerate(day):
        step.append(round(time_delta[i].total_seconds() / (time_period * seconds_in_hour)) + 1)
    #print('step ',step, time_delta, time_period, seconds_in_hour)
    return step

def fill_trajectory_gaps(
    storm, step, lon, lat, grid_x, grid_y, cube, time_period, new_var, miss_val=-99
):
    """
    Fill the gap by linearly interpolating the last latitude, longitude,
    time and other values from the last of these values up to step. The
    trajectory is passed in to the `storm` attribute and is a standard
    `tempest_helper` dictionary. Longitudes and their interpolation may wrap
    around the 0/360 degree numerical discontinuity. The longitudes output
    are between 0 and 359 degrees.

    :param dict storm: Details of the current storm.
    :param int step: The integer number of time points of the current
        point since the start of the file.
    :param float lon: The longitude of the current point in the storm in
        degrees.
    :param float lat: The latitude of the current point in the storm in
        degrees.
    :param int grid_x: The i index of the current point in the storm
    :param int grid_y: The j index of the current point in the storm
    :param cube: A cube loaded from a data file from the current period.
    :type cube: :py:obj:`iris.cube.Cube`
    :param int time_period: The time period in hours between time points in the
        data.
    :param dict new_var: The other variables contained in the storm at the
        current point.
    :param int miss_val: value used for missing data
    """
    gap_length = step - storm["step"][-1]
    # Using technique at https://stackoverflow.com/a/14498790 to handle
    # longitudes wrapping around 0/360
    dlon = (((lon - storm["lon"][-1]) + 180) % 360 - 180) / gap_length
    dlat = (lat - storm["lat"][-1]) / gap_length
    nx = cube.shape[-1]
    dx = (grid_x - storm["grid_x"][-1]) / gap_length
    dy = (grid_y - storm["grid_y"][-1]) / gap_length
    for gap_index in range(1, gap_length):
        lon1 = (storm["lon"][-1] + dlon) % 360
        lat1 = storm["lat"][-1] + dlat
        x1 = int((storm["grid_x"][-1] + dx) % nx)
        y1 = int(storm["grid_y"][-1] + dy)
        storm["lon"].append(lon1)
        storm["lat"].append(lat1)
        storm["grid_x"].append(x1)
        storm["grid_y"].append(y1)
        storm["step"].append(storm["step"][-1] + 1)
        # interpolate the time too
        step_time_components = _calculate_gap_time(
            cube,
            storm["year"][-1],
            storm["month"][-1],
            storm["day"][-1],
            storm["hour"][-1],
            time_period,
        )
        storm["year"].append(step_time_components[0])
        storm["month"].append(step_time_components[1])
        storm["day"].append(step_time_components[2])
        storm["hour"].append(step_time_components[3])

    for var in new_var:
        if isinstance(new_var[var], list):
            # if this is a profile (list) then just use missing data
            res = new_var[var][:]
            for gap_index in range(1, gap_length):
                var1 = []
                for i in range(len(res)):
                    var1.append(miss_val)
                storm[var].append(var1)
        else:
            # interpolate the value
            dvar = (new_var[var] - storm[var][-1]) / gap_length
            for gap_index in range(1, gap_length):
                var1 = storm[var][-1] + dvar
                storm[var].append(var1)

def fill_trajectory_gaps_new(
    storm, step, lon, lat, i, j, cube, time_period, new_var, gap, miss_val=-99
):
    """
    Fill the gap by linearly interpolating the last latitude, longitude,
    time and other values from the last of these values up to step. The
    trajectory is passed in to the `storm` attribute and is a standard
    `tempest_helper` dictionary. Longitudes and their interpolation may wrap
    around the 0/360 degree numerical discontinuity. The longitudes output
    are between 0 and 359 degrees.

    :param dict storm: Details of the current storm.
    :param int step: The integer number of time points of the current
        point since the start of the file.
    :param float lon: The longitude of the current point in the storm in
        degrees.
    :param float lat: The latitude of the current point in the storm in
        degrees.
    :param int grid_x: The i index of the current point in the storm
    :param int grid_y: The j index of the current point in the storm
    :param cube: A cube loaded from a data file from the current period.
    :type cube: :py:obj:`iris.cube.Cube`
    :param int time_period: The time period in hours between time points in the
        data.
    :param dict new_var: The other variables contained in the storm at the
        current point.
    :param int miss_val: value used for missing data
    """
    #gap_length = step - storm["step"][-1]
    gap_length = gap
    # Using technique at https://stackoverflow.com/a/14498790 to handle
    # longitudes wrapping around 0/360
    dlon = (((lon - storm["lon"][-1]) + 180) % 360 - 180) / gap_length
    dlat = (lat - storm["lat"][-1]) / gap_length
    nx = cube.shape[-1]
    dx = (i - storm["i"][-1]) / gap_length
    dy = (j - storm["j"][-1]) / gap_length
    for gap_index in range(1, gap_length):
        lon1 = round((storm["lon"][-1] + dlon) % 360, 6)
        lat1 = round(storm["lat"][-1] + dlat,6)
        x1 = int((storm["i"][-1] + dx) % nx)
        y1 = int(storm["j"][-1] + dy)
        storm["lon"].append(lon1)
        storm["lat"].append(lat1)
        storm["i"].append(x1)
        storm["j"].append(y1)
        storm["step"].append(storm["step"][-1] + 1)
        storm["track_id"].append(storm["track_id"][-1])
        # interpolate the time too
        step_time_components = _calculate_gap_time(
            cube,
            storm["year"][-1],
            storm["month"][-1],
            storm["day"][-1],
            storm["hour"][-1],
            time_period,
        )
        storm["year"].append(step_time_components[0])
        storm["month"].append(step_time_components[1])
        storm["day"].append(step_time_components[2])
        storm["hour"].append(step_time_components[3])

    for var in new_var:
        if isinstance(new_var[var], list):
            # if this is a profile (list) then just use missing data
            res = new_var[var][:]
            for gap_index in range(1, gap_length):
                var1 = []
                for i in range(len(res)):
                    var1.append(miss_val)
                storm[var].append(var1)
        else:
            # interpolate the value
            dvar = round((new_var[var] - storm[var][-1]) / gap_length, 5)
            for gap_index in range(1, gap_length):
                var1 = storm[var][-1] + dvar
                storm[var].append(var1)

def fill_trajectory_gaps_csv(columns, columns_variable, storm, steps, cube, gap, time_period):

    storm_new = {}
    # do simple linear interpolate for the variables
    for col in columns_variable:
        x = steps
        y = storm[col]
        f = interpolate.interp1d(x, y)

        xnew = np.arange(x[0], x[-1], gap)
        ynew = f(xnew)
        storm_new[col] = ynew

    return storm_new

def _calculate_gap_time(cube, year, month, day, hour, time_period):
    """
    Calculate the date and time for the next interpolated time point.

    :param iris.cube.Cube cube: A cube loaded from a data file from the
        current period.
    :param int year: The year of the last time point.
    :param int month: The month of the last time point.
    :param int day: The day of the month of the last time point.
    :param int hour: The hour of the last time point.
    :param int time_period: The time period in hours between time points in the
        data.
    :returns: The year, month, day and hour of the interpolated time point.
    :rtype: tuple
    """
    calendar = cube.coord("time").units.calendar

    last_datetime = DATETIME_TYPES[calendar](year, month, day, hour)
    time_delta = datetime.timedelta(hours=time_period)
    this_datetime = last_datetime + time_delta
    this_datetime_tuple = (
        this_datetime.year,
        this_datetime.month,
        this_datetime.day,
        this_datetime.hour,
    )
    return this_datetime_tuple


def _storm_dates(storm):
    """
    Calculate the date string for each point in the storm.

    :param dict storm: Storm dictionary.
    :returns: The list of date strings for this storm.
    :rtype: list
    """
    dates = []
    for it, year in enumerate(storm["year"]):
        dates.append(
            str(storm["year"][it])
            + str(storm["month"][it]).zfill(2)
            + str(storm["day"][it]).zfill(2)
            + str(storm["hour"][it]).zfill(2)
        )
    return dates


def storms_overlap_in_time(storm_x, storms_y):
    """
    Find the subset of list storms_y that have some overlap in time with storm_x

    :param dict storm_x: Storm dictionary.
    :param list storms_y: List of storm dictionaries
    :returns: The list of storms that overlap in time with storm_x.
    :rtype: list
    """
    set_x = set(_storm_dates(storm_x))
    storms_overlap = []
    for storm in storms_y:
        set_y = set(_storm_dates(storm))
        overlap = set_x.intersection(set_y)
        if len(overlap) >= 1:
            storms_overlap.append(storm)

    return storms_overlap


def storm_overlap_in_space(storm_c, storms_y, distance_threshold=0.5):
    """
    Find if any of the storms that have any overlap in space with storm_c. Expect at
    most one.
    There is some overlap in time already determined.

    :param dict storm_c: Storm dictionary.
    :param list storms_y: List of storm dictionaries which overlap storm_c in time
    :param float distance_threshold: maximum distance (degrees) for storms to
       be apart but identified as overlapping in space
    :returns: Either None, or a dictionary including storm information about the
       overlap.
    :rtype: None or dict
    """
    storm_overlap = None
    set_c = _storm_dates(storm_c)
    for ist, storm_p in enumerate(storms_y):
        n_pts_overlap = 0
        set_p = _storm_dates(storm_p)
        # overlapping times
        overlap = sorted(list(set(set_c).intersection(set_p)))

        time_c = set_c.index(overlap[0])
        time_p = set_p.index(overlap[0])
        lat_c = storm_c["lat"]
        lon_c = storm_c["lon"]
        lat_p = storm_p["lat"]
        lon_p = storm_p["lon"]
        # just look at the point where the storms overlap in time
        it = 0
        timec = time_c + it
        timep = time_p + it
        dist_lat = np.abs(lat_c[timec] - lat_p[timep])
        dist_lon = np.abs(lon_c[timec] - lon_p[timep])
        if dist_lat < distance_threshold and dist_lon < distance_threshold:
            n_pts_overlap += 1

        # now find out how much time-space overlap
        # is it exactly the same storm - we can remove the duplicate from the
        #   earlier dataset
        # is it an extension - we need to remove from the earlier dataset, and
        #   extend the storm in the current dataset
        if n_pts_overlap > 0:
            storm_overlap = {}
            storm_overlap["early"] = storm_p
            storm_overlap["late"] = storm_c
            storm_overlap["time_c"] = time_c
            storm_overlap["time_p"] = time_p
            storm_overlap["offset"] = time_p - time_c
            logger.debug(
                f"time_c, time_p, len(lat_c), len(lat_p), len(overlap), offset ",
                f"{time_c} {time_p} {len(lat_c)} {len(lat_p)} {len(overlap)}",
                f"{storm_overlap['offset']}",
            )
            if len(lat_c) == len(lat_p) == len(overlap):
                # exactly the same storm
                storm_overlap["method"] = "remove"
            else:
                # figure out how they overlap
                if time_c == time_p:
                    # storm has same start time in both
                    if len(lat_c) >= len(lat_p):
                        # the current storm is longer, so just remove the previous one
                        storm_overlap["method"] = "remove"
                    else:
                        # the previous storm is longer, so need to insert
                        storm_overlap["method"] = "extend_odd"
                elif time_p > time_c:
                    # the earlier dataset has the start of the storm
                    # want to extend set_x backwards in time
                    storm_overlap["method"] = "extend"
                elif time_c > time_p:
                    # the later dataset has the start of the storm
                    storm_overlap["method"] = "remove"
            return storm_overlap

    return storm_overlap


def write_track_line(storm, no_lines, new_length, column_names):

    """
    Produce a line of Tempest txt file output matching the track file format

    :param dict storm: Storm dictionary.
    :param int no_lines: Number of time values to read from the storm
    :param int new_length: The new length of the storm
    :param dict column_names: The names of the storm keys (columns of output file)
    :returns: string and list of strings: the first is the new header line for this
        storm the second is a list of lines to be written to the track txt file
    :rtype: str, list
    """
    track_line_date = (
        "start   {}      {}    {}       {}      {}".format(
            str(new_length),
            str(storm["year"][0]),
            str(storm["month"][0]),
            str(storm["day"][0]),
            str(storm["hour"][0]),
        )
        + "\n"
    )

    # need to derive the ordered list of variables to write to correct columns
    # formatting is different for position values and variables
    reversed_name_key = dict(map(reversed, column_names.items()))
    column_ordered = []
    for iv in range(len(column_names)):
        column_ordered.append(reversed_name_key[iv])

    track_lines = []
    track_line_start = "        {}     {}     {}      {}   "
    track_line_end = "   {}    {}       {}      {} \n"

    logger.debug(
        f"no_lines, len(storm[grid_x]), len(storm[year])",
        f"{no_lines} {len(storm['grid_x'])} {len(storm['year'])} ",
        f"{storm['year']} {storm['month']} {storm['day']} {storm['hour']}",
    )
    for it in range(no_lines):
        grid_x = str(storm["grid_x"][it])
        grid_y = str(storm["grid_y"][it])
        lat = "{:.6f}".format(float(storm["lat"][it]))
        lon = "{:.6f}".format(float(storm["lon"][it]))
        year = str(storm["year"][it])
        month = str(storm["month"][it])
        day = str(storm["day"][it])
        hour = str(storm["hour"][it])

        line_start = track_line_start.format(grid_x, grid_y, lon, lat)
        line_end = track_line_end.format(year, month, day, hour)
        line_vars = ""
        for var in column_ordered[4:-4]:
            if "list" in str(type(storm[var][it])):
                logger.debug(f"storm[var][it] {var} {storm[var][it]}")
                line_list = []
                for i in range(len(storm[var][it])):
                    val = "{:.6e}".format((float(storm[var][it][i])))
                    line_list.append(val)
                line_list = '"[' + ",".join(line_list) + ']"'
                line_vars += "    " + line_list
                logger.debug(f"line_list {line_list}")
            else:
                line_vars += "    " + "{:.6e}".format((float(storm[var][it])))
        track_lines.append(line_start + line_vars + line_end)

    return track_line_date, track_lines


def remove_duplicates_from_track_files(
    tracked_file_Tm1,
    tracked_file_T,
    tracked_file_Tm1_adjust,
    tracked_file_T_adjust,
    storms_match,
    column_names,
):

    """
    Rewrite the .txt track files, removing the matching storms from the
    previous timestep which have been found in the current timestep and
    adding them to this current timestep

    :param str tracked_file_Tm1: The path to the track file from the previous timestep.
    :param str tracked_file_T: The path to the track file from the current timestep.
    :param str tracked_file_Tm1_adjust: The path to the updated track file
        for the previous time for output.
    :param str tracked_file_T_adjust: The path to the updated track file
        for the current timestep for output.
    :param list storms_match: The storms which have been found to match
        with a later time
    :param dict column_names: the keys for the storm columns in the output file
    """
    header_delim = "start"

    if len(storms_match) == 0:
        copyfile(tracked_file_Tm1, tracked_file_Tm1_adjust)
        return

    with open(tracked_file_Tm1) as file_input:
        with open(tracked_file_Tm1_adjust, "w") as file_output:
            for line in file_input:
                line_array = line.split()
                if header_delim in line:
                    line_of_traj = 0  # reset trajectory line to zero
                    matching_track = False
                    line_header = line
                    track_length = int(line_array[1])
                    start_date = (
                        line_array[2]
                        + line_array[3].zfill(2)
                        + line_array[4].zfill(2)
                        + line_array[5].zfill(2)
                    )
                else:
                    if line_of_traj <= track_length:
                        lon = float(line_array[2])
                        lat = float(line_array[3])
                        if line_of_traj == 0:
                            for storm in storms_match:
                                storm_old = storm["early"]
                                date = _storm_dates(storm_old)[0]
                                if (
                                    date == start_date
                                    and track_length == storm_old["length"]
                                ):
                                    if (
                                        lon == storm_old["lon"][0]
                                        and lat == storm_old["lat"][0]
                                    ):
                                        matching_track = True
                            if not matching_track:
                                file_output.write(line_header)
                                file_output.write(line)
                        else:
                            if not matching_track:
                                file_output.write(line)
                        line_of_traj += 1

    with open(tracked_file_T) as file_input:
        with open(tracked_file_T_adjust, "w") as file_output:
            for line in file_input:
                line_array = line.split()
                if header_delim in line:
                    line_of_traj = 0  # reset trajectory line to zero
                    matching_track = False
                    line_header = line
                    track_length = int(line_array[1])
                    start_date = (
                        line_array[2]
                        + line_array[3].zfill(2)
                        + line_array[4].zfill(2)
                        + line_array[5].zfill(2)
                    )
                else:
                    if line_of_traj <= track_length:
                        lon = float(line_array[2])
                        lat = float(line_array[3])
                        if line_of_traj == 0:
                            match_type = ""
                            for storm in storms_match:
                                storm_old = storm["early"]
                                storm_new = storm["late"]
                                date = _storm_dates(storm_new)[0]
                                if (
                                    date == start_date
                                    and track_length == storm_new["length"]
                                ):
                                    if (
                                        lon == storm_new["lon"][0]
                                        and lat == storm_new["lat"][0]
                                    ):
                                        matching_track = True
                                        match_type = storm["method"]
                                        storm_old_match = storm_old
                                        match_offset = storm["offset"]
                            if not matching_track:
                                file_output.write(line_header)
                                file_output.write(line)
                            else:
                                if match_type == "extend":
                                    line_extra = ""
                                    new_length = track_length + match_offset
                                    new_date_line, new_track_lines = write_track_line(
                                        storm_old_match,
                                        match_offset,
                                        new_length,
                                        column_names,
                                    )
                                    line_header = new_date_line

                                    for new_line in new_track_lines:
                                        line_extra += new_line

                                elif match_type == "remove":
                                    line_extra = ""
                                else:
                                    line_extra = ""
                                file_output.write(line_header)
                                file_output.write(line_extra)
                                file_output.write(line)

                        else:
                            file_output.write(line)
                        line_of_traj += 1
